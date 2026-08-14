import frappe
from frappe.utils import now_datetime
from frappe.utils import now_datetime

def create_transmittal(project: str, purpose: str, transmission_method: str,
                       content_types: str = None, recipients: list = None):
    """FR-8: Create a new Transmittal with recipients."""
    transmittal = frappe.get_doc({
        "doctype": "Transmittal",
        "project": project,
        "purpose": purpose,
        "transmission_method": transmission_method,
        "content_types": content_types,
        "recipients": [
            {"user": r, "acknowledged": 0} for r in (recipients or [])
        ],
    }).insert(ignore_permissions=True)
    return transmittal.name



def acknowledge_transmittal(transmittal_id: str, recipient_user: str):
    """FR-9: Record click-wrap acknowledgment with immutable timestamp."""
    transmittal = frappe.get_doc("Transmittal", transmittal_id)
    for recipient in transmittal.recipients:
        if recipient.user == recipient_user:
            if recipient.acknowledged:
                frappe.throw("Already acknowledged")
            recipient.acknowledged = 1
            recipient.acknowledged_at = now_datetime()
            break
    transmittal.save(ignore_permissions=True)
    return {"status": "success"}



