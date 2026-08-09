import frappe
import frappe.sessions
from frappe import _
from frappe.rate_limiter import rate_limit
from buildpolaris_bff.application import identity_service as svc
from buildpolaris_bff.api.utils import standard_response

@frappe.whitelist(allow_guest=True)
def get_csrf_token():
    """Native CSRF mechanism (validator-compatible)."""
    token = frappe.sessions.get_csrf_token()
    # CRITICAL: Must commit to persist the CSRF token in the guest session record
    frappe.db.commit() 
    return token

@frappe.whitelist(allow_guest=True)
@rate_limit(limit=5, seconds=60)
def register_tenant(company_name: str, admin_email: str, admin_first_name: str):
    try:
        result = svc.register_tenant(company_name, admin_email, admin_first_name)
        return standard_response(True, result, "Tenant registered successfully")
    except Exception as e:
        return standard_response(False, None, str(e), http_status_code=400)

@frappe.whitelist(allow_guest=True)
@rate_limit(limit=5, seconds=60)
def activate_account(token: str, password: str = None):
    try:
        result = svc.activate_account(token, password)
        return standard_response(True, result, "Account activated")
    except Exception as e:
        return standard_response(False, None, str(e), http_status_code=400)

@frappe.whitelist(allow_guest=True)
@rate_limit(limit=3, seconds=60)
def resend_activation(email: str):
    try:
        result = svc.resend_activation(email)
        return standard_response(True, result, "Activation resent")
    except Exception as e:
        return standard_response(False, None, str(e), http_status_code=400)

@frappe.whitelist()
def get_session_context():
    if frappe.session.user == "Guest":
        frappe.throw(_("Not logged in"), frappe.AuthenticationError)
        
    user = frappe.get_doc("User", frappe.session.user)
    return standard_response(True, {
        "user": user.name,
        "full_name": user.full_name,
        "company": user.company,
        "roles": [r.role for r in user.roles]
    }, "Session context retrieved")
