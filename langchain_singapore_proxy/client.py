"""A small client for the hosted Singapore Proxy MCP server.

The server speaks MCP over Streamable HTTP. A call is three requests: an
``initialize`` that returns an ``mcp-session-id`` header, an
``notifications/initialized`` notification, and then ``tools/call`` with that
session id. Replies come back as either JSON or a one-event SSE stream, so both
are parsed. The session is reused until the server forgets it (HTTP 404), at
which point the client starts a new one and retries once.
"""

import json
import os
from typing import Any, Dict, Optional

import httpx

DEFAULT_ENDPOINT = "https://mcp.singaporemobileproxy.com/mcp"
PROTOCOL_VERSION = "2025-06-18"
TRIAL_URL = (
    "https://singaporemobileproxy.com/client/mcp"
    "?utm_source=pypi&utm_medium=package&utm_campaign=langchain_singapore_proxy"
)

__all__ = ["SingaporeProxyClient", "SingaporeProxyError", "DEFAULT_ENDPOINT"]


class SingaporeProxyError(Exception):
    """The server refused the call or the tool reported an error."""


def _parse_body(response: httpx.Response) -> Dict[str, Any]:
    ctype = response.headers.get("content-type", "")
    text = response.text
    if "text/event-stream" in ctype:
        data_lines = [
            line[len("data:"):].strip()
            for line in text.splitlines()
            if line.startswith("data:")
        ]
        if not data_lines:
            raise SingaporeProxyError("empty event stream from server")
        # One JSON-RPC message per event; the reply is the last one.
        return json.loads(data_lines[-1])
    return json.loads(text)


class SingaporeProxyClient:
    """Call the Singapore Proxy MCP tools over plain HTTP.

    Args:
        api_key: Your key from singaporemobileproxy.com/client/mcp. Falls back
            to the ``SMP_API_KEY`` environment variable.
        endpoint: The MCP endpoint. You shouldn't need to change it.
        timeout: Seconds per HTTP request. Fetches go through a 4G modem, so
            keep this generous.
        http_client: Optional ``httpx.Client``, mainly for tests.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        endpoint: str = DEFAULT_ENDPOINT,
        timeout: float = 120.0,
        http_client: Optional[httpx.Client] = None,
    ) -> None:
        key = api_key or os.environ.get("SMP_API_KEY")
        if not key:
            raise SingaporeProxyError(
                "No API key. Pass api_key= or set SMP_API_KEY. "
                f"Get one (free 24-hour trial) at {TRIAL_URL}"
            )
        self.api_key = key
        self.endpoint = endpoint
        self._http = http_client or httpx.Client(timeout=timeout)
        self._session_id: Optional[str] = None
        self._next_id = 0

    def _headers(self) -> Dict[str, str]:
        headers = {
            "content-type": "application/json",
            "accept": "application/json, text/event-stream",
            "x-api-key": self.api_key,
        }
        if self._session_id:
            headers["mcp-session-id"] = self._session_id
            headers["mcp-protocol-version"] = PROTOCOL_VERSION
        return headers

    def _id(self) -> int:
        self._next_id += 1
        return self._next_id

    def _open_session(self) -> None:
        self._session_id = None
        resp = self._http.post(
            self.endpoint,
            headers=self._headers(),
            json={
                "jsonrpc": "2.0",
                "id": self._id(),
                "method": "initialize",
                "params": {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {"name": "langchain-singapore-proxy", "version": "0.1.0"},
                },
            },
        )
        resp.raise_for_status()
        reply = _parse_body(resp)
        if "error" in reply:
            raise SingaporeProxyError(reply["error"].get("message", str(reply["error"])))
        self._session_id = resp.headers.get("mcp-session-id")
        note = self._http.post(
            self.endpoint,
            headers=self._headers(),
            json={"jsonrpc": "2.0", "method": "notifications/initialized"},
        )
        note.raise_for_status()

    def call_tool(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> str:
        """Run one MCP tool and return its text output.

        Raises:
            SingaporeProxyError: bad key, expired trial, or the tool failed.
        """
        if self._session_id is None:
            self._open_session()
        payload = {
            "jsonrpc": "2.0",
            "id": self._id(),
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments or {}},
        }
        resp = self._http.post(self.endpoint, headers=self._headers(), json=payload)
        if resp.status_code == 404:
            # Session expired on the server. Start over once.
            self._open_session()
            resp = self._http.post(self.endpoint, headers=self._headers(), json=payload)
        resp.raise_for_status()
        reply = _parse_body(resp)
        if "error" in reply:
            raise SingaporeProxyError(reply["error"].get("message", str(reply["error"])))
        result = reply.get("result", {})
        text = "\n".join(
            part.get("text", "")
            for part in result.get("content", [])
            if part.get("type") == "text"
        )
        if result.get("isError"):
            raise SingaporeProxyError(text or f"{name} failed")
        return text

    def fetch_url(self, url: str, format: str = "markdown") -> str:
        """Fetch a page through a Singapore mobile IP."""
        return self.call_tool("fetch_url", {"url": url, "format": format})

    def search_google(self, query: str, num: int = 10) -> str:
        """Run a Singapore-localized Google search (gl=sg)."""
        return self.call_tool("search_google", {"query": query, "num": num})

    def rotate_ip(self) -> str:
        """Ask for a fresh Singapore mobile IP."""
        return self.call_tool("rotate_ip")

    def status(self) -> str:
        """Current exit IP, carrier and remaining quota."""
        return self.call_tool("my_proxy_status")

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "SingaporeProxyClient":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()
