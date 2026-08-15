"""FR-7.1: PM opens a Closing Record once a Project is physically complete.
Also NFR-RETAIN.1's informational retention-expiry lookup."""
import frappe
from frappe.utils import add_years, now_datetime

from buildpolaris_bff.shared.exceptions import ValidationError
from buildpolaris_bff.shared.permissions import assert_project_permission, assert_role


def open_closing_record(project, created_by=None):
	created_by = created_by or frappe.session.user
	assert_project_permission(project, ptype="write", user=created_by)
	assert_role("BuildPolaris Project Manager", "BuildPolaris Admin", user=created_by)

	existing = frappe.db.exists("Closing Record", {"project": project, "status": ["!=", "Finalized"]})
	if existing:
		raise ValidationError(f"Project already has an open Closing Record: {existing}.")

	doc = frappe.get_doc({
		"doctype": "Closing Record",
		"naming_series": "CLOSE-.YYYY.-.#####",
		"project": project,
		"status": "Open",
		"opened_at": now_datetime(),
	})
	doc.insert()
	return doc.as_dict()


def get_closing_record(project: str, user: str | None = None):
	assert_project_permission(project, ptype="read", user=user)
	return frappe.db.get_value(
		"Closing Record", {"project": project}, ["name", "status", "opened_at"], as_dict=True
	)


def get_retention_expiry(closing_record: str, user: str | None = None) -> dict:
	"""NFR-RETAIN.1: informational only. The platform NEVER auto-deletes on
	this date (NFR-RETAIN.2/.3) - a human-approved deletion process, outside
	this function's scope entirely, is the only path that could ever act on it."""
	doc = frappe.get_doc("Closing Record", closing_record)
	assert_project_permission(doc.project, ptype="read", user=user)

	company = frappe.db.get_value("Project", doc.project, "company")
	retention_years = frappe.db.get_value("Company", company, "bp_legal_retention_years") or 7
	return {
		"retention_years": retention_years,
		"retain_until": add_years(doc.opened_at, retention_years),
		"note": "Informational only - no automated deletion is ever triggered by this date (NFR-RETAIN.2).",
	}
