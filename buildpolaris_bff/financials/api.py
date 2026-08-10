import frappe
from buildpolaris_bff.financials.services import budget, commitment, change_event, pay_application

@frappe.whitelist()
def get_budget_summary(project: str): return frappe.get_all("Cost Code", filters={"project": project})
@frappe.whitelist()
def create_cost_code(**kwargs): return budget.create_cost_code(**kwargs)
@frappe.whitelist()
def create_commitment(**kwargs): return commitment.create_commitment(**kwargs)
@frappe.whitelist()
def approve_commitment(commitment_id: str): return commitment.approve_commitment(commitment_id)
@frappe.whitelist()
def create_change_event(**kwargs): return change_event.create_change_event(**kwargs)
@frappe.whitelist()
def approve_change_event(change_event_id: str, approved_by: str = None): return change_event.approve_change_event(change_event_id, approved_by)
