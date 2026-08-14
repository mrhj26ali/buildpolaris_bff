"""
Identity & Tenant Administration - HTTP adapters only (NFR-MAINT.1).
Every function here does Role/permission assertion + shape validation, then
calls exactly one services/ function - no business logic lives here.
"""
import frappe

from buildpolaris_bff.shared.api_envelope import success
from buildpolaris_bff.shared.exceptions import RateLimitedError
from buildpolaris_bff.shared.rate_limit import is_rate_limited
from buildpolaris_bff.identity.services import (
	change_history_service,
	invitation_service,
	registration_service,
	role_service,
	session_service,
)


@frappe.whitelist(allow_guest=True)
def register_tenant(company_name: str, admin_email: str, admin_full_name: str,
                     country: str = "United States", default_currency: str = "USD"):
	"""FR-1.1. Unauthenticated - rate-limited against enumeration/brute-force
	(NFR-SEC.6). Role: Prospect (no Role required, no session yet)."""
	if is_rate_limited("register_tenant", limit=5, seconds=300):
		raise RateLimitedError("Too many registration attempts. Try again later.")
	result = registration_service.register_tenant(
		company_name, admin_email, admin_full_name, country, default_currency
	)
	return success(result)


@frappe.whitelist(allow_guest=True)
def activate_account(user: str, token: str, new_password: str):
	"""FR-1.1. Unauthenticated - rate-limited (NFR-SEC.6)."""
	if is_rate_limited(f"activate:{user}", limit=10, seconds=600):
		raise RateLimitedError("Too many activation attempts. Try again later.")
	result = registration_service.activate_account(user, token, new_password)
	return success(result)


@frappe.whitelist()
def invite_user(email: str, full_name: str, role: str, company: str):
	"""FR-1.2. Role: Admin (asserted inside invitation_service.invite_user)."""
	result = invitation_service.invite_user(email, full_name, role, company)
	return success(result)


@frappe.whitelist(allow_guest=True)
def accept_invite(user: str, token: str, new_password: str):
	"""FR-1.2. Unauthenticated - rate-limited (NFR-SEC.6)."""
	if is_rate_limited(f"accept_invite:{user}", limit=10, seconds=600):
		raise RateLimitedError("Too many attempts. Try again later.")
	result = invitation_service.accept_invite(user, token, new_password)
	return success(result)


@frappe.whitelist()
def assign_project(user: str, project: str):
	"""FR-1.3. Role: Admin or Project Manager."""
	result = invitation_service.assign_project(user, project)
	return success(result)


@frappe.whitelist()
def set_user_role(user: str, role: str, company: str):
	"""FR-1.4. Role: Admin. Guards against demoting the last Admin."""
	result = role_service.set_user_role(user, role, company)
	return success(result)


@frappe.whitelist()
def deactivate_user(user: str, company: str):
	"""FR-1.7. Role: Admin. Deactivates - never hard-deletes."""
	result = role_service.deactivate_user(user, company)
	return success(result)


@frappe.whitelist()
def get_session_context():
	"""FR-1.5. Role: any authenticated user - returns only the caller's own
	context."""
	return success(session_service.get_session_context())


@frappe.whitelist()
def get_change_history(doctype: str, name: str):
	"""FR-1.6. Role: any user with read access to the target document -
	enforced inside shared/audit.get_history via frappe.has_permission."""
	return success(change_history_service.get_change_history(doctype, name))
