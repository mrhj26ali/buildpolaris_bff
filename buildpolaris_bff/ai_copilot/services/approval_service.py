"""
Approval/rejection half of the shared ActionApprovalGate (FR-8.6). The
decision-making surface a PM/Accounting/Owner acts on from the "pending
approval" card (UC-8.3). Execution itself lives in execution_service.py -
kept separate so "who decided" and "what actually got written" are each one
file's concern, matching ARCH §3.1's layering discipline.
"""
import frappe
from frappe import _
from frappe.utils import now_datetime

from buildpolaris_bff.shared.permissions import assert_project_permission, assert_role
from buildpolaris_bff.shared.security_log import log_security_event
from buildpolaris_bff.ai_copilot.services import execution_service, audit_service

APPROVER_ROLES = (
	"BuildPolaris Project Manager",
	"BuildPolaris Accounting",
	"BuildPolaris Owner",
	"BuildPolaris Admin",
)


def approve(action_name: str, approver: str | None = None) -> dict:
	"""Approve and execute, idempotently. A retried/duplicated approval
	click never double-applies (NFR-SCALE.6) - if already Approved, returns
	the prior result without touching the target record again."""
	approver = approver or frappe.session.user
	action = frappe.get_doc("Agent Action Approval", action_name)

	assert_role(*APPROVER_ROLES, user=approver)
	if action.project:
		assert_project_permission(action.project, ptype="write", user=approver)

	if action.status == "Approved":
		return {"status": "already_approved", "action": action.name, "target": action.target_name}
	if action.status == "Rejected":
		frappe.throw(_("This action was rejected and cannot be approved."), frappe.ValidationError)
	if action.status != "Pending":
		frappe.throw(_("Action is not pending."), frappe.ValidationError)

	target_name = execution_service.execute(action.target_doctype, action.proposed_payload, executing_user=approver)

	action.status = "Approved"
	action.approver = approver
	action.decided_at = now_datetime()
	action.target_name = target_name
	action.save(ignore_permissions=True)

	audit_service.record_mutation(
		target_doctype=action.target_doctype,
		target_name=target_name,
		acting_agent_id=action.agent_type,
		model_version=action.model_version,
		confidence=action.confidence,
		tool_trace_id=action.tool_trace_id,
		approval_ref=action.name,
	)

	log_security_event("AGENT_WRITE_APPROVED", {
		"action": action.name, "agent_type": action.agent_type, "target": target_name,
		"approver": approver, "tool_trace_id": action.tool_trace_id,
	})
	return {"status": "approved", "action": action.name, "target": target_name}


def reject(action_name: str, reason: str | None = None, approver: str | None = None) -> dict:
	"""Discard a proposed action. Nothing is ever written (FR-8.6: 'never a
	change that has already taken effect' until approval)."""
	approver = approver or frappe.session.user
	action = frappe.get_doc("Agent Action Approval", action_name)

	assert_role(*APPROVER_ROLES, user=approver)
	if action.project:
		assert_project_permission(action.project, ptype="write", user=approver)

	if action.status != "Pending":
		frappe.throw(_("Only a pending action can be rejected (current status: {0}).").format(action.status), frappe.ValidationError)

	action.status = "Rejected"
	action.approver = approver
	action.decided_at = now_datetime()
	action.decision_reason = reason
	action.save(ignore_permissions=True)

	log_security_event("AGENT_WRITE_REJECTED", {
		"action": action.name, "approver": approver, "reason": reason,
	})
	return {"status": "rejected", "action": action.name}
