"""
Typed contract for MCP tool invocation (FR-8.4, ARCH §4.4). Every MCP tool
in ai_copilot/mcp/tools/*.py wraps exactly one services/ function and speaks
this shape on the wire.
"""
from dataclasses import dataclass


@dataclass
class MCPToolCallRequest:
	tool_name: str
	arguments: dict
	scope_assertion: str
	trace_id: str


@dataclass
class MCPToolCallResult:
	ok: bool
	result: dict | None = None
	error: str | None = None
