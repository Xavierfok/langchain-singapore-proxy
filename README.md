# langchain-singapore-proxy

[![tests](https://github.com/Xavierfok/langchain-singapore-proxy/actions/workflows/tests.yml/badge.svg)](https://github.com/Xavierfok/langchain-singapore-proxy/actions/workflows/tests.yml)

LangChain tools that let an agent browse the web **from a real Singapore mobile IP**: fetch a page the way a phone on Singtel or M1 would see it, run a Singapore-localized Google search, and rotate to a fresh IP when a site pushes back.

Agents can't set a proxy themselves, so anything geo-locked, priced per country or ranked per location comes back as the US or EU version. These tools fix that for Singapore.

They call the hosted [Singapore Proxy MCP server](https://github.com/Xavierfok/singapore-proxy-mcp) (`https://mcp.singaporemobileproxy.com/mcp`) over plain HTTP. There's nothing to run locally.

## Install

```bash
pip install langchain-singapore-proxy
```

## Get a key

Sign up at **[singaporemobileproxy.com/client/mcp](https://singaporemobileproxy.com/client/mcp?utm_source=github&utm_medium=repo&utm_campaign=langchain_singapore_proxy)**. The key comes with a free 24-hour trial capped at 10 GB, one per email. After that the same key keeps working on a paid plan: $4 for a day, $13 for a week, or monthly from $40 ([plans](https://singaporemobileproxy.com/client/plans?days=1&utm_source=github&utm_medium=repo&utm_campaign=langchain_singapore_proxy)).

```bash
export SMP_API_KEY=sk_your_key_here
```

## Use

```python
from langchain_singapore_proxy import SingaporeProxyToolkit

tools = SingaporeProxyToolkit().get_tools()   # reads SMP_API_KEY
```

Hand `tools` to any LangChain or LangGraph agent, for example:

```python
from langchain.agents import create_agent

agent = create_agent("anthropic:claude-sonnet-5", tools=tools)
agent.invoke({"messages": [{"role": "user", "content": "Search Google in Singapore for the best laksa and summarise the top three results."}]})
```

Or call a tool directly:

```python
from langchain_singapore_proxy import SingaporeFetchURL, SingaporeGoogleSearch

SingaporeFetchURL().invoke({"url": "https://www.lazada.sg/", "format": "markdown"})
SingaporeGoogleSearch().invoke({"query": "best chicken rice", "num": 5})
```

Without LangChain, the client works on its own:

```python
from langchain_singapore_proxy import SingaporeProxyClient

with SingaporeProxyClient() as sg:
    print(sg.status())          # exit IP, carrier, remaining quota
    print(sg.search_google("coworking space tanjong pagar"))
```

## Tools

| Tool | Server tool | What it does |
|------|-------------|--------------|
| `singapore_fetch_url(url, format)` | `fetch_url` | Fetch a page through a Singapore mobile IP. `format` is `markdown` (default), `text` or `html`. |
| `singapore_google_search(query, num)` | `search_google` | Google organic results with `gl=sg`, from a Singapore IP. |
| `singapore_rotate_ip()` | `rotate_ip` | Ask for a fresh Singapore mobile IP. |
| `singapore_proxy_status()` | `my_proxy_status` | Current exit IP, carrier and remaining quota. |

Errors from the server (bad key, trial used up, a page that won't load) raise `SingaporeProxyError` with the server's message, so the agent sees what went wrong.

## Notes

- Each key sits on a dedicated 4G line on the Singtel or M1 network. There's no StarHub stock right now.
- The toolkit's four tools share one client and one MCP session. The client opens a new session by itself if the server drops the old one.
- Fetches go through a modem, so the default timeout is 120 s.
- The tests mock the HTTP layer. The tool names and arguments were checked against the live server's `tools/list`.

## Other ways to use the same key

- MCP clients (Claude, Cursor, Cline): [singapore-proxy-mcp](https://github.com/Xavierfok/singapore-proxy-mcp)
- Plain Python scrapers: [proxy-rotator](https://github.com/Xavierfok/proxy-rotator)
- Scrapy: [scrapy-sg-proxy](https://github.com/Xavierfok/scrapy-sg-proxy)
- n8n: [n8n-nodes-singapore-proxy](https://github.com/Xavierfok/n8n-nodes-singapore-proxy)

## License

MIT. Not affiliated with LangChain, Google or any carrier.
