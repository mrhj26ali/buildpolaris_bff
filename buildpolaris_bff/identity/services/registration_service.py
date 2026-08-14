"""
FR-1.1: prospect self-registration -> isolated ERPNext Company + disabled
Admin account pending activation via a single-use, hashed, time-boxed token.
"""
import frappe
from frappe.utils import add_to_date, now_datetime

from buildpolaris_bff.shared.crypto_utils import generate_secure_token, verify_token
from buildpolaris_bff.shared.exceptions import ValidationError
from buildpolaris_bff.shared.security_log import log_security_event

ACTIVATION_TOKEN_TTL_HOURS = 48


def register_tenant(company_name: str, admin_email: str, admin_full_name: str,
                     country: str = "United States", default_currency: str = "USD") -> dict:
	"""Creates an isolated ERPNext Company (locale-aware CoA/currency/fiscal
	year sourced from ERPNext, not a hand-built onboarding form) and a
	disabled Admin User pending activation.

	Returns {"company": ..., "user": ..., "activation_token": <RAW, deliver
	once>}. The raw token is NEVER persisted - only its hash is (NFR-SEC.3).
	"""
	if frappe.db.exists("Company", company_name):
		raise ValidationError(f"A tenant named '{company_name}' already exists.")

	if frappe.db.exists("User", admin_email):
		raise ValidationError(f"A user with email '{admin_email}' already exists.")

	company = frappe.new_doc("Company")
	company.company_name = company_name
	company.default_currency = default_currency
	company.country = country
	company.insert(ignore_permissions=True)

	user = frappe.new_doc("User")
	user.email = admin_email
	user.first_name = admin_full_name
	user.enabled = 0  # disabled pending activation
	user.send_welcome_email = 0
	user.append("roles", {"role": "BuildPolaris Admin"})
	user.flags.ignore_password_policy = True
	user.insert(ignore_permissions=True)

	if frappe.db.has_column("User", "bp_company"):
		frappe.db.set_value("User", user.name, "bp_company", company.name)
		frappe.db.set_value("User", user.name, "bp_invite_status", "Pending")
		frappe.db.set_value("User", user.name, "bp_needs_password", 1)

	raw_token, hashed_token = generate_secure_token()
	frappe.get_doc({
		"doctype": "Account Activation Token",
		"user": user.name,
		"company": company.name,
		"purpose": "Activation",
		"token_hash": hashed_token,
		"expires_at": add_to_date(now_datetime(), hours=ACTIVATION_TOKEN_TTL_HOURS),
	}).insert(ignore_permissions=True)

	log_security_event("TENANT_REGISTERED", {"company": company.name, "admin_user": user.name})
	frappe.db.commit()

	return {"company": company.name, "user": user.name, "activation_token": raw_token}


def activate_account(user: str, raw_token: str, new_password: str) -> dict:
	"""Verifies the single-use, hashed activation token (constant-time
	comparison, NFR-SEC.3) and enables the account with the chosen password."""
	token_doc = _find_valid_token(user, raw_token, purpose="Activation")

	frappe.db.set_value("User", user, "enabled", 1)
	if frappe.db.has_column("User", "bp_invite_status"):
		frappe.db.set_value("User", user, "bp_invite_status", "Accepted")
		frappe.db.set_value("User", user, "bp_needs_password", 0)

	user_doc = frappe.get_doc("User", user)
	user_doc.new_password = new_password
	user_doc.flags.ignore_password_policy = False
	user_doc.save(ignore_permissions=True)

	token_doc.mark_used()
	log_security_event("ACCOUNT_ACTIVATED", {"user": user})
	frappe.db.commit()
	return {"user": user, "status": "activated"}


def _find_valid_token(user: str, raw_token: str, purpose: str):
	candidates = frappe.get_all(
		"Account Activation Token",
		filters={"user": user, "purpose": purpose, "used_at": ["is", "not set"]},
		fields=["name"],
		ignore_permissions=True,
	)
	for c in candidates:
		token_doc = frappe.get_doc("Account Activation Token", c.name)
		if verify_token(raw_token, token_doc.token_hash):
			if token_doc.is_expired():
				log_security_event("EXPIRED_TOKEN_USE_ATTEMPT", {"user": user, "purpose": purpose})
				raise ValidationError("Activation token has expired.")
			return token_doc

	log_security_event("INVALID_TOKEN_USE_ATTEMPT", {"user": user, "purpose": purpose})
	raise ValidationError("Invalid or already-used activation token.")
