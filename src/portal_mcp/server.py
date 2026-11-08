"""FastMCP stdio server."""
from mcp.server.fastmcp import FastMCP

from . import tools


def build() -> FastMCP:
    mcp = FastMCP("ispace")
    for fn in tools.READ + tools.WRITE:
        mcp.tool()(fn)
    return mcp


def run() -> None:
    build().run(transport="stdio")
