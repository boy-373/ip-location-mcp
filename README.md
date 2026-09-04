# IP Location MCP

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![MCP](https://img.shields.io/badge/MCP-Server-blue)](https://modelcontextprotocol.io)
[![Remote](https://img.shields.io/badge/Streamable%20HTTP-hosted%20free-success)](https://mcp.pianam.cn/ip-mcp/mcp)

**IPv4 geolocation lookup with Chinese output** — country/region/city, coordinates, timezone and ISP/ASN info, with automatic fallback between two free providers.

- **Try it in 30 seconds**: a free public MCP endpoint is already running — just paste the URL into your MCP client (no install, no API key).
- **Or self-host**: a single Python file, stdlib HTTP + FastMCP, zero paid dependencies.

## ⚡ Use the hosted endpoint (no setup)

```
https://mcp.pianam.cn/ip-mcp/mcp
```

Transport: **Streamable HTTP** (MCP 2025-03-26 compatible). No authentication required.

## 🔌 Client configuration

Add this to your MCP client's `mcpServers` configuration (Claude Desktop `claude_desktop_config.json`, Cursor `mcp.json`, Cline, Cherry Studio, etc.):

```json
{
  "mcpServers": {
    "ip-location": {
      "type": "http",
      "url": "https://mcp.pianam.cn/ip-mcp/mcp"
    }
  }
}
```

> Clients that do not accept `"type": "http"` (some Cherry Studio / older
> Cline versions) accept the same entry with just `"url"`.

## 🧰 Tools

| Tool | Parameters | Returns |
|---|---|---|
| `query_ip_location(ip="", ctx=None)` | `ip`: IPv4 address, e.g. `"8.8.8.8"`. Empty: attempts the caller's own public IP (via X-Forwarded-For). | 归属地 (country/region/city), coordinates, timezone, ISP, organization and AS number — in Chinese. Error message for invalid/non-IPv4 input. |

## 📡 Data sources, caching & limits

- Primary source: **[ip-api.com](https://ip-api.com/)** — free endpoint with direct Chinese-language output.
- Automatic fallback: **[ipwho.is](https://ipwho.is/)** (free, 10k requests/month) with built-in English→Chinese country/province mapping (all Chinese provinces + US/AU/JP/KR common regions).
- Results cached for **24 hours** (geolocation barely changes); hosted endpoint rate-limited to **60 requests / minute / IP**.
- No API key, no login; read-only lookups.

## 🐢 Self-hosting

```bash
git clone https://github.com/boy-373/ip-location-mcp.git
cd ip-location-mcp
pip install -r requirements.txt
python ip_lookup_mcp_server.py
# the server listens on 127.0.0.1:8006 by default; override with:
#   MCP_HOST=0.0.0.0 MCP_PORT=9000 python ip_lookup_mcp_server.py
#   MCP_ALLOWED_HOSTS="your-domain.com,127.0.0.1:*"
#   MCP_ALLOWED_ORIGINS="https://your-domain.com"
```

Then point your MCP client at `http://127.0.0.1:8006/mcp`.
No API keys or accounts are ever required.



## 🗂️ Files

- `ip_lookup_mcp_server.py` — the MCP server (FastMCP, Streamable HTTP transport).
- `rate_limit.py` — lightweight per-IP sliding-window rate-limit middleware (60 req/min default).
- `requirements.txt` — `mcp`, `uvicorn`, `starlette`.
- `server.json` — official MCP Registry manifest (remote server entry, ready to publish with `mcp-publisher`).
- `smithery.yaml` / `glama.json` — directory listing metadata.

---

## 🇨🇳 中文使用说明

**一句话**：IP 归属地查询，国家/省份/城市/运营商/ASN 全中文输出，主备双通道高可用。

**在线直连地址（免费、无需 Key、开箱即用）**：`https://mcp.pianam.cn/ip-mcp/mcp`

在 MCP 客户端（Claude Desktop / Cursor / Cherry Studio / Cline 等）的配置里加入：

```json
{
  "mcpServers": {
    "ip-location": {
      "type": "http",
      "url": "https://mcp.pianam.cn/ip-mcp/mcp"
    }
  }
}
```

**工具**：

- `query_ip_location(ip)`：查 IPv4 归属地。传 IP 地址（如 `8.8.8.8`）；留空时尝试查询调用方自己的公网 IP。
- 返回国家/省份/城市、经纬度、时区、运营商、组织、AS 编号，中文输出。
- 主数据源 ip-api.com（免费、中文直出），故障自动切换 ipwho.is（含中国省份拼音中文化映射）。

**服务特性**：数据源全部为公开接口、无需注册/付费；服务端内存缓存、失败自动降级/切换备用通道；单 IP 限流 60 次/分钟。

**本地部署**：

```bash
git clone https://github.com/boy-373/ip-location-mcp.git
cd ip-location-mcp
pip install -r requirements.txt
python ip_lookup_mcp_server.py
# 默认监听 127.0.0.1:8006，可用环境变量 MCP_HOST / MCP_PORT / MCP_ALLOWED_HOSTS / MCP_ALLOWED_ORIGINS 覆盖
```

## 📄 License

[MIT](LICENSE) © 2026 boy-373

## Install via Smithery

One-click install for [Smithery](https://smithery.ai)-supported clients (Claude Desktop, Cursor, etc.):

[![Smithery](https://smithery.ai/badge/1561852680/ip-location-mcp)](https://smithery.ai/servers/1561852680/ip-location-mcp)

Or run:

```bash
npx -y @smithery/cli install 1561852680/ip-location-mcp --client claude
```

---

## 🔌 Use with Any AI Client — One-Click MCP Gateway

Want to call this MCP (and **22,000+** others) directly from your AI assistant? We host a free **MCP aggregation gateway**. Add this single URL to Cherry Studio, Claude Desktop, Cursor, Cline, or any MCP-compatible client:

```
https://mcp.pianam.cn/ai/mcp
```

Then just tell your AI what you want in plain language (e.g. "weather in Qingdao" / "trending searches on Weibo") — it automatically **searches → inspects → calls** the right MCP for you. No per-server setup.

**📖 3-step setup guide / 中文接入教程**: https://mcp.pianam.cn/ai-gateway

- 🔍 AI auto-discovers tools across 22,000+ MCP servers
- ✅ Servers health-checked weekly — alive ones ranked first
- 🌏 Chinese-language search optimized
- 🆓 Free, no API key required for the gateway
