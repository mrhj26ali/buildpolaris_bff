"""
FR-1.2: Admin invites additional users with a designated Role; the invitee
activates via a single-use, hashed, time-boxed token on first login.
FR-1.3's Project-scoping (assign_project) also lives here since it's part
of the same "bring a user into scope" workflow.
"""
import frappe
from frappe.utils import add_to_date, now_datetime

from buildpolaris_bff.shared.crypto_utils import generate_secure_token
from buildpolaris_bff.shared.exceptions import ValidationError
from buildpolaris_bff.shared.permissions import PLATFORM_ROLES, assert_role
from buildpolaris_bff.shared.security_log import log_security_event
from buildpolaris_bff.identity.services.registration_service import _find_valid_token

INVITE_TOKEN_TTL_HOURS = 72


def invite_user(email: str, full_name: str, role: str, company: str,
                 invited_by: str | None = None) -> dict:
	"""Role: Admin. Safe to call from a script/job/test identically -
	permission is asserted here, not only at the api.py layer."""
	invited_by = invited_by or frappe.session.user
	assert_role("BuildPolaris Admin", user=invited_by)

	if role not in PLATFORM_ROLES:
		raise ValidationError(f"'{role}' is not a recognized BuildPolaris Role.")

	if frappe.db.exists("User", email):
		raise ValidationError(f"A user with email '{email}' already exists.")

	user = frappe.new_doc("User")
	user.email = email
	user.first_name = full_name
	user.enabled = 0
	user.send_welcome_email = 0
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

	log_security_event("USER_INVITED", {"invited_by": invited_by, "user": user.name, "role": role})
	frappe.db.commit()
	return {"user": user.name, "invite_token": raw_token}


def accept_invite(user: str, raw_token: str, new_password: str) -> dict:
	token_doc = _find_valid_token(user, raw_token, purpose="Invite")

	frappe.db.set_value("User", user, "enabled", 1)
	if frappe.db.has_column("User", "bp_invite_status"):
		frappe.db.set_value("User", user, "bp_invite_status", "Accepted")
		frappe.db.set_value("User", user, "bp_needs_password", 0)

	user_doc = frappe.get_doc("User", user)
	user_doc.new_password = new_password
	user_doc.flags.ignore_password_policy = False
	user_doc.save(ignore_permissions=True)

	token_doc.mark_used()
	log_security_event("INVITE_ACCEPTED", {"user": user})
	frappe.db.commit()
	return {"user": user, "status": "activated"}


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
