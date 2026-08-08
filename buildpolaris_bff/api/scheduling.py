import frappe
from buildpolaris_bff.application.cpm_engine import run_dcma_health_check

@frappe.whitelist()
def get_wbs_tree(project: str):
    """FR-1: Fetch hierarchical WBS for the Gantt chart."""
    return frappe.get_all("Task", 
        filters={"project": project}, 
        fields=["name", "task_name", "parent_task", "exp_start_date", "exp_end_date", "progress", "is_critical", "wbs_code"],
        order_by="creation asc"
    )

@frappe.whitelist()
def save_dependency(project: str, predecessor: str, successor: str, type: str, lag_days: int):
    """FR-3: Save dependency. Validation happens in the DocType controller."""
    doc = frappe.get_doc({
        "doctype": "Task Dependency",
        "project": project,
        "predecessor_task": predecessor,
        "successor_task": successor,
        "type": type,
        "lag_days": lag_days
    })
    doc.insert(ignore_permissions=True)
    return doc.name

@frappe.whitelist()
def get_health_check(project: str):
    """FR-15: Expose DCMA health check to PWA."""
    return run_dcma_health_check(project)