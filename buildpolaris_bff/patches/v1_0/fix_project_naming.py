import frappe


def execute():
	"""ERPNext v16's native Project DocType ships with
	`autoname: "field:project_name"` - the record's primary key IS its
	project_name, which must then be globally unique across the ENTIRE
	site. That's a reasonable default for a single-tenant ERPNext
	install, but BuildPolaris's own architecture (ARCH §1: "MariaDB - ONE
	system of record") deliberately hosts multiple Company tenants on one
	shared site - two different tenants both naming a project "Riverside
	Complex" would collide on insert with a raw DuplicateEntryError
	instead of a clear, actionable error.

	Switches Project's primary key to an auto-generated naming series
	(PROJ-.YYYY.-.#####), consistent with every other BuildPolaris
	DocType's naming convention (Pay Application uses PA-.YYYY.-.#####,
	etc.) - project_name remains a required, human-readable label field,
	it's just no longer required to be unique.

	Idempotent - frappe.make_property_setter overwrites any existing
	Property Setter for the same (doctype, fieldname, property) rather
	than duplicating one on re-run.
	"""
	frappe.make_property_setter(
		{
			"doctype": "Project",
			"fieldname": None,
			"property": "autoname",
			"value": "PROJ-.YYYY.-.#####",
			"property_type": "Data",
		},
		validate_fields_for_doctype=False,
	)
