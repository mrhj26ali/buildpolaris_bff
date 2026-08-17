"""
FR-1.4: Role management, with the last-Admin-of-a-Company demotion guard,
generalized to multi-Role-per-user (a User can legitimately hold more than
one BuildPolaris Role - e.g. Project Manager + Safety Officer on a small
project - Frappe's own Role model already supports this natively; nothing
in REQ/UC restricts a user to exactly one).
FR-1.7: deactivate (never hard-delete) a user, preserving historical records.
"""
import frappe

from buildpolaris_bff.identity.services.role_mapping import to_frappe_roles, to_short_roles
from buildpolaris_bff.shared.exceptions import ValidationError
from buildpolaris_bff.shared.permissions import assert_role, get_assigned_projects
from buildpolaris_bff.shared.security_log import log_security_event

ADMIN_ROLE = "BuildPolaris Admin"


def _company_for(user: str) -> str | None:
	if not frappe.db.has_column("User", "bp_company"):
		return None
	return frappe.db.get_value("User", user, "bp_company")


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


def update_user_roles(email: str, roles: list[str], changed_by: str | None = None):
	"""Replaces the target user's full Role set with `roles` (a full
	replacement, not a merge - matches buildpolaris_pwa's team management
	screen, which always submits the complete intended Role set)."""
	changed_by = changed_by or frappe.session.user
	assert_role(ADMIN_ROLE, user=changed_by)

	if not roles:
		raise ValidationError("At least one Role is required.")
	frappe_roles = to_frappe_roles(roles)

	user_doc = frappe.get_doc("User", email)
	company = _company_for(email)

	# FR-1.4: never demote the last remaining Admin of a Company.
	current_roles = {r.role for r in user_doc.roles}
	if ADMIN_ROLE in current_roles and ADMIN_ROLE not in frappe_roles and company:
		remaining_admins = [a for a in _admins_in_company(company) if a != email]
		if not remaining_admins:
			raise ValidationError(f"Cannot remove the last remaining {ADMIN_ROLE} of {company}.")

	user_doc.roles = []
	for role in frappe_roles:
		user_doc.append("roles", {"role": role})
	user_doc.save(ignore_permissions=True)

	log_security_event("ROLE_CHANGED", {"user": email, "new_roles": frappe_roles, "changed_by": changed_by})
	frappe.db.commit()
	return {"user": email, "roles": to_short_roles(frappe_roles)}


def disable_user(email: str, deactivated_by: str | None = None):
	"""FR-1.7: deactivate, never hard-delete - preserves historical records
	for audit (NFR-RETAIN.2: deactivation is independent of retention-period
	expiry and never itself triggers deletion). Company is resolved from
	the TARGET user's own tenant, never accepted from the client."""
	deactivated_by = deactivated_by or frappe.session.user
	assert_role(ADMIN_ROLE, user=deactivated_by)

	user_doc = frappe.get_doc("User", email)
	company = _company_for(email)
	is_admin = any(r.role == ADMIN_ROLE for r in user_doc.roles)
	if is_admin and company:
		remaining_admins = [a for a in _admins_in_company(company) if a != email]
		if not remaining_admins:
			raise ValidationError(f"Cannot deactivate the last remaining {ADMIN_ROLE} of {company}.")

	frappe.db.set_value("User", email, "enabled", 0)
	log_security_event("USER_DEACTIVATED", {"user": email, "deactivated_by": deactivated_by})
	frappe.db.commit()
	return {"user": email, "status": "disabled"}


def list_team_members(user: str | None = None) -> list:
	"""FR-1.2/1.4/1.7's read model - every User belonging to the caller's
	own Company, with their Roles, status, and assigned Projects. Never
	lists across Companies - `bp_company` scoping is server-side, not a
	client-supplied filter."""
	user = user or frappe.session.user
	assert_role(ADMIN_ROLE, user=user)

	company = _company_for(user)
	if not company:
		return []

	filters = {"bp_company": company} if frappe.db.has_column("User", "bp_company") else {}
	rows = frappe.get_all(
		"User", filters=filters,
		fields=["name", "email", "full_name", "enabled"] + (
			["bp_invite_status"] if frappe.db.has_column("User", "bp_invite_status") else []
		),
	)

	members = []
	for row in rows:
		frappe_roles = frappe.get_roles(row.name)
		bp_roles = [r for r in frappe_roles if r.startswith("BuildPolaris ")]
		if not bp_roles:
			continue  # not a BuildPolaris platform user (e.g. the AI service account)

		if not row.enabled:
			status = "Disabled"
		elif row.get("bp_invite_status") == "Pending":
			status = "Invited"
		else:
			status = "Active"

		members.append({
			"email": row.email or row.name,
			"full_name": row.full_name,
			"roles": to_short_roles(bp_roles),
			"status": status,
			"assigned_projects": get_assigned_projects(row.name),
		})
	return members
