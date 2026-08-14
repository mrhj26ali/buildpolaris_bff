"""Communications - HTTP adapters only (NFR-MAINT.1)."""
import frappe

from buildpolaris_bff.shared.api_envelope import success
from buildpolaris_bff.communications.services import (
	action_item_service,
	dashboard_search_service,
	meeting_service,
	rfi_service,
	submittal_service,
	transmittal_service,
)


@frappe.whitelist()
def create_rfi(project, subject, question, assigned_to, due_date, response_route=None, watchers=None):
	if isinstance(watchers, str):
		watchers = frappe.parse_json(watchers)
	return success(rfi_service.create_rfi(project, subject, question, assigned_to, due_date, response_route, watchers))


@frappe.whitelist()
def add_watcher(rfi, user):
	return success(rfi_service.add_watcher(rfi, user))


@frappe.whitelist()
def answer_rfi(rfi, response):
	return success(rfi_service.answer_rfi(rfi, response))


@frappe.whitelist()
def close_rfi(rfi):
	return success(rfi_service.close_rfi(rfi))


@frappe.whitelist()
def list_rfis(project):
	return success(rfi_service.list_rfis(project))


@frappe.whitelist()
def create_submittal(project, spec_section, lines):
	if isinstance(lines, str):
		lines = frappe.parse_json(lines)
	return success(submittal_service.create_submittal(project, spec_section, lines))


@frappe.whitelist()
def review_submittal_line(submittal, line_name, status):
	return success(submittal_service.review_line(submittal, line_name, status))


@frappe.whitelist()
def list_submittals(project):
	return success(submittal_service.list_submittals(project))


@frappe.whitelist()
def issue_transmittal(project, method, recipients, files):
	if isinstance(recipients, str):
		recipients = frappe.parse_json(recipients)
	if isinstance(files, str):
		files = frappe.parse_json(files)
	return success(transmittal_service.issue_transmittal(project, method, recipients, files))


@frappe.whitelist()
def list_transmittals(project):
	return success(transmittal_service.list_transmittals(project))


@frappe.whitelist()
def create_meeting_series(project, title, recurrence_rule=None):
	return success(meeting_service.create_series(project, title, recurrence_rule))


@frappe.whitelist()
def record_minutes(series, occurred_at, notes, action_items=None):
	if isinstance(action_items, str):
		action_items = frappe.parse_json(action_items)
	return success(meeting_service.record_minutes(series, occurred_at, notes, action_items))


@frappe.whitelist()
def list_minutes(series):
	return success(meeting_service.list_minutes(series))


@frappe.whitelist()
def create_action_item(project, description, assignee, due_date, minutes=None):
	return success(action_item_service.create_action_item(project, description, assignee, due_date, minutes))


@frappe.whitelist()
def close_action_item(action_item):
	return success(action_item_service.close_action_item(action_item))


@frappe.whitelist()
def list_action_items(project, status=None):
	return success(action_item_service.list_action_items(project, status))


@frappe.whitelist()
def search_communications(project, status=None, assignee=None):
	return success(dashboard_search_service.search_communications(project, status, assignee))
