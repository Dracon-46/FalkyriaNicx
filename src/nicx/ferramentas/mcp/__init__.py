"""MCP (Model Context Protocol) layer for Nicx."""

from nicx.ferramentas.mcp.client import MCPClient
from nicx.ferramentas.mcp.protocol import (
    MCPError,
    MCPNotification,
    MCPRequest,
    MCPResponse,
)
from nicx.ferramentas.mcp.server import MCPServer
from nicx.ferramentas.mcp.transport import (
    InProcessTransport,
    MCPTransport,
    SSETransport,
    StdioTransport,
    StreamableHTTPTransport,
)

__all__ = [
    "MCPClient",
    "MCPError",
    "MCPNotification",
    "MCPRequest",
    "MCPResponse",
    "MCPServer",
    "MCPTransport",
    "InProcessTransport",
    "SSETransport",
    "StdioTransport",
    "StreamableHTTPTransport",
]
