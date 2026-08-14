"""Action Items, optionally linked to Meeting Minutes (FR-4.4). Closing is
allowed for the assignee OR a PM/Admin - not gated purely by DocType Role
permission, since a Subcontractor assignee legitimately needs to close
their own item without a blanket write grant on the doctype."""
import frappe

from buildpolaris_bff.shared.exceptions import PermissionDeniedError
from buildpolaris_bff.shared.permissions import assert_project_permission, has_any_role


def create_action_item(project, description, assignee, due_date, minutes=None, created_by=None):
	created_by = created_by or frappe.session.user
	assert_project_permission(project, ptype="write", user=created_by)

	doc = frappe.get_doc({
		"doctype": "Action Item",
		"naming_series": "AI-.YYYY.-.#####",
		"project": project,
		"minutes": minutes,
		"description": description,
		"assignee": assignee,
		"due_date": due_date,
		"status": "Open",
	})
	doc.insert()
	return doc.as_dict()


def close_action_item(action_item: str, closed_by: str | None = None):
	closed_by = closed_by or frappe.session.user
	doc = frappe.get_doc("Action Item", action_item)
	assert_project_permission(doc.project, ptype="read", user=closed_by)

	if closed_by != doc.assignee and not has_any_role(
		"BuildPolaris Project Manager", "BuildPolaris Admin", user=closed_by
	):
		raise PermissionDeniedError("Only the assignee or a PM/Admin can close this Action Item.")

	doc.status = "Done"
	doc.save(ignore_permissions=True)
	return doc.as_dict()


def list_action_items(project: str, status: str | None = None, user: str | None = None):
	assert_project_permission(project, ptype="read", user=user)
	filters = {"project": project}
	if status:
		filters["status"] = status
	return frappe.get_all("Action Item", filters=filters,
	                       fields=["name", "description", "assignee", "due_date", "status"],
	                       order_by="due_date asc")
