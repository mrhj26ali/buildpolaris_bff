"""FR-4.6: RFIs, Submittals, Transmittals, Action Items filterable and
searchable by Project, status, and assignee from one unified dashboard."""
import frappe

from buildpolaris_bff.shared.permissions import assert_project_permission


def search_communications(project, status=None, assignee=None, user=None):
	assert_project_permission(project, ptype="read", user=user)
	return {
		"rfis": _search_rfis(project, status, assignee),
		"submittals": _search_submittals(project, status),
		"transmittals": _search_transmittals(project),
		"action_items": _search_action_items(project, status, assignee),
	}


def _search_rfis(project, status, assignee):
	filters = {"project": project}
	if status:
		filters["status"] = status
	if assignee:
		filters["assigned_to"] = assignee
	return frappe.get_all("RFI", filters=filters,
	                       fields=["name", "subject", "status", "assigned_to", "due_date"])


def _search_submittals(project, status):
	filters = {"project": project}
	if status:
		filters["status"] = status
	return frappe.get_all("Submittal Package", filters=filters,
	                       fields=["name", "spec_section", "status"])


def _search_transmittals(project):
	return frappe.get_all("Transmittal", filters={"project": project},
	                       fields=["name", "sent_by", "sent_at", "method"])


def _search_action_items(project, status, assignee):
	filters = {"project": project}
	if status:
		filters["status"] = status
	if assignee:
		filters["assignee"] = assignee
	return frappe.get_all("Action Item", filters=filters,
	                       fields=["name", "description", "assignee", "due_date", "status"])
