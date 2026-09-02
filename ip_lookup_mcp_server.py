# -*- coding: utf-8 -*-
"""
IP 归属地查询 · 远程 MCP Server
------------------------------
部署在 mcp.pianam.cn，任何支持 MCP 协议的 AI 客户端
(Claude Desktop / Cursor / Cline 等) 填入 URL 即可查询 IP 归属地。
数据源：ip-api.com（免费、无需 API Key，中文直出），
网络异常时自动切换备用通道 ipwho.is（免费 1 万次/月）。纯只读查询。
注意：ip-api.com 免费版按服务器出口 IP 限流 45 次/分钟，
结果缓存 24 小时 + 共用限流中间件，正常使用不会触顶。

Author: liufuyang  2026-09-01
"""
import json
import os
import re
import ssl
import time
import urllib.parse
import urllib.request
from pathlib import Path

from mcp.server.fastmcp import FastMCP, Context
from mcp.server.transport_security import TransportSecuritySettings

BASE_DIR = Path(__file__).parent

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
# ipwho.is 备用通道用 curl 类 UA
UA_CURL = "curl/8.4.0"
# 备用源返回英文国家名，补中文映射（常见国家/地区）
COUNTRY_CN = {
    "China": "中国", "United States": "美国", "Japan": "日本", "South Korea": "韩国",
    "Hong Kong": "中国香港", "Taiwan": "中国台湾", "Singapore": "新加坡",
    "United Kingdom": "英国", "Germany": "德国", "France": "法国", "Russia": "俄罗斯",
    "Canada": "加拿大", "Australia": "澳大利亚", "India": "印度", "Thailand": "泰国",
    "Vietnam": "越南", "Malaysia": "马来西亚", "Indonesia": "印度尼西亚",
    "Philippines": "菲律宾", "Netherlands": "荷兰", "Italy": "意大利",
    "Spain": "西班牙", "Brazil": "巴西", "Mexico": "墨西哥", "Switzerland": "瑞士",
    "Sweden": "瑞典", "Norway": "挪威", "Denmark": "丹麦", "Finland": "芬兰",
    "Poland": "波兰", "Turkey": "土耳其", "Ireland": "爱尔兰", "Belgium": "比利时",
    "Austria": "奥地利", "New Zealand": "新西兰", "South Africa": "南非",
    "United Arab Emirates": "阿联酋", "Saudi Arabia": "沙特阿拉伯", "Israel": "以色列",
}
# 备用源省份/州名中文化（中国省份拼音 + 美/澳/日常见项；不含的保留原文）
REGION_CN = {
    "Jiangsu Sheng": "江苏", "Shandong Sheng": "山东", "Guangdong Sheng": "广东",
    "Zhejiang Sheng": "浙江", "Henan Sheng": "河南", "Sichuan Sheng": "四川",
    "Hubei Sheng": "湖北", "Hunan Sheng": "湖南", "Hebei Sheng": "河北",
    "Fujian Sheng": "福建", "Anhui Sheng": "安徽", "Liaoning Sheng": "辽宁",
    "Shaanxi Sheng": "陕西", "Jiangxi Sheng": "江西", "Shanxi Sheng": "山西",
    "Guangxi Zhuang Autonomous Region": "广西", "Yunnan Sheng": "云南",
    "Guizhou Sheng": "贵州", "Heilongjiang Sheng": "黑龙江", "Jilin Sheng": "吉林",
    "Gansu Sheng": "甘肃", "Inner Mongolia Autonomous Region": "内蒙古",
    "Xinjiang Uyghur Autonomous Region": "新疆", "Tibet Autonomous Region": "西藏",
    "Hainan Sheng": "海南", "Ningxia Hui Autonomous Region": "宁夏",
    "Qinghai Sheng": "青海", "Tianjin Municipality": "天津",
    "Shanghai Municipality": "上海", "Beijing Municipality": "北京",
    "Chongqing Municipality": "重庆",
    "Hong Kong SAR": "香港", "Macau SAR": "澳门", "Taiwan": "台湾",
    "California": "加利福尼亚州", "New York": "纽约州", "Texas": "得克萨斯州",
    "Washington": "华盛顿州", "Virginia": "弗吉尼亚州", "Florida": "佛罗里达州",
    "Illinois": "伊利诺伊州", "Massachusetts": "马萨诸塞州",
    "Queensland": "昆士兰州", "New South Wales": "新南威尔士州",
    "Victoria": "维多利亚州", "Tokyo": "东京都", "Osaka": "大阪府", "Seoul": "首尔",
}


def region_cn(name):
    if not name:
        return ""
    if name in REGION_CN:
        return REGION_CN[name]
    if name.endswith(" Sheng"):  # 未收录的中国省份拼音：去后缀
        return name[:-6]
    return name


_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

CACHE_TTL = 24 * 3600  # IP 归属地基本不变，缓存 24 小时
_ip_cache = {}

_IP_RE = re.compile(
    r"^(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)$"
)


def _http_get_json(url, timeout=15, ua=UA):
    req = urllib.request.Request(url)
    req.add_header("User-Agent", ua)
    req.add_header("Accept", "application/json,text/plain,*/*")
    resp = urllib.request.urlopen(req, timeout=timeout, context=_SSL_CTX)
    return json.loads(resp.read().decode("utf-8", errors="ignore"))


def _xff_ip(ctx):
    """从请求头取调用方真实 IP（nginx 已注入 X-Forwarded-For）。"""
    # FastMCP Context 暴露 starlette request
    try:
        req = ctx.request_context.request
        xff = req.headers.get("x-forwarded-for", "")
        if xff:
            first = xff.split(",")[0].strip()
            if first:
                return first
        xri = req.headers.get("x-real-ip", "")
        if xri.strip():
            return xri.strip()
        if req.client:
            return req.client.host
    except Exception:
        return None
    return None


def fetch_ip_api(ip):
    """主通道：ip-api.com（中文直出，HTTP 免费端点）。"""
    url = (f"http://ip-api.com/json/{urllib.parse.quote(ip)}"
           "?lang=zh-CN&fields=status,message,country,regionName,city,"
           "zip,lat,lon,timezone,isp,org,as,query")
    d = _http_get_json(url, timeout=20)
    if d.get("status") != "success":
        raise RuntimeError(d.get("message") or "ip-api 查询失败")
    loc = "".join(p for p in [d.get("country"), d.get("regionName"), d.get("city")] if p)
    return {
        "IP": d.get("query", ip),
        "归属地": loc or "未知",
        "国家": d.get("country", ""),
        "省份/地区": d.get("regionName", ""),
        "城市": d.get("city", ""),
        "经纬度": f"{d.get('lat')}, {d.get('lon')}",
        "时区": d.get("timezone", ""),
        "运营商": d.get("isp", ""),
        "组织": d.get("org", ""),
        "AS": d.get("as", ""),
        "数据源": "ip-api.com",
    }


def fetch_ipwho_is(ip):
    """备用通道：ipwho.is（免费 1 万次/月，HTTPS）。"""
    d = _http_get_json(f"https://ipwho.is/{urllib.parse.quote(ip)}", timeout=15, ua=UA_CURL)
    if not d.get("success"):
        raise RuntimeError(d.get("message") or "ipwho.is 查询失败")
    country_en = d.get("country", "")
    country_cn = COUNTRY_CN.get(country_en, country_en)
    region = region_cn(d.get("region", ""))
    conn = d.get("connection") or {}
    tz = d.get("timezone") or {}
    loc = "".join(p for p in [country_cn, region, d.get("city")] if p)
    asn = conn.get("asn")
    as_text = f"AS{asn} {conn.get('org','')}".strip() if asn else (conn.get("org") or "")
    return {
        "IP": d.get("ip", ip),
        "归属地": loc or "未知",
        "国家": country_cn,
        "省份/地区": region,
        "城市": d.get("city", ""),
        "经纬度": f"{d.get('latitude')}, {d.get('longitude')}",
        "时区": tz.get("id", "") if isinstance(tz, dict) else str(tz),
        "运营商": conn.get("isp") or conn.get("org") or "",
        "组织": conn.get("org") or "",
        "AS": as_text,
        "数据源": "ipwho.is（备用通道）",
    }


def lookup_raw(ip):
    ip = (ip or "").strip()
    if not ip:
        return {"error": "没有获取到调用方 IP，请在参数里直接传入要查询的 IP 地址，例如 8.8.8.8"}
    if not _IP_RE.match(ip):
        return {"error": f"「{ip}」不是合法的 IPv4 地址，请检查后重试"}

    cached = _ip_cache.get(ip)
    if cached and time.time() - cached[0] < CACHE_TTL:
        return cached[1]

    err = None
    try:
        out = fetch_ip_api(ip)
    except Exception as e:
        err = f"{type(e).__name__}: {e}"
        try:
            out = fetch_ipwho_is(ip)
        except Exception as e2:
            return {"error": f"查询失败（主通道 {err}；备用通道 {type(e2).__name__}: {e2}）"}

    out["说明"] = "归属地数据来自公开 IP 地理库，仅供参考；运营商/城市可能有偏差"
    if err:
        out["备用通道原因"] = err
    _ip_cache[ip] = (time.time(), out)
    return out


mcp = FastMCP(
    "ip-location-query",
    host=os.environ.get("MCP_HOST", "127.0.0.1"),
    port=int(os.environ.get("MCP_PORT", "8006")),
    transport_security=TransportSecuritySettings(
        allowed_hosts=(os.environ.get("MCP_ALLOWED_HOSTS") or "127.0.0.1:*,localhost:*,[::1]:*,mcp.pianam.cn,mcp.pianam.cn:*").split(","),
        allowed_origins=(os.environ.get("MCP_ALLOWED_ORIGINS") or "https://mcp.pianam.cn,https://mcp.pianam.cn:*,http://127.0.0.1:*,http://localhost:*").split(","),
    ),
)


@mcp.tool()
def query_ip_location(ip: str = "", ctx: Context = None) -> dict:
    """查询 IP 地址的归属地和运营商信息。

    参数:
        ip: 要查询的 IPv4 地址，例如 "8.8.8.8"、"114.114.114.114"；
            留空时尝试查询调用方自己的公网 IP（部分网络环境下取不到，需手动传入）
    返回:
        归属地（国家/省份/城市）、经纬度、时区、运营商/组织、AS 编号。
    数据源: ip-api.com（免费无需 Key），网络异常时自动切换 ipwho.is。
    """
    try:
        target = (ip or "").strip()
        if not target and ctx is not None:
            target = _xff_ip(ctx) or ""
        return lookup_raw(target)
    except Exception as e:
        return {"error": f"查询失败: {type(e).__name__}: {e}"}


if __name__ == "__main__":
    # 挂限流中间件：必须用 uvicorn 直接跑自定义 app——mcp.run() 内部会另建 app 实例，外挂中间件会被丢弃
    import sys
    import uvicorn
    sys.path.insert(0, str(BASE_DIR))
    from rate_limit import RateLimitMiddleware
    _app = mcp.streamable_http_app()
    _app.add_middleware(RateLimitMiddleware, limit_per_minute=60)
    uvicorn.run(_app, host=mcp.settings.host, port=mcp.settings.port, log_level=mcp.settings.log_level.lower())
