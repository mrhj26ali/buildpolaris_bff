"""FR-4.1: any authorized user raises an RFI with assignment, a defined
response route, and watchers/CC recipients for visibility without
transferring ownership."""
import frappe

from buildpolaris_bff.shared.exceptions import ValidationError
from buildpolaris_bff.shared.permissions import assert_project_permission
from buildpolaris_bff.shared.security_log import log_security_event


def create_rfi(project, subject, question, assigned_to, due_date, response_route=None,
                watchers=None, created_by=None):
	created_by = created_by or frappe.session.user
	assert_project_permission(project, ptype="write", user=created_by)

	doc = frappe.get_doc({
		"doctype": "RFI",
		"naming_series": "RFI-.YYYY.-.#####",
		"project": project,
		"subject": subject,
		"question": question,
		"assigned_to": assigned_to,
		"due_date": due_date,
		"response_route": response_route,
		"status": "Open",
	})
	for watcher in (watchers or []):
		doc.append("watchers", {"user": watcher})
	doc.insert()
	return doc.as_dict()


def add_watcher(rfi: str, user: str, added_by: str | None = None):
	"""Watchers see the RFI without owning it (FR-4.1)."""
	added_by = added_by or frappe.session.user
	doc = frappe.get_doc("RFI", rfi)
	assert_project_permission(doc.project, ptype="read", user=added_by)

	if any(w.user == user for w in doc.watchers):
		return doc.as_dict()
	doc.append("watchers", {"user": user})
	doc.save()
	return doc.as_dict()


def answer_rfi(rfi: str, response: str, answered_by: str | None = None):
	answered_by = answered_by or frappe.session.user
	doc = frappe.get_doc("RFI", rfi)
	assert_project_permission(doc.project, ptype="write", user=answered_by)

	if doc.status not in ("Open", "Escalated"):
		raise ValidationError(f"RFI must be Open or Escalated to answer (current: {doc.status}).")

	doc.response = response
	doc.status = "Answered"
	doc.save()
	log_security_event("RFI_ANSWERED", {"rfi": rfi, "answered_by": answered_by})
	return doc.as_dict()


def close_rfi(rfi: str, closed_by: str | None = None):
	closed_by = closed_by or frappe.session.user
	doc = frappe.get_doc("RFI", rfi)
	assert_project_permission(doc.project, ptype="write", user=closed_by)

	if doc.status != "Answered":
		raise ValidationError(f"RFI must be Answered before closing (current: {doc.status}).")
	doc.status = "Closed"
	doc.save()
	return doc.as_dict()


def list_rfis(project: str, user: str | None = None):
	assert_project_permission(project, ptype="read", user=user)
	return frappe.get_all("RFI", filters={"project": project},
	                       fields=["name", "subject", "status", "assigned_to", "due_date"],
	                       order_by="due_date asc")
