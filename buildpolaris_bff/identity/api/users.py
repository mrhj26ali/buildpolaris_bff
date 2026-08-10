import json

import frappe

from buildpolaris_bff.identity.services import identity as svc


def _roles(roles) -> list[str]:
	if isinstance(roles, str):
		roles = json.loads(roles)
	return list(roles)


@frappe.whitelist()
def available_roles():
	"""FR-1.8 — role catalog for the checkbox UI"""
	return svc.available_roles()


@frappe.whitelist()
def list_users():
	"""FR-1.7 — tenant user list (UC-02/UC-07)"""
	return svc.list_tenant_users()


@frappe.whitelist()
def invite_user(email: str, full_name: str, roles):
	"""UC-02 (FR-1.2)"""
	return svc.invite_user(email, full_name, _roles(roles))


@frappe.whitelist()
def resend_invite(email: str):
	return svc.resend_invite(email)


@frappe.whitelist()
def update_user_roles(email: str, roles):
	"""UC-07 (FR-1.7/1.10)"""
	return svc.update_user_roles(email, _roles(roles))


@frappe.whitelist()
def set_user_enabled(email: str, enabled):
	"""UC-07"""
	enabled = enabled in (True, "true", "1", 1)
	return svc.set_user_enabled(email, enabled)
