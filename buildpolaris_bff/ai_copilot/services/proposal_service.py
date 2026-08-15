"""
Proposal half of the shared ActionApprovalGate (FR-8.6, NFR-EXT.3 - "no
feature builds its own copy"). Called by ai_copilot/api.py's
propose_agent_action() on Direction-2 calls from buildpolaris_ai (ARCH
§4.2), once per agent-drafted write.

AGENT_WRITABLE_DOCTYPES is the entire allow-list of what any agent may ever
target - deliberately small and explicit (FR-8.5's four named agents: RFI
drafting, submittal-review assistance, contract-clause flagging -> Change
Event, daily-log field extraction) plus Punch List Item, which shares the
same field-execution write-shape. Anything else is refused outright, not
"trusted because the caller says so".
"""
import json

import frappe
from frappe import _
from frappe.utils import now_datetime

from buildpolaris_bff.shared.security_log import log_security_event

AGENT_WRITABLE_DOCTYPES = {
	"RFI",
	"Submittal Package",
	"Change Event",
	"Daily Log",
	"Punch List Item",
}


def propose(
	agent_type: str,
	target_doctype: str,
	payload: dict,
	model_version: str | None = None,
	confidence: float | None = None,
	tool_trace_id: str | None = None,
	idempotency_key: str | None = None,
	proposed_by: str | None = None,
) -> dict:
	"""Create a pending-approval card. `proposed_by` is the ASSERTED user
	from the Scope Assertion the AI sidecar forwarded (ARCH §4.2's
	on-behalf-of pattern) - never the AI service account itself, which has
	no BuildPolaris Role at all."""
	proposed_by = proposed_by or frappe.session.user

	if target_doctype not in AGENT_WRITABLE_DOCTYPES:
		log_security_event("AGENT_WRITE_REFUSED_DOCTYPE", {
			"agent_type": agent_type, "target_doctype": target_doctype, "proposed_by": proposed_by,
		})
		frappe.throw(_("Agents may not write to {0}").format(target_doctype), frappe.PermissionError)

	if not tool_trace_id:
		frappe.throw(_("tool_trace_id is required for agent writes."), frappe.ValidationError)

	key = idempotency_key or tool_trace_id

	# Idempotent proposal: a retried propose() with the same key returns the
	# existing card rather than creating a duplicate (NFR-SCALE.6).
	existing = frappe.db.get_value("Agent Action Approval", {"idempotency_key": key}, "name")
	if existing:
		return frappe.get_doc("Agent Action Approval", existing).as_dict()

	project = payload.get("project")

	action = frappe.get_doc({
		"doctype": "Agent Action Approval",
		"agent_type": agent_type,
		"target_doctype": target_doctype,
		"project": project,
		"proposed_payload": json.dumps(payload, default=str),
		"model_version": model_version,
		"confidence": confidence,
		"tool_trace_id": tool_trace_id,
		"idempotency_key": key,
		"status": "Pending",
	}).insert(ignore_permissions=True)

	log_security_event("AGENT_WRITE_PROPOSED", {
		"action": action.name, "agent_type": agent_type, "target_doctype": target_doctype,
		"project": project, "proposed_by": proposed_by, "tool_trace_id": tool_trace_id,
	})
	return action.as_dict()


def list_pending(project: str | None = None, user: str | None = None) -> list:
	"""Feeds the 'pending approval' card list a PM/Accounting/Owner sees
	(UC-8.3). Project-scoped like every other list endpoint (NFR-SCALE.1)."""
	from buildpolaris_bff.shared.permissions import assert_project_permission, get_user_roles

	user = user or frappe.session.user
	filters = {"status": "Pending"}
	if project:
		assert_project_permission(project, ptype="read", user=user)
		filters["project"] = project
	elif "System Manager" not in get_user_roles(user) and "BuildPolaris Admin" not in get_user_roles(user):
		from buildpolaris_bff.shared.permissions import get_assigned_projects
		assigned = get_assigned_projects(user)
		if assigned:
			filters["project"] = ["in", assigned]

	return frappe.get_all(
		"Agent Action Approval",
		filters=filters,
		fields=["name", "agent_type", "target_doctype", "project", "model_version",
		        "confidence", "tool_trace_id", "creation"],
		order_by="creation asc",
	)
