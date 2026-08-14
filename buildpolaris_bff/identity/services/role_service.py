"""
FR-1.4: Role management, with the last-Admin-of-a-Company demotion guard.
FR-1.7: deactivate (never hard-delete) a user, preserving historical records.
"""
import frappe

from buildpolaris_bff.shared.exceptions import ValidationError
from buildpolaris_bff.shared.permissions import PLATFORM_ROLES, assert_role
from buildpolaris_bff.shared.security_log import log_security_event

ADMIN_ROLE = "BuildPolaris Admin"


def _admins_in_company(company: str) -> list[str]:
	rows = frappe.get_all(
		"Has Role", filters={"role": ADMIN_ROLE, "parenttype": "User"}, fields=["parent"]
	)
	admin_users = [r.parent for r in rows]
	if not admin_users:
		return []
	return frappe.get_all(
		"User",
		filters={"name": ["in", admin_users], "bp_company": company, "enabled": 1},
		pluck="name",
	)


def set_user_role(user: str, role: str, company: str, changed_by: str | None = None):
	changed_by = changed_by or frappe.session.user
	assert_role(ADMIN_ROLE, user=changed_by)

	if role not in PLATFORM_ROLES:
		raise ValidationError(f"'{role}' is not a recognized BuildPolaris Role.")

	user_doc = frappe.get_doc("User", user)

	# FR-1.4: never demote the last remaining Admin of a Company.
	current_roles = {r.role for r in user_doc.roles}
	if ADMIN_ROLE in current_roles and role != ADMIN_ROLE:
		remaining_admins = [a for a in _admins_in_company(company) if a != user]
		if not remaining_admins:
			raise ValidationError(f"Cannot remove the last remaining {ADMIN_ROLE} of {company}.")

	user_doc.roles = []
	user_doc.append("roles", {"role": role})
	user_doc.save(ignore_permissions=True)

	log_security_event("ROLE_CHANGED", {"user": user, "new_role": role, "changed_by": changed_by})
	frappe.db.commit()
	return {"user": user, "role": role}


def deactivate_user(user: str, company: str, deactivated_by: str | None = None):
	"""FR-1.7: deactivate, never hard-delete - preserves historical records
	for audit (NFR-RETAIN.2: deactivation is independent of retention-period
	expiry and never itself triggers deletion)."""
	deactivated_by = deactivated_by or frappe.session.user
	assert_role(ADMIN_ROLE, user=deactivated_by)

	user_doc = frappe.get_doc("User", user)
	is_admin = any(r.role == ADMIN_ROLE for r in user_doc.roles)
	if is_admin:
		remaining_admins = [a for a in _admins_in_company(company) if a != user]
		if not remaining_admins:
			raise ValidationError(f"Cannot deactivate the last remaining {ADMIN_ROLE} of {company}.")

	frappe.db.set_value("User", user, "enabled", 0)
	log_security_event("USER_DEACTIVATED", {"user": user, "deactivated_by": deactivated_by})
	frappe.db.commit()
	return {"user": user, "status": "deactivated"}
