"""MCP (Model Context Protocol) layer for Nicx."""

from nicx.mcp.client import MCPClient
from nicx.mcp.protocol import MCPError, MCPNotification, MCPRequest, MCPResponse
from nicx.mcp.server import MCPServer
from nicx.mcp.transport import (
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
