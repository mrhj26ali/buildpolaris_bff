"""FR-7.3: Lien Waivers collected per payment (Accounting). Subject to
NFR-RETAIN.1's extended retention period - never a delete endpoint exposed
for this doctype."""
import frappe

from buildpolaris_bff.shared.exceptions import ValidationError
from buildpolaris_bff.shared.permissions import assert_project_permission, assert_role

VALID_TYPES = {"Conditional", "Unconditional", "Partial", "Final"}


def add_lien_waiver(closing_record, supplier, file, type, pay_application=None, created_by=None):
	created_by = created_by or frappe.session.user
	closing_doc = frappe.get_doc("Closing Record", closing_record)
	assert_project_permission(closing_doc.project, ptype="write", user=created_by)
	assert_role("BuildPolaris Accounting", "BuildPolaris Admin", user=created_by)

	if type not in VALID_TYPES:
		raise ValidationError(f"type must be one of {VALID_TYPES}.")
	if not frappe.db.exists("File", file):
		raise ValidationError(f"File '{file}' does not exist.")

	doc = frappe.get_doc({
		"doctype": "Lien Waiver",
		"naming_series": "LW-.YYYY.-.#####",
		"closing_record": closing_record,
		"supplier": supplier,
		"pay_application": pay_application,
		"type": type,
		"file": file,
	})
	doc.insert()
	return doc.as_dict()


def list_lien_waivers(closing_record: str, user: str | None = None):
	closing_doc = frappe.get_doc("Closing Record", closing_record)
	assert_project_permission(closing_doc.project, ptype="read", user=user)
	return frappe.get_all("Lien Waiver", filters={"closing_record": closing_record},
	                       fields=["name", "supplier", "pay_application", "type"])
