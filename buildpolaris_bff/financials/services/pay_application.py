import frappe

def create_pay_application(project: str, commitment_id: str, period_start: str = None, period_end: str = None, retainage_percent: float = None, lines: list = None):
    commitment = frappe.get_doc("Commitment", commitment_id)
    existing = frappe.get_all("Pay Application", filters={"commitment": commitment_id}, fields=["application_number"], order_by="application_number desc", limit=1)
    next_num = (existing[0].application_number + 1) if existing else 1
    pay_app = frappe.get_doc({"doctype": "Pay Application", "project": project, "commitment": commitment_id, "application_number": next_num, "period_start": period_start, "period_end": period_end, "retainage_percent": retainage_percent if retainage_percent is not None else commitment.retainage_percent, "status": "Draft", "lines": [{"cost_code": l.get("cost_code"), "description": l.get("description", ""), "scheduled_value": l.get("scheduled_value", 0), "previous_completed": l.get("previous_completed", 0), "current_completed": l.get("current_completed", 0)} for l in (lines or [])]}).insert(ignore_permissions=True)
    return pay_app.name

def submit_pay_application(pay_app_id: str):
    pay_app = frappe.get_doc("Pay Application", pay_app_id)
    if pay_app.status != "Draft": frappe.throw(f"Cannot submit pay application in status '{pay_app.status}'")
    if not pay_app.lines: frappe.throw("Cannot submit pay application without schedule of values lines")
    pay_app.status = "Submitted"
    pay_app.save(ignore_permissions=True)
    return {"status": "success", "pay_app_id": pay_app.name}

def approve_pay_application(pay_app_id: str):
    pay_app = frappe.get_doc("Pay Application", pay_app_id)
    if pay_app.status != "Submitted": frappe.throw(f"Cannot approve pay application in status '{pay_app.status}'. Must be Submitted first.")
    pay_app.status = "Approved"
    pay_app.save(ignore_permissions=True)
    return {"status": "success", "pay_app_id": pay_app.name}
