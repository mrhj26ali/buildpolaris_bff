"""FR-4.4: PM schedules recurring Meeting Series and records Meeting
Minutes with Action Items."""
import frappe

from buildpolaris_bff.shared.permissions import assert_project_permission, assert_role


def create_series(project, title, recurrence_rule=None, created_by=None):
	created_by = created_by or frappe.session.user
	assert_project_permission(project, ptype="write", user=created_by)
	assert_role("BuildPolaris Project Manager", "BuildPolaris Admin", user=created_by)

	doc = frappe.get_doc({
		"doctype": "Meeting Series",
		"naming_series": "MSER-.YYYY.-.#####",
		"project": project,
		"title": title,
		"recurrence_rule": recurrence_rule,
	})
	doc.insert()
	return doc.as_dict()


def record_minutes(series, occurred_at, notes, action_items=None, recorded_by=None):
	"""action_items: [{description, assignee, due_date}, ...] - created in
	the same call, matching FR-4.4's 'record Minutes WITH Action Items'."""
	recorded_by = recorded_by or frappe.session.user
	series_doc = frappe.get_doc("Meeting Series", series)
	assert_project_permission(series_doc.project, ptype="write", user=recorded_by)
	assert_role("BuildPolaris Project Manager", "BuildPolaris Admin", user=recorded_by)

	minutes_doc = frappe.get_doc({
		"doctype": "Meeting Minutes",
		"naming_series": "MIN-.YYYY.-.#####",
		"series": series,
		"occurred_at": occurred_at,
		"notes": notes,
	})
	minutes_doc.insert()

	from buildpolaris_bff.communications.services.action_item_service import create_action_item

	created_items = []
	for item in (action_items or []):
		created_items.append(create_action_item(
			project=series_doc.project,
			description=item.get("description"),
			assignee=item.get("assignee"),
			due_date=item.get("due_date"),
			minutes=minutes_doc.name,
			created_by=recorded_by,
		))

	result = minutes_doc.as_dict()
	result["action_items"] = created_items
	return result


def list_minutes(series: str, user: str | None = None):
	series_doc = frappe.get_doc("Meeting Series", series)
	assert_project_permission(series_doc.project, ptype="read", user=user)
	return frappe.get_all("Meeting Minutes", filters={"series": series},
	                       fields=["name", "occurred_at", "notes"], order_by="occurred_at desc")
