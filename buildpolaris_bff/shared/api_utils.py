import frappe
from frappe import _
from functools import wraps

def standard_response(success=True, data=None, message=None, error_code=None, http_status_code=200):
    frappe.local.response["http_status_code"] = http_status_code
    return {"success": success, "data": data, "message": message or ("Success" if success else "An error occurred"), "error_code": error_code}

def require_project_access(project_field="project"):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            project = kwargs.get(project_field) or frappe.form_dict.get(project_field)
            if not project: frappe.throw(_("Project is required"), frappe.ValidationError)
            if not frappe.has_permission("Project", doc=project, ptype="read"): frappe.throw(_("Not authorized"), frappe.PermissionError)
            return func(*args, **kwargs)
        return wrapper
    return decorator
