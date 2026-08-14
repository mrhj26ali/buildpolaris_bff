import frappe
from frappe.utils import today


def get_dashboard(project: str) -> dict:
    """
    FR-4.7: Unified dashboard aggregating all communications doctypes.
    Defensive: handles missing doctypes gracefully.
    """
    def safe_count(doctype, filters):
        try:
            if frappe.db.exists("DocType", doctype):
                return frappe.db.count(doctype, filters)
        except Exception:
            pass
        return 0

    rfi_count = safe_count("RFI", {"project": project})
    rfi_overdue = safe_count("RFI", {
        "project": project,
        "status": ["!=", "Closed"],
        "date_required": ["<", today()],
    })

    submittal_count = safe_count("Submittal Package", {"project": project})
    transmittal_count = safe_count("Transmittal", {"project": project})

    action_item_count = safe_count("Action Item", {"project": project})
    action_item_overdue = safe_count("Action Item", {
        "project": project,
        "status": ["!=", "Closed"],
        "due_date": ["<", today()],
    })

    escalation_count = safe_count("Escalation Log", {"project": project})

    return {
        "project": project,
        "rfi_count": rfi_count,
        "rfi_overdue": rfi_overdue,
        "submittal_count": submittal_count,
        "transmittal_count": transmittal_count,
        "action_item_count": action_item_count,
        "action_item_overdue": action_item_overdue,
        "escalation_count": escalation_count,
        "total_overdue": rfi_overdue + action_item_overdue,
    }
