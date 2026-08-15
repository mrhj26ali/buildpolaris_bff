"""
MCP tool host (FR-8.4, ARCH §4.4). buildpolaris_bff IS the MCP server here;
buildpolaris_ai's orchestrator is the client - the reverse of most MCP
setups, a deliberate ARCH decision so every tool call re-enters the same
Frappe permission stack every other request goes through, instead of the AI
sidecar needing its own copy of BuildPolaris's authorization logic.

Transport note: this exposes the tool-list/tool-call contract as two plain
`@frappe.whitelist()` JSON endpoints rather than a separate ASGI
Streamable-HTTP process, because Frappe itself is WSGI-hosted and standing
up a second always-on process just for transport framing is unwarranted
complexity for a single internal consumer (buildpolaris_ai) that already
speaks plain HTTP+JSON. The tool-call *contract* (name, arguments, result)
matches MCP's shape exactly; only the wire framing is simplified.

Authorization is two-layered (ARCH §4.2):
  1. Transport identity: the caller must be an authenticated, non-Guest
     Frappe session - in practice the low-privilege 'BuildPolaris AI
     Service' account (install.py), which itself holds NO BuildPolaris
     Role and can read/write nothing on its own.
  2. Actual authorization: the Scope Assertion's ASSERTED user's own
     Role/Project permissions, re-verified on every single tool call - the
     transport identity never substitutes for it (NFR-SEC.1/SEC.8).
"""
import frappe

from buildpolaris_bff.ai_copilot.mcp.tool_registry import get_tool, list_tools as _list_tools
from buildpolaris_bff.shared.exceptions import BuildPolarisError, PermissionDeniedError
from buildpolaris_bff.shared.scope_assertion import verify_scope_assertion
from buildpolaris_bff.shared.security_log import log_structured


@frappe.whitelist()
def list_tools():
	_assert_service_caller()
	return {"tools": _list_tools()}


@frappe.whitelist()
def call_tool(tool_name: str, arguments: dict | None = None, scope_assertion: str = "", trace_id: str | None = None):
	_assert_service_caller()

	if isinstance(arguments, str):
		arguments = frappe.parse_json(arguments)
	arguments = arguments or {}

	claims = verify_scope_assertion(scope_assertion)
	asserted_user = claims["user"]
	asserted_project = claims.get("project")

	fn = get_tool(tool_name)
	if not fn:
		return {"ok": False, "error": f"Unknown tool: {tool_name}"}

	try:
		result = fn(arguments, asserted_user=asserted_user, asserted_project=asserted_project)
		log_structured("MCP_TOOL_CALL_OK", {
			"tool": tool_name, "asserted_user": asserted_user, "trace_id": trace_id,
		})
		return {"ok": True, "result": result}
	except BuildPolarisError as exc:
		log_structured("MCP_TOOL_CALL_ERROR", {
			"tool": tool_name, "asserted_user": asserted_user, "error": exc.message, "trace_id": trace_id,
		})
		return {"ok": False, "error": exc.message}
	except frappe.PermissionError as exc:
		return {"ok": False, "error": str(exc) or "Permission denied."}


def _assert_service_caller():
	"""Reject anonymous/Guest callers outright. Does NOT grant any data
	access itself - see module docstring's two-layer model."""
	if frappe.session.user == "Guest":
		raise PermissionDeniedError("MCP tool calls require an authenticated service session.")
