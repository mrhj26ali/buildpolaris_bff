"""FR-6.4: users create, assign, and close Punch List items, optionally
linked to an RFI. Also the offline-sync target for 'Punch List Item'
(FR-6.5) - the only field-execution doctype whose offline queue includes
UPDATE actions (assign/close) as well as creates, per ERD §5.4's
punch_items conflict-resolution note."""
import frappe
from frappe.utils import now_datetime

from buildpolaris_bff.shared.exceptions import ValidationError
from buildpolaris_bff.shared.permissions import assert_project_permission


def create_punch_item(project, location, description, assigned_to=None, rfi=None, created_by=None):
	created_by = created_by or frappe.session.user
	assert_project_permission(project, ptype="read", user=created_by)

	doc = frappe.get_doc({
		"doctype": "Punch List Item",
		"naming_series": "PLI-.YYYY.-.#####",
		"project": project,
		"location": location,
		"description": description,
		"assigned_to": assigned_to,
		"rfi": rfi,
		"status": "Open",
	})
	doc.insert()
	return doc.as_dict()


def assign_punch_item(punch_item: str, assigned_to: str, assigned_by: str | None = None):
	assigned_by = assigned_by or frappe.session.user
	doc = frappe.get_doc("Punch List Item", punch_item)
	assert_project_permission(doc.project, ptype="write", user=assigned_by)

	doc.assigned_to = assigned_to
	if doc.status == "Open":
		doc.status = "InProgress"
	doc.save()
	return doc.as_dict()


def close_punch_item(punch_item: str, closed_by: str | None = None):
	closed_by = closed_by or frappe.session.user
	doc = frappe.get_doc("Punch List Item", punch_item)
	assert_project_permission(doc.project, ptype="write", user=closed_by)

	doc.status = "Closed"
	doc.closed_at = now_datetime()
	doc.save()
	return doc.as_dict()


def apply_offline_write(payload: dict, local_uuid: str) -> dict:
	"""Dispatched by shared/offline_sync_service.py. payload['_action']:
	'create' (default) | 'assign' | 'close'. This is the one field-execution
	collection where a queued offline write can be an update, not just a
	create - matching ERD §5.4's punch_items conflict-resolution note
	(append-only vs. genuinely-conflicting field updates)."""
	action = payload.get("_action", "create")

	if action == "create":
		doc = create_punch_item(
			project=payload.get("project"), location=payload.get("location"),
			description=payload.get("description"), assigned_to=payload.get("assigned_to"),
			rfi=payload.get("rfi"), created_by=payload.get("created_by"),
		)
		return {"server_id": doc["name"], "sync_status": "synced"}

	server_id = payload.get("server_id") or payload.get("name")
	if not server_id:
		raise ValidationError("Update actions require a resolved server_id from the initial sync.")

	if action == "assign":
		doc = assign_punch_item(server_id, payload.get("assigned_to"), payload.get("assigned_by"))
	elif action == "close":
		doc = close_punch_item(server_id, payload.get("closed_by"))
	else:
		raise ValidationError(f"Unknown offline action '{action}' for Punch List Item.")

	return {"server_id": doc["name"], "sync_status": "synced"}


def list_punch_items(project: str, status: str | None = None, user: str | None = None):
	assert_project_permission(project, ptype="read", user=user)
	filters = {"project": project}
	if status:
		filters["status"] = status
	return frappe.get_all("Punch List Item", filters=filters,
	                       fields=["name", "location", "description", "assigned_to", "status", "rfi"],
	                       order_by="modified desc")
