import frappe
from buildpolaris_bff.financials.services.budget import _update_cost_code_committed

def create_commitment(project: str, cost_code: str, vendor: str, commitment_type: str = "Subcontract", original_amount: float = 0, retainage_percent: float = 10, description: str = None):
    commitment = frappe.get_doc({"doctype": "Commitment", "project": project, "cost_code": cost_code, "vendor": vendor, "commitment_type": commitment_type, "original_amount": original_amount, "retainage_percent": retainage_percent, "description": description, "status": "Draft"}).insert(ignore_permissions=True)
    return commitment.name

def approve_commitment(commitment_id: str):
    commitment = frappe.get_doc("Commitment", commitment_id)
    if commitment.status != "Draft": frappe.throw(f"Cannot approve commitment in status '{commitment.status}'")
    commitment.status = "Approved"
    commitment.save(ignore_permissions=True)
    _update_cost_code_committed(commitment.cost_code)
    return {"status": "success", "commitment_id": commitment.name}
