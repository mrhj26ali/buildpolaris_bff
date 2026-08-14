"""FR-5.1: Document Controller registers Drawings with versioned Revisions
that supersede rather than overwrite prior versions."""
import frappe

from buildpolaris_bff.shared.permissions import assert_project_permission, assert_role


def register_drawing(project, drawing_number, title, discipline=None, created_by=None):
	created_by = created_by or frappe.session.user
	assert_project_permission(project, ptype="write", user=created_by)
	assert_role("BuildPolaris Document Controller", "BuildPolaris Admin", user=created_by)

	doc = frappe.get_doc({
		"doctype": "Drawing",
		"naming_series": "DWG-.YYYY.-.#####",
		"project": project,
		"drawing_number": drawing_number,
		"title": title,
		"discipline": discipline,
	})
	doc.insert()
	return doc.as_dict()


def list_drawings(project: str, user: str | None = None):
	assert_project_permission(project, ptype="read", user=user)
	return frappe.get_all("Drawing", filters={"project": project},
	                       fields=["name", "drawing_number", "title", "discipline"])
