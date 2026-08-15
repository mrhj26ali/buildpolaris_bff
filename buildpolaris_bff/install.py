import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

PLATFORM_ROLES = [
	{"role": "BuildPolaris Admin", "description": "Full tenant administration: users, roles, settings."},
	{"role": "BuildPolaris Owner", "description": "Read-heavy oversight: change-order approval, EVM visibility, closeout sign-off."},
	{"role": "BuildPolaris Project Manager", "description": "Owns schedule, budget, RFIs, change orders, EVM for assigned projects."},
	{"role": "BuildPolaris Accounting", "description": "Pay application approval, retainage, financial reconciliation."},
	{"role": "BuildPolaris Document Controller", "description": "Document control, drawing revisions, transmittals."},
	{"role": "BuildPolaris Site Superintendent", "description": "Field lead: daily logs, look-aheads, punch lists."},
	{"role": "BuildPolaris Safety Officer", "description": "Inspections, incident logging."},
	{"role": "BuildPolaris Subcontractor", "description": "Restricted scope: own submittals, RFIs, pay applications, punch resolution, closeout documents."},
]

AI_SERVICE_ACCOUNT_EMAIL = "ai-service@buildpolaris.internal"


def get_platform_role_names():
	return [r["role"] for r in PLATFORM_ROLES]


def after_install():
	_bootstrap()


def after_migrate():
	_bootstrap()


def _bootstrap():
	create_platform_roles()
	create_bp_custom_fields()
	enable_versioning()
	create_ai_service_account()
	frappe.db.commit()


def create_platform_roles():
	for r in PLATFORM_ROLES:
		if not frappe.db.exists("Role", r["role"]):
			role = frappe.new_doc("Role")
			role.role_name = r["role"]
			role.desk_access = 1  # required so users become System Users (REST access)
			role.description = r["description"]
			role.insert(ignore_permissions=True)


def create_bp_custom_fields():
	"""BuildPolaris-specific fields on the native User DocType: tenant
	linkage and invite-lifecycle status only. Single-use secrets themselves
	live in the 'Account Activation Token' doctype, hashed (NFR-SEC.3) -
	never as a raw-token field on User."""
	create_custom_fields(
		{
			"User": [
				{
					"fieldname": "bp_section",
					"fieldtype": "Section Break",
					"label": "BuildPolaris",
					"insert_after": "enabled",
				},
				{
					"fieldname": "bp_company",
					"fieldtype": "Link",
					"options": "Company",
					"label": "BuildPolaris Company",
					"read_only": 1,
				},
				{
					"fieldname": "bp_invite_status",
					"fieldtype": "Select",
					"options": "\nPending\nAccepted\nExpired",
					"label": "Invite Status",
					"read_only": 1,
				},
				{
					"fieldname": "bp_needs_password",
					"fieldtype": "Check",
					"label": "Needs Password",
					"read_only": 1,
				},
				{
					"fieldname": "bp_invited_by",
					"fieldtype": "Link",
					"options": "User",
					"label": "Invited By",
					"read_only": 1,
				},
			]
		},
		ignore_validate=True,
		update=True,
	)


def enable_versioning():
	from frappe.custom.doctype.property_setter.property_setter import make_property_setter

	for doctype in ("User", "Company"):
		existing = frappe.db.exists(
			"Property Setter",
			{"doc_type": doctype, "property": "track_changes", "field_name": ["is", "not set"]},
		)
		if not existing:
			try:
				make_property_setter(
					doctype, None, "track_changes", "1", "Check",
					for_doctype=True, validate_fields_for_doctype=False,
				)
			except Exception:
				frappe.db.set_value(doctype, doctype, "track_changes", 1)


def create_ai_service_account():
	"""ARCH §4.2: buildpolaris_ai authenticates to the BFF (Direction 2 -
	MCP tool calls, propose_agent_action) as this ONE dedicated User. It is
	granted ZERO BuildPolaris Roles - it is purely a transport identity.
	Actual authorization on every call comes from the Scope Assertion's
	asserted user, verified fresh each time (shared/scope_assertion.py) -
	this account itself can read or write nothing.

	Idempotent: running again after the API secret has already been
	generated does nothing (the secret is one-way hashed and not
	regenerated on every migrate, so it never silently rotates under a
	live buildpolaris_ai deployment).
	"""
	if frappe.db.exists("User", AI_SERVICE_ACCOUNT_EMAIL):
		return

	user = frappe.get_doc({
		"doctype": "User",
		"email": AI_SERVICE_ACCOUNT_EMAIL,
		"first_name": "BuildPolaris AI Service",
		"user_type": "System User",
		"send_welcome_email": 0,
		"enabled": 1,
		"roles": [],  # deliberately empty - see docstring
	})
	user.insert(ignore_permissions=True)

	# Remove default new-user Roles Frappe may attach (e.g. "All") so the
	# transport identity really does start with zero data access.
	user.reload()
	for row in list(user.roles):
		user.remove(row)
	user.save(ignore_permissions=True)

	api_secret = frappe.generate_hash(length=15)
	user.api_key = frappe.generate_hash(length=15)
	user.save(ignore_permissions=True)

	from frappe.utils.password import update_password
	update_password(user=user.name, pwd=api_secret, fieldname="api_secret", logout_all_sessions=False)

	# Shown exactly once - copy these into buildpolaris_ai's own
	# site/deployment config as buildpolaris_ai_service_api_key/secret
	# equivalents, then delete this file.
	try:
		import os
		note_path = frappe.get_site_path("private", "files", "buildpolaris_ai_service_credentials.txt")
		os.makedirs(os.path.dirname(note_path), exist_ok=True)
		with open(note_path, "w") as fh:
			fh.write(
				"BuildPolaris AI Service transport account (ARCH §4.2).\n"
				"Configure these on the buildpolaris_ai side, then DELETE this file.\n\n"
				f"api_key:    {user.api_key}\n"
				f"api_secret: {api_secret}\n"
			)
	except Exception:
		frappe.log_error(
			title="Could not write AI service credential file",
			message=f"api_key={user.api_key} (api_secret not logged - regenerate via bench console if lost).",
		)
