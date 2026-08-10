import frappe
from frappe.utils import now_datetime
from buildpolaris_bff.financials.services.budget import _update_cost_code_committed

def create_change_event(project: str, title: str, amount: float = 0, change_type: str = "Change Order", cost_code: str = None, description: str = None, linked_rfi: str = None, linked_commitment: str = None):
    change_event = frappe.get_doc({"doctype": "Change Event", "project": project, "title": title, "amount": amount, "change_type": change_type, "cost_code": cost_code, "description": description, "linked_rfi": linked_rfi, "linked_commitment": linked_commitment, "status": "Draft"}).insert(ignore_permissions=True)
    return change_event.name

def submit_change_event(change_event_id: str):
    ce = frappe.get_doc("Change Event", change_event_id)
    if ce.status != "Draft": frappe.throw(f"Cannot submit change event in status '{ce.status}'")
    ce.status = "Pending"
    ce.save(ignore_permissions=True)
    return {"status": "success", "change_event_id": ce.name}

def approve_change_event(change_event_id: str, approved_by: str = None):
    ce = frappe.get_doc("Change Event", change_event_id)
    if ce.status != "Pending": frappe.throw(f"Cannot approve change event in status '{ce.status}'. Must be Pending first.")
    ce.status = "Approved"
    ce.approved_by = approved_by or frappe.session.user
    ce.approved_at = now_datetime()
    ce.save(ignore_permissions=True)
    if ce.linked_commitment:
        commitment = frappe.get_doc("Commitment", ce.linked_commitment)
        approved_total = frappe.get_all("Change Event", filters={"linked_commitment": ce.linked_commitment, "status": "Approved"}, fields=["amount"])
        commitment.approved_changes = sum(c.amount or 0 for c in approved_total)
        commitment.revised_amount = (commitment.original_amount or 0) + commitment.approved_changes
        commitment.save(ignore_permissions=True)
        _update_cost_code_committed(commitment.cost_code)
    return {"status": "success", "change_event_id": ce.name}

def reject_change_event(change_event_id: str):
    ce = frappe.get_doc("Change Event", change_event_id)
    if ce.status != "Pending": frappe.throw(f"Cannot reject change event in status '{ce.status}'")
    ce.status = "Rejected"
    ce.save(ignore_permissions=True)
    return {"status": "success", "change_event_id": ce.name}
