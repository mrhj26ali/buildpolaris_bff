import frappe
from buildpolaris_bff.project_closeout.services import gates, documents

@frappe.whitelist()
def get_closeout_status(project: str): 
    rec = frappe.get_all("Closing Record", filters={"project": project}, limit=1)
    return frappe.get_doc("Closing Record", rec[0].name).as_dict() if rec else {}
@frappe.whitelist()
def initiate_closeout(**kwargs): return gates.initiate_closeout(**kwargs)
@frappe.whitelist()
def issue_substantial_completion(**kwargs): return gates.issue_substantial_completion(**kwargs)
@frappe.whitelist()
def create_warranty_document(**kwargs): return documents.create_warranty_document(**kwargs)
