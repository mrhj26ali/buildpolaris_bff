import frappe
from buildpolaris_bff.scheduling.services.cpm_engine import run_dcma_health_check

@frappe.whitelist()
def get_wbs_tree(project: str): return frappe.get_all("Task", filters={"project": project})
@frappe.whitelist()
def save_dependency(project: str, predecessor: str, successor: str, type: str, lag_days: int):
    doc = frappe.get_doc({"doctype": "Task Dependency", "project": project, "predecessor_task": predecessor, "successor_task": successor, "type": type, "lag_days": lag_days})
    doc.insert(ignore_permissions=True)
    return doc.name
@frappe.whitelist()
def get_health_check(project: str): return run_dcma_health_check(project)
