from functools import wraps

import frappe
from frappe import _

from buildpolaris_bff.shared.security_log import log_security_event


def _current_request_path() -> str:
    request = getattr(frappe.local, "request", None)
    return getattr(request, "path", "unknown") if request else "unknown"


def require_authenticated_user(func):
    """
    Reject Guest users.
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        if frappe.session.user == "Guest":
            log_security_event(
                "UNAUTHENTICATED_API_ACCESS",
                {
                    "path": _current_request_path(),
                    "user": frappe.session.user,
                },
            )
            frappe.throw(_("Authentication required"), frappe.AuthenticationError)

        return func(*args, **kwargs)

    return wrapper


def require_roles(*roles: str):
    """
    Require at least one of the given Frappe roles.

    The Administrator is intentionally allowed as a platform operator.
    Tenant authorization must still be enforced by company/project guards.
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if frappe.session.user == "Guest":
                log_security_event(
                    "UNAUTHENTICATED_API_ACCESS",
                    {
                        "path": _current_request_path(),
                        "user": frappe.session.user,
                    },
                )
                frappe.throw(_("Authentication required"), frappe.AuthenticationError)

            if frappe.session.user == "Administrator":
                return func(*args, **kwargs)

            user_roles = frappe.get_roles()

            if not any(role in user_roles for role in roles):
                log_security_event(
                    "FORBIDDEN_ROLE_ACCESS",
                    {
                        "user": frappe.session.user,
                        "required_roles": list(roles),
                        "path": _current_request_path(),
                    },
                )
                frappe.throw(_("Not authorized"), frappe.PermissionError)

            return func(*args, **kwargs)

        return wrapper

    return decorator


def require_project_access(project_field: str = "project"):
    """
    Require read access to the Project passed in kwargs/form_dict.
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            project = kwargs.get(project_field) or frappe.form_dict.get(project_field)

            if not project:
                frappe.throw(_("Project is required"), frappe.ValidationError)

            if not frappe.db.exists("Project", project):
                log_security_event(
                    "PROJECT_ACCESS_MISSING_PROJECT",
                    {
                        "user": frappe.session.user,
                        "project": project,
                    },
                )
                frappe.throw(_("Not authorized"), frappe.PermissionError)

            if not frappe.has_permission("Project", "read", project):
                log_security_event(
                    "PROJECT_ACCESS_DENIED",
                    {
                        "user": frappe.session.user,
                        "project": project,
                    },
                )
                frappe.throw(_("Not authorized"), frappe.PermissionError)

            return func(*args, **kwargs)

        return wrapper

    return decorator


def require_document_access(doctype: str, name_field: str = "name", ptype: str = "read"):
    """
    Generic document-level permission guard.
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            docname = kwargs.get(name_field) or frappe.form_dict.get(name_field)

            if not docname:
                frappe.throw(_("{0} is required").format(name_field), frappe.ValidationError)

            if not frappe.db.exists(doctype, docname):
                log_security_event(
                    "DOCUMENT_ACCESS_MISSING_DOCUMENT",
                    {
                        "user": frappe.session.user,
                        "doctype": doctype,
                        "docname": docname,
                    },
                )
                frappe.throw(_("Not authorized"), frappe.PermissionError)

            if not frappe.has_permission(doctype, ptype, docname):
                log_security_event(
                    "DOCUMENT_ACCESS_DENIED",
                    {
                        "user": frappe.session.user,
                        "doctype": doctype,
                        "docname": docname,
                        "ptype": ptype,
                    },
                )
                frappe.throw(_("Not authorized"), frappe.PermissionError)

            return func(*args, **kwargs)

        return wrapper

    return decorator
