import frappe
from frappe import _
from functools import wraps

def standard_response(success=True, data=None, message=None, error_code=None, http_status_code=200):
    """
    Standardizes API responses for the BuildPolaris PWA.
    Frappe automatically wraps the returned dict in a 'message' key.
    The PWA client is designed to unwrap res.message to get this exact structure.
    """
    frappe.local.response["http_status_code"] = http_status_code
    return {
        "success": success,
        "data": data,
        "message": message or ("Success" if success else "An error occurred"),
        "error_code": error_code
    }

def require_project_access(project_field="project"):
    """
    Decorator to enforce Frappe v16 document-level project access control on API endpoints.
    Prevents cross-project data leakage at the API boundary.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            project = kwargs.get(project_field) or frappe.form_dict.get(project_field)
            if not project:
                frappe.throw(_("Project is required"), frappe.ValidationError)
            
            # Frappe v16 document-level permission check
            if not frappe.has_permission("Project", doc=project, ptype="read"):
                frappe.throw(_("Not authorized to access this project"), frappe.PermissionError)
                
            return func(*args, **kwargs)
        return wrapper
    return decorator
