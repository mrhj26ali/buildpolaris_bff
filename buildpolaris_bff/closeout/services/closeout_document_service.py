"""FR-7.3/FR-7.4: O&M Manuals and Warranty Documents (Document Controller)
plus Consent of Surety and Contractor's Affidavit (Accounting) all live in
the one polymorphic Closeout Document doctype (ERD §3.5)."""
import frappe

from buildpolaris_bff.shared.exceptions import ValidationError
from buildpolaris_bff.shared.permissions import assert_project_permission, assert_role

VALID_CATEGORIES = {"OMManual", "Warranty", "ConsentOfSurety", "ContractorAffidavit"}


def add_document(closing_record, category, file, created_by=None):
	created_by = created_by or frappe.session.user
	closing_doc = frappe.get_doc("Closing Record", closing_record)
	assert_project_permission(closing_doc.project, ptype="write", user=created_by)
	assert_role("BuildPolaris Document Controller", "BuildPolaris Accounting", "BuildPolaris Admin", user=created_by)

	if category not in VALID_CATEGORIES:
		raise ValidationError(f"category must be one of {VALID_CATEGORIES}.")
	if not frappe.db.exists("File", file):
		raise ValidationError(f"File '{file}' does not exist.")

	doc = frappe.get_doc({
		"doctype": "Closeout Document",
		"closing_record": closing_record,
		"category": category,
		"file": file,
	})
	doc.insert()
	return doc.as_dict()


def list_documents(closing_record: str, user: str | None = None):
	closing_doc = frappe.get_doc("Closing Record", closing_record)
	assert_project_permission(closing_doc.project, ptype="read", user=user)
	return frappe.get_all("Closeout Document", filters={"closing_record": closing_record},
	                       fields=["name", "category", "file"])
