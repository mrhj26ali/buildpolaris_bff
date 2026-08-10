import frappe
import frappe.sessions
from frappe import _
from buildpolaris_bff.identity.services import identity as svc
from buildpolaris_bff.shared.api_utils import standard_response

@frappe.whitelist(allow_guest=True)
def get_csrf_token():
    token = frappe.sessions.get_csrf_token()
    frappe.db.commit() 
    return token

@frappe.whitelist(allow_guest=True)
def register_tenant(company_name: str, admin_email: str, admin_first_name: str, password: str = None):
    try:
        result = svc.register_new_tenant(company_name, admin_email, admin_first_name, password)
        return standard_response(True, result, "Tenant registered successfully")
    except Exception as e:
        return standard_response(False, None, str(e), http_status_code=400)

@frappe.whitelist(allow_guest=True)
def activate_account(token: str, password: str = None):
    try:
        result = svc.activate_account(token, password)
        return standard_response(True, result, "Account activated")
    except Exception as e:
        return standard_response(False, None, str(e), http_status_code=400)

@frappe.whitelist(allow_guest=True)
def resend_activation(email: str):
    return standard_response(True, {"status": "resent"}, "Activation resent")

@frappe.whitelist()
def get_session_context():
    try:
        result = svc.get_session_context()
        return standard_response(True, result, "Session context retrieved")
    except Exception as e:
        return standard_response(False, None, str(e), http_status_code=400)
