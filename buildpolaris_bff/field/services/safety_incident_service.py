"""FR-6.3: any field user reports a Safety Incident with severity
classification. NFR-PRIV.1/.2: involved-person names are field-level
restricted to Safety Officer/Admin (enforced via DocType permlevel, not
computed here). NFR-AUD.4: exportable for regulatory (OSHA-class)
reporting. Also the offline-sync target for 'Safety Incident' (FR-6.5)."""
import frappe

from buildpolaris_bff.shared.permissions import assert_project_permission


def create_incident(project, incident_date, severity, narrative, involved_persons=None,
                     media=None, reported_by=None):
	"""involved_persons: [{person_name, role_on_site}] - any field user may
	report (FR-6.3); the field-level permlevel restriction on
	`involved_persons` governs who can later READ names, not who can create
	the incident."""
	reported_by = reported_by or frappe.session.user
	assert_project_permission(project, ptype="read", user=reported_by)

	valid_severities = {"Minor", "Recordable", "Lost-Time", "Fatality"}
	if severity not in valid_severities:
		from buildpolaris_bff.shared.exceptions import ValidationError
		raise ValidationError(f"severity must be one of {valid_severities}.")

	doc = frappe.get_doc({
		"doctype": "Safety Incident",
		"naming_series": "INC-.YYYY.-.#####",
		"project": project,
		"incident_date": incident_date,
		"severity": severity,
		"narrative": narrative,
		"reported_by": reported_by,
	})
	for p in (involved_persons or []):
		doc.append("involved_persons", {
			"person_name": p.get("person_name"), "role_on_site": p.get("role_on_site"),
		})
	doc.insert(ignore_permissions=True)  # permlevel-1 field write on create; role already asserted above

	if media:
		from buildpolaris_bff.field.services.media_capture_service import add_media_capture
		for m in media:
			add_media_capture("Safety Incident", doc.name, m.get("file"), m.get("latitude"),
			                   m.get("longitude"), m.get("captured_at"), added_by=reported_by)

	return doc.as_dict()


def apply_offline_write(payload: dict, local_uuid: str) -> dict:
	"""Dispatched by shared/offline_sync_service.py for the RxDB
	'safety_incidents' collection - field names match 1:1."""
	doc = create_incident(
		project=payload.get("project"),
		incident_date=payload.get("incident_date"),
		severity=payload.get("severity"),
		narrative=payload.get("narrative"),
		involved_persons=payload.get("involved_persons") or [],
		media=payload.get("media") or [],
		reported_by=payload.get("reported_by"),
	)
	return {"server_id": doc["name"], "sync_status": "synced"}


def list_incidents(project: str, user: str | None = None):
	assert_project_permission(project, ptype="read", user=user)
	# involved_persons is permlevel-1; frappe.get_all naturally omits fields
	# the caller's Role can't read at that permlevel.
	return frappe.get_all("Safety Incident", filters={"project": project},
	                       fields=["name", "incident_date", "severity", "reported_by"],
	                       order_by="incident_date desc")


def export_for_regulatory_reporting(project: str, from_date: str, to_date: str, user: str | None = None):
	"""NFR-AUD.4: severity + date fields map cleanly to OSHA-class
	recordkeeping without manual reformatting. Jurisdiction-specific export
	TEMPLATES (the actual government form) are explicitly future work per
	the NFR text - this returns the clean structured rows a template would
	consume."""
	assert_project_permission(project, ptype="read", user=user)
	return frappe.get_all(
		"Safety Incident",
		filters={"project": project, "incident_date": ["between", [from_date, to_date]]},
		fields=["name", "incident_date", "severity", "narrative", "reported_by"],
		order_by="incident_date asc",
	)
