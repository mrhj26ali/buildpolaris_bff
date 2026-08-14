"""
FR-4.5: auto-escalate overdue RFIs and Action Items via a scheduled job
(hooks.py scheduler events), using Frappe's native ToDo/notification
engine - never a bespoke Escalation Log doctype (ARCH §2.4 correction).
"""
import frappe
from frappe.utils import today


def escalate_overdue_items():
	_escalate_rfis()
	_escalate_action_items()
	frappe.db.commit()


def _escalate_rfis():
	overdue = frappe.get_all(
		"RFI",
		filters={"status": ["not in", ["Closed", "Answered"]], "due_date": ["<", today()]},
		fields=["name", "project", "assigned_to", "subject"],
	)
	for rfi in overdue:
		frappe.db.set_value("RFI", rfi.name, "status", "Escalated")
		_notify_overdue("RFI", rfi.name, rfi.subject, rfi.project, rfi.assigned_to)


def _escalate_action_items():
	overdue = frappe.get_all(
		"Action Item",
		filters={"status": "Open", "due_date": ["<", today()]},
		fields=["name", "project", "assignee", "description"],
	)
	for item in overdue:
		frappe.db.set_value("Action Item", item.name, "status", "Overdue")
		_notify_overdue("Action Item", item.name, item.description, item.project, item.assignee)


def _notify_overdue(doctype, name, label, project, assignee):
	"""Idempotent: skip if an open ToDo already exists for this reference,
	so a re-run of the daily job never double-notifies."""
	already = frappe.db.exists("ToDo", {
		"reference_type": doctype, "reference_name": name, "status": "Open",
	})
	if already:
		return

	pm_users = frappe.get_all(
		"User Permission", filters={"allow": "Project", "for_value": project}, pluck="user",
	)
	recipients = set(pm_users)
	if assignee:
		recipients.add(assignee)

	for user in recipients:
		try:
			frappe.get_doc({
				"doctype": "ToDo",
				"allocated_to": user,
				"reference_type": doctype,
				"reference_name": name,
				"description": f"OVERDUE: {doctype} '{label}' ({name}) is past due and has been escalated.",
				"priority": "High",
			}).insert(ignore_permissions=True)
		except Exception:
			frappe.log_error(title=f"Escalation ToDo failed for {doctype} {name}", message=frappe.get_traceback())
