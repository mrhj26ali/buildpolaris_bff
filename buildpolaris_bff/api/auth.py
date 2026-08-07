import frappe
from frappe.rate_limiter import rate_limit

from buildpolaris_bff.application import identity_service as svc


@frappe.whitelist(allow_guest=True)
def get_csrf_token():
	"""Native CSRF mechanism (validator-compatible)."""
	return frappe.sessions.get_csrf_token()


@frappe.whitelist(allow_guest=True)
def get_current_user():
	return {"user": frappe.session.user}


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=5, seconds=3600, ip_based=True)
def register_tenant(company_name: str, admin_email: str, admin_name: str,
					admin_password: str, country: str = "United States",
					currency: str = "USD"):
	"""UC-01 (FR-1.1, FR-1.9)"""
	return svc.register_new_tenant(
		company_name, admin_email, admin_name, admin_password, country, currency
	)


@frappe.whitelist(allow_guest=True)
def activate_account(token: str, password: str | None = None):
	"""UC-01/UC-02 activation"""
	return svc.activate_account(token, password)


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=3, seconds=3600, ip_based=True)
def resend_activation(email: str):
	return svc.resend_activation(email)


@frappe.whitelist()
def get_session_context():
	"""UC-03/UC-04 — user, roles, persona, company"""
	return svc.get_session_context()