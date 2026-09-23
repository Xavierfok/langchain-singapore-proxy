import json

import httpx
import pytest

from langchain_singapore_proxy import (
    SingaporeFetchURL,
    SingaporeProxyClient,
    SingaporeProxyError,
    SingaporeProxyToolkit,
)


def sse(message):
    return httpx.Response(
        200,
        headers={"content-type": "text/event-stream"},
        text="event: message\ndata: " + json.dumps(message) + "\n\n",
    )


class FakeServer:
    """Mimics the hosted server: initialize -> session id, then tools/call."""

    def __init__(self, tool_reply=None, expire_first_call=False):
        self.calls = []
        self.sessions = 0
        self.tool_reply = tool_reply or {"content": [{"type": "text", "text": "ok"}]}
        self.expire_first_call = expire_first_call

    def __call__(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        self.calls.append((body.get("method"), dict(request.headers), body))
        method = body.get("method")
        if method == "initialize":
            self.sessions += 1
            resp = sse({"jsonrpc": "2.0", "id": body["id"], "result": {"protocolVersion": "2025-06-18"}})
            resp.headers["mcp-session-id"] = f"s{self.sessions}"
            return resp
        if method == "notifications/initialized":
            return httpx.Response(202)
        if method == "tools/call":
            if self.expire_first_call and request.headers.get("mcp-session-id") == "s1":
                return httpx.Response(404)
            return sse({"jsonrpc": "2.0", "id": body["id"], "result": self.tool_reply})
        return httpx.Response(400)


def make_client(server, key="sk_test"):
    return SingaporeProxyClient(api_key=key, http_client=httpx.Client(transport=httpx.MockTransport(server)))


def test_handshake_then_call_sends_key_and_session():
    server = FakeServer()
    client = make_client(server)
    assert client.fetch_url("https://example.com") == "ok"
    methods = [c[0] for c in server.calls]
    assert methods == ["initialize", "notifications/initialized", "tools/call"]
    _, headers, body = server.calls[-1]
    assert headers["x-api-key"] == "sk_test"
    assert headers["mcp-session-id"] == "s1"
    assert body["params"] == {"name": "fetch_url", "arguments": {"url": "https://example.com", "format": "markdown"}}


def test_session_is_reused():
    server = FakeServer()
    client = make_client(server)
    client.status()
    client.rotate_ip()
    assert [c[0] for c in server.calls].count("initialize") == 1
    assert server.calls[-1][2]["params"]["name"] == "rotate_ip"


def test_expired_session_reinitializes_once():
    server = FakeServer(expire_first_call=True)
    client = make_client(server)
    assert client.search_google("hawker centre", num=5) == "ok"
    assert server.sessions == 2
    assert server.calls[-1][2]["params"]["arguments"] == {"query": "hawker centre", "num": 5}


def test_tool_error_raises_with_server_message():
    server = FakeServer(
        tool_reply={
            "content": [{"type": "text", "text": "Error executing tool my_proxy_status: API key is invalid."}],
            "isError": True,
        }
    )
    client = make_client(server)
    with pytest.raises(SingaporeProxyError, match="API key is invalid"):
        client.status()


def test_plain_json_reply_is_parsed():
    def handler(request):
        body = json.loads(request.content)
        if body.get("method") == "initialize":
            return httpx.Response(200, json={"jsonrpc": "2.0", "id": body["id"], "result": {}}, headers={"mcp-session-id": "j"})
        if body.get("method") == "notifications/initialized":
            return httpx.Response(202)
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": body["id"], "result": {"content": [{"type": "text", "text": "json ok"}]}})

    client = make_client(handler)
    assert client.status() == "json ok"


def test_missing_key_points_to_trial(monkeypatch):
    monkeypatch.delenv("SMP_API_KEY", raising=False)
    with pytest.raises(SingaporeProxyError, match="client/mcp"):
        SingaporeProxyClient()


def test_env_key_is_used(monkeypatch):
    monkeypatch.setenv("SMP_API_KEY", "sk_env")
    assert SingaporeProxyClient().api_key == "sk_env"


def test_langchain_tool_invoke():
    server = FakeServer(tool_reply={"content": [{"type": "text", "text": "# Page"}]})
    tool = SingaporeFetchURL(client=make_client(server))
    assert tool.invoke({"url": "https://example.com", "format": "text"}) == "# Page"
    assert server.calls[-1][2]["params"]["arguments"]["format"] == "text"


def test_toolkit_tools_share_one_session():
    server = FakeServer()
    tools = SingaporeProxyToolkit(client=make_client(server)).get_tools()
    assert [t.name for t in tools] == [
        "singapore_fetch_url",
        "singapore_google_search",
        "singapore_rotate_ip",
        "singapore_proxy_status",
    ]
    tools[3].invoke({})
    tools[1].invoke({"query": "bubble tea"})
    assert [c[0] for c in server.calls].count("initialize") == 1
