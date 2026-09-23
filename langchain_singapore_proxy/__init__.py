"""LangChain tools for Singapore Mobile Proxy: fetch pages and search Google from a Singapore mobile IP."""

from .client import DEFAULT_ENDPOINT, SingaporeProxyClient, SingaporeProxyError
from .tools import (
    SingaporeFetchURL,
    SingaporeGoogleSearch,
    SingaporeProxyStatus,
    SingaporeProxyToolkit,
    SingaporeRotateIP,
)

__version__ = "0.1.0"

__all__ = [
    "DEFAULT_ENDPOINT",
    "SingaporeProxyClient",
    "SingaporeProxyError",
    "SingaporeFetchURL",
    "SingaporeGoogleSearch",
    "SingaporeRotateIP",
    "SingaporeProxyStatus",
    "SingaporeProxyToolkit",
]
