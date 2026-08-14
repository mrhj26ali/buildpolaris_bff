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
				frappe.db.set_value("DocType", doctype, "track_changes", 1)
