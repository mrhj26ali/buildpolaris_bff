"""
FR-1.1: prospect self-registration -> isolated ERPNext Company + disabled
Admin account pending activation via a single-use, hashed, time-boxed token.

Activation is deliberately TOKEN-ONLY (no `user` parameter) - the PWA's
ActivateAccountPage.tsx only ever has a `?token=` query param on the
activation link (there's no companion `user`/`email` param sent), and the
exact same page/flow is shared by both self-registration activation and
invited-user activation (see invitation_service.accept_invite, which
delegates to the same lookup below). A raw activation token is already
high-entropy (crypto_utils.generate_secure_token) and short-lived, so a
hash lookup across the (small, time-boxed) set of pending tokens rather
than a single indexed row is an acceptable, deliberate trade-off - this
is the same trust model most "magic link" auth flows use.
"""
import frappe
from frappe.utils import add_to_date, now_datetime

from buildpolaris_bff.shared.crypto_utils import generate_secure_token, verify_token
from buildpolaris_bff.shared.exceptions import ValidationError
from buildpolaris_bff.shared.security_log import log_security_event

ACTIVATION_TOKEN_TTL_HOURS = 48


def _resolve_country(country: str) -> str:
	"""buildpolaris_pwa's RegisterTenantPage.tsx has no visible country
	input - it silently sends a hardcoded default of 'US' (an ISO code),
	but Company.country is a Link to ERPNext's own Country doctype, whose
	primary key is the full name ('United States'), not the code. ERPNext
	ships every Country with a `code` field (lowercase ISO-3166 alpha-2),
	so this resolves either form rather than failing Link validation on
	the very first step of onboarding."""
	if frappe.db.exists("Country", country):
		return country
	resolved = frappe.db.get_value("Country", {"code": country.lower()}, "name")
	if resolved:
		return resolved
	raise ValidationError(f"'{country}' is not a recognized country.")


def register_tenant(company_name: str, admin_email: str, admin_first_name: str,
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
	company.country = _resolve_country(country)
	company.insert(ignore_permissions=True)

	user = frappe.new_doc("User")
	user.email = admin_email
	user.first_name = admin_first_name
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


def activate_account(raw_token: str, new_password: str) -> dict:
	"""Verifies a single-use, hashed activation/invite token (constant-time
	comparison, NFR-SEC.3) and enables the matching account with the chosen
	password. Handles BOTH self-registration ('Activation' purpose) and
	invited-user ('Invite' purpose) tokens - see module docstring."""
	token_doc = _find_valid_token_by_hash(raw_token, purposes=["Activation", "Invite"])
	user = token_doc.user

	frappe.db.set_value("User", user, "enabled", 1)
	if frappe.db.has_column("User", "bp_invite_status"):
		frappe.db.set_value("User", user, "bp_invite_status", "Accepted")
		frappe.db.set_value("User", user, "bp_needs_password", 0)

	user_doc = frappe.get_doc("User", user)
	user_doc.new_password = new_password
	user_doc.flags.ignore_password_policy = False
	user_doc.save(ignore_permissions=True)

	token_doc.mark_used()
	log_security_event("ACCOUNT_ACTIVATED", {"user": user, "purpose": token_doc.purpose})
	frappe.db.commit()
	return {"user": user, "status": "activated"}


def _find_valid_token_by_hash(raw_token: str, purposes: list[str]):
	"""Scans pending (unused, unexpired) tokens across the given purposes
	and returns the one whose hash matches raw_token, constant-time
	compared. There is deliberately no `user` filter - see module
	docstring for why."""
	candidates = frappe.get_all(
		"Account Activation Token",
		filters={"purpose": ["in", purposes], "used_at": ["is", "not set"]},
		fields=["name"],
		ignore_permissions=True,
	)
	for c in candidates:
		token_doc = frappe.get_doc("Account Activation Token", c.name)
		if verify_token(raw_token, token_doc.token_hash):
			if token_doc.is_expired():
				log_security_event("EXPIRED_TOKEN_USE_ATTEMPT", {"purpose": token_doc.purpose})
				raise ValidationError("This activation link has expired.")
			return token_doc

	log_security_event("INVALID_TOKEN_USE_ATTEMPT", {"purposes": purposes})
	raise ValidationError("Invalid or already-used activation link.")
