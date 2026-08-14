"""
BuildPolaris scheduled jobs (wired in hooks.scheduler_events).
Job failures MUST surface to an operator-visible channel (NFR-OBS.2).
"""
import frappe
from frappe.utils import today


def escalate_overdue_communications():
    """
    UC-4.5 / FR-4.5: escalate overdue RFIs and Action Items via the existing
    notification engine. Runs daily.
    """
    overdue_rfis = frappe.get_all(
        "RFI", filters={"status": ["not in", ["Closed", "Answered"]], "requested_reply_date": ["<", today()]},
        fields=["name", "assigned_to", "project"], ignore_permissions=True,
    )
    for rfi in overdue_rfis:
        _escalate("RFI", rfi.name)

    overdue_actions = frappe.get_all(
        "Action Item", filters={"status": ["!=", "Closed"], "due_date": ["<", today()]},
        fields=["name", "assigned_to", "project"], ignore_permissions=True,
    )
    for item in overdue_actions:
        _escalate("Action Item", item.name)
    frappe.db.commit()


def _escalate(reference_doctype, reference_name):
    already = frappe.db.exists("Escalation Log", {
        "reference_doctype": reference_doctype, "reference_name": reference_name,
    })
    if already:
        return
    try:
        frappe.get_doc({
            "doctype": "Escalation Log",
            "reference_doctype": reference_doctype,
            "reference_name": reference_name,
            "escalation_tier": 1,
        }).insert(ignore_permissions=True)
    except Exception:
        frappe.log_error(
            title=f"BuildPolaris escalation failed: {reference_doctype} {reference_name}",
            message=frappe.get_traceback(),
        )


def closeout_lookahead_digest():
    """Phase 6 placeholder: closeout look-ahead digests to PM/Owner."""
    pass


def schedule_health_check():
    """Hourly placeholder: lightweight schedule health for active projects."""
    pass
