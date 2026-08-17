import frappe

@frappe.whitelist(allow_guest=True)
def get_csrf_token():
    """Returns the Frappe CSRF token for the current session."""
    return frappe.local.csrf_token