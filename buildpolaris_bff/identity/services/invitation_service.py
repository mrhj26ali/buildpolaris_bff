"""
FR-1.2: Admin invites additional users with one or more Roles; the invitee
activates via a single-use, hashed, time-boxed token on first login (see
registration_service.activate_account - the same unified activation flow
handles both self-registration and invited-user tokens).
FR-1.3's Project-scoping (assign_project) also lives here since it's part
of the same "bring a user into scope" workflow.
"""
import frappe
from frappe.utils import add_to_date, now_datetime

from buildpolaris_bff.identity.services.role_mapping import to_frappe_roles
from buildpolaris_bff.shared.crypto_utils import generate_secure_token
from buildpolaris_bff.shared.exceptions import ValidationError
from buildpolaris_bff.shared.permissions import assert_role
from buildpolaris_bff.shared.security_log import log_security_event

INVITE_TOKEN_TTL_HOURS = 72


def _company_for(user: str) -> str | None:
	if not frappe.db.has_column("User", "bp_company"):
		return None
	return frappe.db.get_value("User", user, "bp_company")


def invite_user(email: str, first_name: str, roles: list[str], project_names: list[str] | None = None,
                 invited_by: str | None = None) -> dict:
	"""Role: Admin. Company is resolved from the INVITING Admin's own
	tenant - never accepted from the client, so an Admin can never invite
	a user into a Company they don't themselves belong to."""
	invited_by = invited_by or frappe.session.user
	assert_role("BuildPolaris Admin", user=invited_by)

	company = _company_for(invited_by)
	if not company:
		raise ValidationError("Your user account has no Company assigned - contact a System Manager.")

	if not roles:
		raise ValidationError("At least one Role is required.")
	frappe_roles = to_frappe_roles(roles)

	if frappe.db.exists("User", email):
		raise ValidationError(f"A user with email '{email}' already exists.")

	user = frappe.new_doc("User")
	user.email = email
	user.first_name = first_name
	user.enabled = 0
	user.send_welcome_email = 0
	for role in frappe_roles:
		user.append("roles", {"role": role})
	user.flags.ignore_password_policy = True
	user.insert(ignore_permissions=True)

	if frappe.db.has_column("User", "bp_company"):
		frappe.db.set_value("User", user.name, "bp_company", company)
		frappe.db.set_value("User", user.name, "bp_invite_status", "Pending")
		frappe.db.set_value("User", user.name, "bp_needs_password", 1)
		frappe.db.set_value("User", user.name, "bp_invited_by", invited_by)

	raw_token, hashed_token = generate_secure_token()
	frappe.get_doc({
		"doctype": "Account Activation Token",
		"user": user.name,
		"company": company,
		"purpose": "Invite",
		"token_hash": hashed_token,
		"expires_at": add_to_date(now_datetime(), hours=INVITE_TOKEN_TTL_HOURS),
		"created_by_user": invited_by,
	}).insert(ignore_permissions=True)

	for project in (project_names or []):
		assign_project(user.name, project, assigned_by=invited_by)

	log_security_event("USER_INVITED", {"invited_by": invited_by, "user": user.name, "roles": frappe_roles})
	frappe.db.commit()
	return {"user": user.name, "invite_token": raw_token}


def accept_invite(raw_token: str, new_password: str) -> dict:
	"""Thin alias over the unified activation lookup - kept as a distinct
	entrypoint for callers that specifically mean 'accepting an invite'
	rather than 'activating a self-registration', even though both now
	resolve the same way. See registration_service.activate_account."""
	from buildpolaris_bff.identity.services.registration_service import activate_account
	return activate_account(raw_token, new_password)


def assign_project(user: str, project: str, assigned_by: str | None = None):
	"""FR-1.3: grants Project-scoped access via native User Permission -
	never an application-level filter a developer could omit."""
	assigned_by = assigned_by or frappe.session.user
	assert_role("BuildPolaris Admin", "BuildPolaris Project Manager", user=assigned_by)

	if frappe.db.exists("User Permission", {"user": user, "allow": "Project", "for_value": project}):
		return {"user": user, "project": project, "status": "already_assigned"}

	frappe.get_doc({
		"doctype": "User Permission",
		"user": user,
		"allow": "Project",
		"for_value": project,
		"apply_to_all_doctypes": 1,
	}).insert(ignore_permissions=True)
	log_security_event("PROJECT_ASSIGNED", {"user": user, "project": project, "assigned_by": assigned_by})
	return {"user": user, "project": project, "status": "assigned"}
