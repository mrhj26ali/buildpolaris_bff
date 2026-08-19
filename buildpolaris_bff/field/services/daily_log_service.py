"""FR-6.1: Site Superintendent submits a Daily Log (weather, labor,
equipment, notes) with attached photos. Also the offline-sync target for
the 'Daily Log' collection (FR-6.5, dispatched via
shared/offline_sync_service.py)."""
import frappe

from buildpolaris_bff.shared.permissions import assert_project_permission, assert_role


def create_daily_log(project, log_date, weather=None, notes=None, labor=None, equipment=None,
                      media=None, submitted_by=None):
	"""labor: [{trade, headcount, hours}]; equipment: [{equipment, hours_used}];
	media: [{file, latitude, longitude, captured_at}] (FR-6.6, see
	media_capture_service for EXIF fallback extraction)."""
	submitted_by = submitted_by or frappe.session.user
	assert_project_permission(project, ptype="read", user=submitted_by)
	assert_role("BuildPolaris Site Superintendent", "BuildPolaris Admin", user=submitted_by)

	doc = frappe.get_doc({
		"doctype": "Daily Log",
		"naming_series": "DL-.YYYY.-.#####",
		"project": project,
		"log_date": log_date,
		"submitted_by": submitted_by,
		"weather": weather,
		"notes": notes,
	})
	for line in (labor or []):
		doc.append("labor", {
			"trade": line.get("trade"), "headcount": line.get("headcount"), "hours": line.get("hours"),
		})
	for line in (equipment or []):
		doc.append("equipment", {
			"equipment": line.get("equipment"), "hours_used": line.get("hours_used"),
		})
	doc.insert()

	if media:
		from buildpolaris_bff.field.services.media_capture_service import add_media_capture
		for m in media:
			add_media_capture("Daily Log", doc.name, m.get("file"), m.get("latitude"),
			                   m.get("longitude"), m.get("captured_at"), added_by=submitted_by)

	return doc.as_dict()


def apply_offline_write(payload: dict, local_uuid: str) -> dict:
	"""Dispatched by shared/offline_sync_service.py. Field names match the
	RxDB 'daily_logs' collection 1:1 (ERD §3.4 design note) - no
	translation layer that could silently drop a field."""
	doc = create_daily_log(
		project=payload.get("project"),
		log_date=payload.get("log_date"),
		weather=payload.get("weather"),
		notes=payload.get("notes"),
		labor=payload.get("labor") or [],
		equipment=payload.get("equipment") or [],
		media=payload.get("media") or [],
		submitted_by=payload.get("submitted_by"),
	)
	return {"server_id": doc["name"], "sync_status": "synced"}


def list_daily_logs(project: str, user: str | None = None):
	assert_project_permission(project, ptype="read", user=user)
	return frappe.get_all("Daily Log", filters={"project": project},
	                       fields=["name", "log_date", "submitted_by", "weather"],
	                       order_by="log_date desc")
