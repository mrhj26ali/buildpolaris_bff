import frappe
from frappe.utils import now_datetime
from frappe.utils import now_datetime

def create_rfi(project: str, subject: str, description: str = None,
               reference_doctype: str = None, reference_name: str = None,
               sender_recommendation: str = None, cost_impact: int = 0,
               schedule_impact: int = 0, requested_reply_date: str = None,
               watchers: list = None):
    """FR-1: Create a new RFI with Draft status."""
    rfi = frappe.get_doc({
        "doctype": "RFI",
        "project": project,
        "subject": subject,
        "description": description,
        "reference_doctype": reference_doctype,
        "reference_name": reference_name,
        "sender_recommendation": sender_recommendation,
        "cost_impact": cost_impact,
        "schedule_impact": schedule_impact,
        "requested_reply_date": requested_reply_date,
        "raised_by": frappe.session.user,
        "status": "Draft",
    }).insert(ignore_permissions=True)

    # FR-2: Add watchers
    if watchers:
        for user in watchers:
            frappe.get_doc({
                "doctype": "RFI Watcher",
                "rfi": rfi.name,
                "user": user,
                "watching": 1,
            }).insert(ignore_permissions=True)

    return rfi.name



def submit_rfi(rfi_id: str):
    """FR-1: Transition RFI from Draft to Open."""
    rfi = frappe.get_doc("RFI", rfi_id)
    if rfi.status != "Draft":
        frappe.throw(f"Cannot submit RFI in status {rfi.status}")
    rfi.status = "Open"
    rfi.save(ignore_permissions=True)
    return {"status": "success", "rfi_id": rfi.name}



def answer_rfi(rfi_id: str, receivers_reply: str):
    """FR-1: Transition RFI to Answered."""
    rfi = frappe.get_doc("RFI", rfi_id)
    if rfi.status != "Open":
        frappe.throw(f"Cannot answer RFI in status {rfi.status}")
    rfi.receivers_reply = receivers_reply
    rfi.status = "Answered"
    rfi.save(ignore_permissions=True)
    return {"status": "success", "rfi_id": rfi.name}



def close_rfi(rfi_id: str):
    """FR-1: Transition RFI to Closed."""
    rfi = frappe.get_doc("RFI", rfi_id)
    if rfi.status != "Answered":
        frappe.throw(f"Cannot close RFI in status {rfi.status}")
    rfi.status = "Closed"
    rfi.save(ignore_permissions=True)
    return {"status": "success", "rfi_id": rfi.name}



def route_item(project: str, reference_doctype: str, reference_name: str,
               reviewer: str, decision: str = None):
    """FR-3: Record a routing step using the unified RouteStep entity."""
    route_step = frappe.get_doc({
        "doctype": "Route Step",
        "project": project,
        "reference_doctype": reference_doctype,
        "reference_name": reference_name,
        "reviewer": reviewer,
        "decision": decision,
        "routed_at": now_datetime(),
    }).insert(ignore_permissions=True)

    # Update ball_in_court on the referenced document
    doc = frappe.get_doc(reference_doctype, reference_name)
    doc.ball_in_court = reviewer
    doc.save(ignore_permissions=True)

    return route_step.name



