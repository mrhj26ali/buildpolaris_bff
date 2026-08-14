"""
ActionApprovalGate - the ONE mechanism every agent uses to write (FR-8.6,
NFR-EXT.3, UC-8.5).

- Read actions may auto-execute; writes may NOT. Every write is proposed,
  rendered as a pending-approval card, and executed only after a human
  approves, exactly once (idempotent on tool_trace_id, NFR-SCALE.6).
- Full provenance captured at proposal time: agent_type, payload,
  model_version, confidence, tool_trace_id (NFR-AUD.2). Approver decision
  captured at resolution time.
- Execution runs through the normal service/doctype path with the CURRENT
  session user's permissions enforced (NFR-SEC.8) - the gate never escalates.
"""
import json
import frappe
from frappe import _
from frappe.utils import now_datetime
from buildpolaris_bff.shared.security_log import log_security_event

# Only these doctypes may ever be written by an agent. Everything else is
# refused outright - an agent cannot propose arbitrary writes.
AGENT_WRITABLE_DOCTYPES = {
    "RFI", "Daily Log", "Punch List Item", "Change Event",
}


def propose(
    agent_type: str,
    target_doctype: str,
    payload: dict,
    model_version: str = None,
    confidence: float = None,
    tool_trace_id: str = None,
) -> str:
    """Create a pending-approval card. Called by the AI sidecar via BFF."""
    if target_doctype not in AGENT_WRITABLE_DOCTYPES:
        log_security_event("AGENT_WRITE_REFUSED_DOCTYPE", {
            "agent_type": agent_type, "target_doctype": target_doctype,
        })
        frappe.throw(_("Agents may not write to {0}").format(target_doctype), frappe.PermissionError)

    if not tool_trace_id:
        frappe.throw(_("tool_trace_id is required for agent writes"), frappe.ValidationError)

    # Idempotent proposal: same tool_trace_id returns the existing card.
    existing = frappe.db.get_value("BP Agent Action", {"tool_trace_id": tool_trace_id}, "name")
    if existing:
        return existing

    action = frappe.get_doc({
        "doctype": "BP Agent Action",
        "agent_type": agent_type,
        "target_doctype": target_doctype,
        "payload": json.dumps(payload, default=str),
        "model_version": model_version,
        "confidence": confidence,
        "tool_trace_id": tool_trace_id,
        "status": "Pending",
        "proposed_by": frappe.session.user,
        "proposed_at": now_datetime(),
    }).insert(ignore_permissions=True)
    return action.name


def reject(action_id: str, reason: str = None) -> dict:
    """Discard a proposed action. Nothing executes."""
    action = frappe.get_doc("BP Agent Action", action_id)
    if action.status != "Pending":
        frappe.throw(_("Only pending actions can be rejected"), frappe.ValidationError)
    action.status = "Rejected"
    action.approver = frappe.session.user
    action.decision_reason = reason
    action.resolved_at = now_datetime()
    action.save(ignore_permissions=True)
    log_security_event("AGENT_WRITE_REJECTED", {"action": action_id, "by": frappe.session.user})
    return {"status": "rejected", "action": action_id}


def approve(action_id: str) -> dict:
    """
    Approve and execute idempotently. A retried/duplicated approval never
    double-applies (NFR-SCALE.6) - if already Executed, returns the prior result.
    """
    action = frappe.get_doc("BP Agent Action", action_id)

    if action.status == "Executed":
        return {"status": "already_executed", "action": action_id, "target": action.target_name}
    if action.status == "Rejected":
        frappe.throw(_("This action was rejected and cannot be executed"), frappe.ValidationError)
    if action.status != "Pending":
        frappe.throw(_("Action is not pending"), frappe.ValidationError)

    payload = json.loads(action.payload) if isinstance(action.payload, str) else (action.payload or {})
    target = _execute(action.target_doctype, payload)

    action.status = "Executed"
    action.target_name = target
    action.approver = frappe.session.user
    action.resolved_at = now_datetime()
    action.executed_at = now_datetime()
    action.save(ignore_permissions=True)
    log_security_event("AGENT_WRITE_EXECUTED", {
        "action": action_id, "agent_type": action.agent_type,
        "model_version": action.model_version, "target": target,
        "tool_trace_id": action.tool_trace_id, "by": frappe.session.user,
    })
    return {"status": "executed", "action": action_id, "target": target}


def _execute(doctype: str, payload: dict) -> str:
    """
    Apply the approved payload through the normal doctype path, with the
    current session user's permissions enforced (no ignore_permissions on
    the business write). Returns the created/updated document name.
    """
    if doctype not in AGENT_WRITABLE_DOCTYPES:
        frappe.throw(_("Agents may not write to {0}").format(doctype), frappe.PermissionError)

    name = payload.get("name")
    if name and frappe.db.exists(doctype, name):
        doc = frappe.get_doc(doctype, name)
        # Permission check enforced by framework (NFR-SEC.1/SEC.8).
        doc.update({k: v for k, v in payload.items() if k != "name"})
        doc.save()  # raises PermissionError if the approver lacks write access
        return doc.name

    doc = frappe.get_doc({"doctype": doctype, **payload})
    doc.insert()  # raises PermissionError if the approver lacks create access
    return doc.name
