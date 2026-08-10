import frappe

def create_cost_code(project: str, code: str, title: str, original_budget: float = 0, parent_cost_code: str = None):
    cost_code = frappe.get_doc({"doctype": "Cost Code", "project": project, "code": code, "title": title, "original_budget": original_budget, "revised_budget": original_budget, "parent_cost_code": parent_cost_code}).insert(ignore_permissions=True)
    return cost_code.name

def _update_cost_code_committed(cost_code_id: str):
    commitments = frappe.get_all("Commitment", filters={"cost_code": cost_code_id, "status": ["in", ["Approved", "Closed"]]}, fields=["revised_amount"])
    total_committed = sum(c.revised_amount or 0 for c in commitments)
    cost_code = frappe.get_doc("Cost Code", cost_code_id)
    cost_code.committed_amount = total_committed
    cost_code.save(ignore_permissions=True)
