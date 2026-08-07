import secrets
from datetime import datetime, timedelta

import frappe
from frappe.utils import now_datetime, validate_email_address

from buildpolaris_bff.application.persona import resolve_persona
from buildpolaris_bff.infrastructure import erpnext_bridge as bridge
from buildpolaris_bff.infrastructure.security_log import log_security_event
from buildpolaris_bff.install import ADMIN_ROLE_NAME, PLATFORM_ROLES, get_platform_role_names

ACTIVATION_TTL_HOURS = 72
INVITE_TTL_HOURS = 72


def _token() -> str:
	return secrets.token_urlsafe(32)


def _pwa_url() -> str:
	return frappe.conf.get("pwa_url") or "http://localhost:5173"


def _send_email(recipient: str, subject: str, html: str):
	if frappe.flags.in_test or frappe.conf.get("mute_emails"):
		return
	try:
		frappe.sendmail(recipients=[recipient], subject=subject, message=html, now=True)
	except Exception as e:
		# In local dev without SMTP configured, log the error but DO NOT crash the registration API.
		frappe.log_error(title="BuildPolaris Email Failed", message=f"Could not send to {recipient}: {e!s}")


# ---------------------------------------------------------------- UC-01 (FR-1.1)
def register_new_tenant(
	company_name, admin_email, admin_name, admin_password, country="United States", currency="USD"
) -> dict:
	if not all([company_name, admin_email, admin_name, admin_password]):
		frappe.throw("Missing required fields.")
	if len(admin_password) < 8:
		frappe.throw("Password must be at least 8 characters long.")
	if not validate_email_address(admin_email):
		frappe.throw("Invalid email address.")
	if bridge.company_exists(company_name):
		frappe.throw("A workspace with this company name already exists. Choose a unique name.")
	if bridge.user_exists(admin_email):
		frappe.throw("A user with this email already exists.")

	initials = "".join(w[0].upper() for w in company_name.split()[:2]) or "BP"
	abbr = (initials + secrets.token_hex(2)).upper()

	company = bridge.create_company(company_name, abbr, country, currency)

	bridge.create_platform_user(
		admin_email, admin_name, password=admin_password, enabled=0, roles=[ADMIN_ROLE_NAME]
	)

	token, expiry = _token(), now_datetime() + timedelta(hours=ACTIVATION_TTL_HOURS)
	bridge.set_user_fields(
		admin_email,
		bp_company=company,
		bp_activation_token=token,
		bp_activation_expiry=expiry,
	)
	bridge.add_company_permission(admin_email, company)

	link = f"{_pwa_url()}/activate?token={token}"
	_send_email(
		admin_email,
		"Activate your BuildPolaris workspace",
		f"<p>Welcome {admin_name},</p>"
		f"<p>Click below to activate your workspace <b>{company_name}</b>:</p>"
		f"<p><a href='{link}'>Activate workspace</a></p>"
		f"<p>This link expires in {ACTIVATION_TTL_HOURS} hours.</p>",
	)

	return {
		"status": "success",
		"company": company,
		"admin_email": admin_email,
		"message": "Workspace created. Check your email to activate it.",
	}


def activate_account(token: str, password: str | None = None) -> dict:
	user_email = frappe.db.get_value("User", {"bp_activation_token": token}, "name") or frappe.db.get_value(
		"User", {"bp_invite_token": token}, "name"
	)
	if not user_email:
		return {"status": "invalid"}

	fields = bridge.get_user_fields(
		user_email,
		[
			"bp_activation_token",
			"bp_activation_expiry",
			"bp_invite_token",
			"bp_invite_expiry",
			"bp_needs_password",
		],
	)

	expiry = (
		fields.get("bp_activation_expiry")
		if fields.get("bp_activation_token") == token
		else fields.get("bp_invite_expiry")
	)
	if not expiry or expiry < now_datetime():
		return {"status": "expired"}

	if fields.get("bp_needs_password") and not password:
		return {"status": "password_required"}
	if fields.get("bp_needs_password") and len(password) < 8:
		frappe.throw("Password must be at least 8 characters long.")

	with bridge.sudo_as_administrator():
		user = frappe.get_doc("User", user_email)
		if fields.get("bp_needs_password"):
			user.new_password = password
		user.enabled = 1
		user.bp_activation_token = None
		user.bp_activation_expiry = None
		user.bp_invite_token = None
		user.bp_invite_expiry = None
		user.bp_needs_password = 0
		if user.bp_invite_status == "Pending":
			user.bp_invite_status = "Accepted"
		user.save(ignore_permissions=True)

	return {"status": "activated"}


def resend_activation(email: str) -> dict:
	if not bridge.user_exists(email):
		frappe.throw("No account found for this email.")
	company = bridge.get_user_company(email)
	token, expiry = _token(), now_datetime() + timedelta(hours=ACTIVATION_TTL_HOURS)
	bridge.set_user_fields(email, bp_activation_token=token, bp_activation_expiry=expiry)
	link = f"{_pwa_url()}/activate?token={token}"
	_send_email(
		email,
		"Activate your BuildPolaris account",
		f"<p><a href='{link}'>Activate account</a></p><p>Expires in {ACTIVATION_TTL_HOURS} hours.</p>",
	)
	return {"status": "sent", "company": company}


def dev_get_activation_token(email: str):
	fields = bridge.get_user_fields(email, ["bp_activation_token", "bp_invite_token"])
	print("activation:", fields.get("bp_activation_token"))
	print("invite:", fields.get("bp_invite_token"))
	print(
		"link:",
		f"{_pwa_url()}/activate?token={fields.get('bp_invite_token') or fields.get('bp_activation_token')}",
	)


# ---------------------------------------------------------------- Session (UC-03/UC-04)
def get_session_context() -> dict:
	if frappe.session.user == "Guest":
		frappe.throw("Not logged in", frappe.PermissionError)

	roles = frappe.get_roles(frappe.session.user)
	full_name = frappe.db.get_value("User", frappe.session.user, "full_name")
	company = bridge.get_user_company(frappe.session.user)
	persona = resolve_persona(roles)

	return {
		"user": frappe.session.user,
		"full_name": full_name,
		"roles": [r for r in roles if r in get_platform_role_names()],
		"persona": persona,
		"company": company,
		"is_admin": ADMIN_ROLE_NAME in roles,
	}


# ---------------------------------------------------------------- Guards
def require_tenant_member() -> str:
	if frappe.session.user == "Guest":
		frappe.throw("Not logged in", frappe.PermissionError)
	company = bridge.get_user_company(frappe.session.user)
	if not company:
		frappe.throw("No tenant associated with this user", frappe.PermissionError)
	return company


def require_admin() -> str:
	company = require_tenant_member()
	if ADMIN_ROLE_NAME not in frappe.get_roles(frappe.session.user):
		log_security_event(
			"UNAUTHORIZED_ADMIN_ACCESS",
			{
				"user": frappe.session.user,
				"company": company,
			},
		)
		frappe.throw("Admin role required", frappe.PermissionError)
	return company


def _require_same_tenant(target_email: str, company: str):
	target_company = bridge.get_user_company(target_email)
	if target_company != company:
		log_security_event(
			"CROSS_TENANT_ACCESS_ATTEMPT",
			{
				"user": frappe.session.user,
				"target": target_email,
				"tenant": company,
				"target_tenant": target_company,
			},
		)
		frappe.throw("Forbidden", frappe.PermissionError)


def _tenant_admin_count(company: str) -> int:
	users = frappe.get_all(
		"User", filters={"bp_company": company, "enabled": 1}, pluck="name", ignore_permissions=True
	)
	return sum(1 for u in users if ADMIN_ROLE_NAME in frappe.get_roles(u))


def _validate_roles(roles: list[str]):
	allowed = set(get_platform_role_names())
	invalid = set(roles) - allowed
	if invalid:
		frappe.throw(f"Invalid roles: {', '.join(invalid)}")
	if not roles:
		frappe.throw("At least one role must be selected.")


# ---------------------------------------------------------------- UC-02 / UC-07 (FR-1.2/1.7/1.8/1.10)
def available_roles() -> list[dict]:
	return PLATFORM_ROLES


def list_tenant_users() -> list[dict]:
	company = require_tenant_member()
	# FIX: ignore_permissions=True prevents 403 when BFF admin lists users
	rows = frappe.get_all(
		"User",
		filters={"bp_company": company},
		fields=["name", "email", "full_name", "enabled", "bp_invite_status"],
		order_by="creation asc",
		ignore_permissions=True,
	)
	platform_roles = set(get_platform_role_names())
	for row in rows:
		row["roles"] = [r for r in frappe.get_roles(row["name"]) if r in platform_roles]
	return rows


def invite_user(email: str, full_name: str, roles: list[str]) -> dict:
	company = require_admin()
	if not validate_email_address(email):
		frappe.throw("Invalid email address.")
	_validate_roles(roles)
	if bridge.user_exists(email):
		frappe.throw("A user with this email already exists.")

	bridge.create_platform_user(email, full_name, password=None, enabled=1, roles=roles)

	token, expiry = _token(), now_datetime() + timedelta(hours=INVITE_TTL_HOURS)
	bridge.set_user_fields(
		email,
		bp_company=company,
		bp_invite_token=token,
		bp_invite_expiry=expiry,
		bp_invite_status="Pending",
		bp_needs_password=1,
		bp_invited_by=frappe.session.user,
	)
	bridge.add_company_permission(email, company)

	link = f"{_pwa_url()}/activate?token={token}"
	_send_email(
		email,
		f"You have been invited to {company}",
		f"<p>{frappe.session.user} invited you to join <b>{company}</b> on BuildPolaris.</p>"
		f"<p><a href='{link}'>Set your password</a></p>"
		f"<p>This invite expires in {INVITE_TTL_HOURS} hours.</p>",
	)
	return {"status": "invited", "email": email}


def resend_invite(email: str) -> dict:
	company = require_admin()
	_require_same_tenant(email, company)
	token, expiry = _token(), now_datetime() + timedelta(hours=INVITE_TTL_HOURS)
	bridge.set_user_fields(email, bp_invite_token=token, bp_invite_expiry=expiry, bp_invite_status="Pending")
	link = f"{_pwa_url()}/activate?token={token}"
	_send_email(
		email,
		f"Invitation to {company} (refreshed)",
		f"<p><a href='{link}'>Set your password</a></p><p>Expires in {INVITE_TTL_HOURS} hours.</p>",
	)
	return {"status": "resent"}


def update_user_roles(email: str, roles: list[str]) -> dict:
	company = require_admin()
	_require_same_tenant(email, company)
	_validate_roles(roles)

	# FIX: Elevate privileges locally just to check roles of another user before writing
	with bridge.sudo_as_administrator():
		is_admin_now = ADMIN_ROLE_NAME in frappe.get_roles(email)
		if is_admin_now and ADMIN_ROLE_NAME not in roles and _tenant_admin_count(company) <= 1:
			frappe.throw("Cannot remove the last tenant Admin.")

	bridge.set_platform_roles(email, roles)
	return {"status": "updated"}


def set_user_enabled(email: str, enabled: bool) -> dict:
	company = require_admin()
	_require_same_tenant(email, company)

	if email == frappe.session.user and not enabled:
		frappe.throw("You cannot disable your own account.")

	# FIX: Elevate privileges locally just to check roles of another user before writing
	with bridge.sudo_as_administrator():
		if not enabled and ADMIN_ROLE_NAME in frappe.get_roles(email) and _tenant_admin_count(company) <= 1:
			frappe.throw("Cannot disable the last tenant Admin.")

	bridge.set_user_fields(email, enabled=1 if enabled else 0)
	return {"status": "enabled" if enabled else "disabled"}
