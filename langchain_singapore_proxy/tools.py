"""LangChain tools that browse the web from a Singapore mobile IP."""

from typing import List, Literal, Optional, Type

from langchain_core.tools import BaseTool, BaseToolkit
from pydantic import BaseModel, ConfigDict, Field

from .client import SingaporeProxyClient

__all__ = [
    "SingaporeFetchURL",
    "SingaporeGoogleSearch",
    "SingaporeRotateIP",
    "SingaporeProxyStatus",
    "SingaporeProxyToolkit",
]


class _FetchInput(BaseModel):
    url: str = Field(description="The full http(s) URL to fetch.")
    format: Literal["markdown", "text", "html"] = Field(
        default="markdown",
        description='"markdown" (clean main content), "text", or "html".',
    )


class _SearchInput(BaseModel):
    query: str = Field(description="What to search Google for.")
    num: int = Field(default=10, description="How many organic results to return.")


class _NoInput(BaseModel):
    pass


class _SingaporeProxyTool(BaseTool):
    """Shared plumbing: every tool holds a client, built from SMP_API_KEY if not given."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    client: Optional[SingaporeProxyClient] = None

    def _get_client(self) -> SingaporeProxyClient:
        if self.client is None:
            self.client = SingaporeProxyClient()
        return self.client


class SingaporeFetchURL(_SingaporeProxyTool):
    name: str = "singapore_fetch_url"
    description: str = (
        "Fetch a web page as a visitor on a Singapore mobile network (Singtel or M1) "
        "would see it. Use for Singapore prices, stock, geo-locked pages and local "
        "versions of sites. Returns the page as markdown by default."
    )
    args_schema: Type[BaseModel] = _FetchInput

    def _run(self, url: str, format: str = "markdown", run_manager=None) -> str:
        return self._get_client().fetch_url(url, format)


class SingaporeGoogleSearch(_SingaporeProxyTool):
    name: str = "singapore_google_search"
    description: str = (
        "Search Google as a user in Singapore (gl=sg, from a Singapore mobile IP) "
        "and get the organic results. Use for local SERPs, SEO checks and finding "
        "Singapore businesses or pages."
    )
    args_schema: Type[BaseModel] = _SearchInput

    def _run(self, query: str, num: int = 10, run_manager=None) -> str:
        return self._get_client().search_google(query, num)


class SingaporeRotateIP(_SingaporeProxyTool):
    name: str = "singapore_rotate_ip"
    description: str = (
        "Get a fresh Singapore mobile IP. Use when a site blocks or rate-limits "
        "the current one."
    )
    args_schema: Type[BaseModel] = _NoInput

    def _run(self, run_manager=None) -> str:
        return self._get_client().rotate_ip()


class SingaporeProxyStatus(_SingaporeProxyTool):
    name: str = "singapore_proxy_status"
    description: str = "Show the current Singapore exit IP, carrier and remaining quota."
    args_schema: Type[BaseModel] = _NoInput

    def _run(self, run_manager=None) -> str:
        return self._get_client().status()


class SingaporeProxyToolkit(BaseToolkit):
    """All four tools sharing one client (and one MCP session).

    Example::

        from langchain_singapore_proxy import SingaporeProxyToolkit
        tools = SingaporeProxyToolkit().get_tools()   # reads SMP_API_KEY
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    client: Optional[SingaporeProxyClient] = None

    def get_tools(self) -> List[BaseTool]:
        client = self.client or SingaporeProxyClient()
        return [
            SingaporeFetchURL(client=client),
            SingaporeGoogleSearch(client=client),
            SingaporeRotateIP(client=client),
            SingaporeProxyStatus(client=client),
        ]
