from contextlib import contextmanager

import frappe


@contextmanager
def sudo_as_administrator():
	original_user = frappe.session.user
	try:
		frappe.set_user("Administrator")
		yield
	finally:
		frappe.set_user(original_user)


def company_exists(company_name: str) -> bool:
	return bool(frappe.db.exists("Company", company_name))


def user_exists(email: str) -> bool:
	return bool(frappe.db.exists("User", email))


def create_company(company_name: str, abbr: str, country: str, currency: str) -> str:
	"""FR-1.9 — tenant provisioning via native Company (locale-aware CoA template)."""
	if company_exists(company_name):
		frappe.throw(f"A company named '{company_name}' already exists.", frappe.DuplicateEntryError)

	with sudo_as_administrator():
		company = frappe.new_doc("Company")
		company.company_name = company_name
		company.abbr = abbr
		company.country = country
		company.default_currency = currency
		company.insert(ignore_permissions=True)
		return company.name


def create_platform_user(email: str, full_name: str, password: str | None = None, enabled: int = 1, roles: list[str] | None = None) -> str:
	with sudo_as_administrator():
		user = frappe.new_doc("User")
		user.email = email
		user.first_name = full_name
		user.enabled = enabled
		user.send_welcome_email = 0  # PWA owns onboarding
		user.user_type = "System User"
		if password:
			user.new_password = password
			
		# Append roles BEFORE insert to satisfy ERPNext's native validation
		if roles:
			for role in roles:
				user.append("roles", {"role": role})
				
		user.insert(ignore_permissions=True)
		return user.name


def set_platform_roles(email: str, roles: list[str]):
	"""Replace the user's platform roles with the given list; keep non-platform roles."""
	from buildpolaris_bff.install import get_platform_role_names

	platform_roles = set(get_platform_role_names())
	with sudo_as_administrator():
		user = frappe.get_doc("User", email)
		kept = [r.role for r in user.roles if r.role not in platform_roles]
		user.set("roles", [{"role": r} for r in kept + list(roles)])
		user.save(ignore_permissions=True)


def set_user_fields(email: str, **fields):
	with sudo_as_administrator():
		frappe.db.set_value("User", email, fields)


def get_user_fields(email: str, fields: list[str]) -> dict:
	# FIX: Use get_all with ignore_permissions=True to safely bypass native User guards
	# WITHOUT mutating global session state (which breaks the whitelist registry on hot-reload)
	result = frappe.get_all(
		"User",
		filters={"name": email},
		fields=fields,
		limit=1,
		ignore_permissions=True
	)
	return result[0] if result else {}


def add_company_permission(email: str, company: str):
	"""FR-1.5 — native row-level isolation for the whole tenant."""
	from frappe.permissions import add_user_permission

	with sudo_as_administrator():
		add_user_permission(
			"Company", company, email,
			ignore_permissions=True
		)


def get_user_company(email: str) -> str | None:
	# FIX: Use get_all with ignore_permissions=True to safely bypass native User guards
	result = frappe.get_all(
		"User",
		filters={"name": email},
		fields=["bp_company"],
		limit=1,
		ignore_permissions=True
	)
	company = result[0].get("bp_company") if result else None
	
	if not company:
		perm_result = frappe.get_all(
			"User Permission",
			filters={"user": email, "allow": "Company"},
			fields=["for_value"],
			limit=1,
			ignore_permissions=True
		)
		company = perm_result[0].get("for_value") if perm_result else None
		
	return company