"""
Identity & Tenant Administration - HTTP adapters only (NFR-MAINT.1).
Every function here does Role/permission assertion + shape validation, then
calls exactly one services/ function - no business logic lives here.

Every dotted path and payload shape below matches buildpolaris_pwa's
src/lib/auth/session.ts and src/features/identity/model/identityApi.ts
exactly - those files were the more complete, already-built side of this
contract; this module was brought into alignment with them, not the
other way around.
"""
import frappe

from buildpolaris_bff.shared.api_envelope import success, api_guard
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
@api_guard
def register_tenant(company_name: str, admin_email: str, admin_first_name: str,
                     country: str = "United States"):
	"""FR-1.1. Unauthenticated - rate-limited against enumeration/brute-force
	(NFR-SEC.6). Role: Prospect (no Role required, no session yet)."""
	if is_rate_limited("register_tenant", limit=5, seconds=300):
		raise RateLimitedError("Too many registration attempts. Try again later.")
	result = registration_service.register_tenant(company_name, admin_email, admin_first_name, country)
	return success(result)


@frappe.whitelist(allow_guest=True)
@api_guard
def activate_account(token: str, password: str):
	"""FR-1.1. Unauthenticated - rate-limited (NFR-SEC.6). Token-only - see
	registration_service.activate_account's docstring for why there is no
	`user` parameter."""
	if is_rate_limited(f"activate:{token[:16]}", limit=10, seconds=600):
		raise RateLimitedError("Too many activation attempts. Try again later.")
	result = registration_service.activate_account(token, password)
	return success(result)


@frappe.whitelist()
@api_guard
def invite_user(email: str, first_name: str, roles: list, project_names: list | None = None):
	"""FR-1.2. Role: Admin (asserted inside invitation_service.invite_user).
	Company is resolved server-side from the inviting Admin - never
	accepted from the client."""
	if isinstance(roles, str):
		roles = frappe.parse_json(roles)
	if isinstance(project_names, str):
		project_names = frappe.parse_json(project_names)
	result = invitation_service.invite_user(email, first_name, roles, project_names)
	return success(result)


@frappe.whitelist(allow_guest=True)
@api_guard
def accept_invite(token: str, new_password: str):
	"""FR-1.2. Unauthenticated - rate-limited (NFR-SEC.6). Token-only, same
	reasoning as activate_account."""
	if is_rate_limited(f"accept_invite:{token[:16]}", limit=10, seconds=600):
		raise RateLimitedError("Too many attempts. Try again later.")
	result = invitation_service.accept_invite(token, new_password)
	return success(result)


@frappe.whitelist()
@api_guard
def assign_project(user: str, project: str):
	"""FR-1.3. Role: Admin or Project Manager."""
	result = invitation_service.assign_project(user, project)
	return success(result)


@frappe.whitelist()
@api_guard
def list_team_members():
	"""FR-1.2/1.4/1.7's read model. Role: Admin (asserted inside
	role_service.list_team_members). Scoped to the caller's own Company
	server-side - never a client-supplied filter."""
	return success(role_service.list_team_members())


@frappe.whitelist()
@api_guard
def update_user_roles(email: str, roles: list):
	"""FR-1.4. Role: Admin. Replaces the target user's full Role set.
	Guards against demoting the last Admin of a Company."""
	if isinstance(roles, str):
		roles = frappe.parse_json(roles)
	result = role_service.update_user_roles(email, roles)
	return success(result)


@frappe.whitelist()
@api_guard
def disable_user(email: str):
	"""FR-1.7. Role: Admin. Deactivates - never hard-deletes."""
	result = role_service.disable_user(email)
	return success(result)


@frappe.whitelist()
@api_guard
def get_session_context():
	"""FR-1.5. Role: any authenticated user - returns only the caller's own
	context. Not allow_guest - Frappe itself rejects an unauthenticated
	caller with a 401 before this ever runs."""
	return success(session_service.get_session_context())


@frappe.whitelist()
@api_guard
def get_change_history(doctype: str, name: str):
	"""FR-1.6. Role: any user with read access to the target document -
	enforced inside shared/audit.get_history via frappe.has_permission."""
	return success(change_history_service.get_change_history(doctype, name))
