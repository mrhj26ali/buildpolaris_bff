"""
NFR-AUD.2: every agent-executed mutation logs acting_agent_id, model_version,
confidence, tool_trace_id - so it's legally distinguishable from a human
edit and reconstructable from the log alone, without re-running the agent.
A human edit simply never calls record_mutation() - Commitment, RFI, etc.
carry no AI-specific columns themselves (ERD §3.6 design note).
"""
import frappe
from frappe.utils import now_datetime


def record_mutation(target_doctype: str, target_name: str, acting_agent_id: str,
                     model_version: str | None, confidence: float | None,
                     tool_trace_id: str | None, approval_ref: str | None = None) -> str:
	doc = frappe.get_doc({
		"doctype": "Agent Mutation Log",
		"target_doctype": target_doctype,
		"target_name": target_name,
		"acting_agent_id": acting_agent_id,
		"model_version": model_version,
		"confidence": confidence,
		"tool_trace_id": tool_trace_id,
		"approval_ref": approval_ref,
		"applied_at": now_datetime(),
	}).insert(ignore_permissions=True)
	return doc.name


def get_mutation_history(doctype: str, name: str, user: str | None = None) -> list:
	"""Read-side of NFR-AUD.2 - lets a UI show 'this record was last changed
	by RFIDraftingAgent under approval AGT-0042' alongside native Version
	history (FR-1.6)."""
	if not frappe.has_permission(doctype, "read", name, user=user):
		frappe.throw("Forbidden", frappe.PermissionError)

	return frappe.get_all(
		"Agent Mutation Log",
		filters={"target_doctype": doctype, "target_name": name},
		fields=["name", "acting_agent_id", "model_version", "confidence",
		        "tool_trace_id", "approval_ref", "applied_at"],
		order_by="applied_at desc",
	)
