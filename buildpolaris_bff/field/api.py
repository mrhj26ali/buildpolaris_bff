"""Field Execution - HTTP adapters only (NFR-MAINT.1). sync_offline_write
is the single REST entrypoint the PWA's outbox replays against
(Idempotency-Key = local_uuid, per ARCH §4.1)."""
import frappe

from buildpolaris_bff.shared.api_envelope import success
from buildpolaris_bff.field.services import (
	daily_log_service,
	jsa_service,
	media_capture_service,
	punch_list_service,
	safety_incident_service,
)


@frappe.whitelist()
def sync_offline_write(doctype, payload, local_uuid, idempotency_key=None):
	"""FR-6.5: the PWA outbox replay endpoint. Re-validates and applies a
	single queued write via shared/offline_sync_service.py - never a bypass
	of server-side rules just because the write happened offline."""
	if isinstance(payload, str):
		payload = frappe.parse_json(payload)
	from buildpolaris_bff.shared.offline_sync_service import apply_offline_write
	return success(apply_offline_write(doctype, payload, local_uuid, idempotency_key))


@frappe.whitelist()
def create_daily_log(project, log_date, weather=None, notes=None, labor=None, equipment=None, media=None):
	if isinstance(labor, str):
		labor = frappe.parse_json(labor)
	if isinstance(equipment, str):
		equipment = frappe.parse_json(equipment)
	if isinstance(media, str):
		media = frappe.parse_json(media)
	return success(daily_log_service.create_daily_log(project, log_date, weather, notes, labor, equipment, media))


@frappe.whitelist()
def list_daily_logs(project):
	return success(daily_log_service.list_daily_logs(project))


@frappe.whitelist()
def create_jsa(project, jsa_date, crew, hazards):
	if isinstance(hazards, str):
		hazards = frappe.parse_json(hazards)
	return success(jsa_service.create_jsa(project, jsa_date, crew, hazards))


@frappe.whitelist()
def list_jsas(project):
	return success(jsa_service.list_jsas(project))


@frappe.whitelist()
def create_incident(project, incident_date, severity, narrative, involved_persons=None, media=None):
	if isinstance(involved_persons, str):
		involved_persons = frappe.parse_json(involved_persons)
	if isinstance(media, str):
		media = frappe.parse_json(media)
	return success(safety_incident_service.create_incident(
		project, incident_date, severity, narrative, involved_persons, media
	))


@frappe.whitelist()
def list_incidents(project):
	return success(safety_incident_service.list_incidents(project))


@frappe.whitelist()
def export_incidents_for_regulatory_reporting(project, from_date, to_date):
	return success(safety_incident_service.export_for_regulatory_reporting(project, from_date, to_date))


@frappe.whitelist()
def create_punch_item(project, location, description, assigned_to=None, rfi=None):
	return success(punch_list_service.create_punch_item(project, location, description, assigned_to, rfi))


@frappe.whitelist()
def assign_punch_item(punch_item, assigned_to):
	return success(punch_list_service.assign_punch_item(punch_item, assigned_to))


@frappe.whitelist()
def close_punch_item(punch_item):
	return success(punch_list_service.close_punch_item(punch_item))


@frappe.whitelist()
def list_punch_items(project, status=None):
	return success(punch_list_service.list_punch_items(project, status))


@frappe.whitelist()
def delete_media_capture(parent_doctype, parent_name, row_name):
	return success(media_capture_service.delete_media_capture(parent_doctype, parent_name, row_name))
