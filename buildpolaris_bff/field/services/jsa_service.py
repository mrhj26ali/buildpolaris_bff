"""FR-6.2: Safety Officer completes a Job Safety Analysis enumerating
hazards and mitigations before work starts. Also the offline-sync target
for the 'JSA' collection (FR-6.5)."""
import frappe

from buildpolaris_bff.shared.exceptions import ValidationError
from buildpolaris_bff.shared.permissions import assert_project_permission, assert_role


def create_jsa(project, jsa_date, crew, hazards, prepared_by=None):
	"""hazards: [{hazard, mitigation}] - required, non-empty (FR-6.2)."""
	prepared_by = prepared_by or frappe.session.user
	assert_project_permission(project, ptype="read", user=prepared_by)
	assert_role("BuildPolaris Safety Officer", "BuildPolaris Admin", user=prepared_by)

	if not hazards:
		raise ValidationError("A JSA must enumerate at least one hazard and mitigation.")

	doc = frappe.get_doc({
		"doctype": "JSA",
		"naming_series": "JSA-.YYYY.-.#####",
		"project": project,
		"jsa_date": jsa_date,
		"crew": crew,
		"prepared_by": prepared_by,
	})
	for h in hazards:
		doc.append("hazards", {"hazard": h.get("hazard"), "mitigation": h.get("mitigation")})
	doc.insert()
	return doc.as_dict()


def apply_offline_write(payload: dict, local_uuid: str) -> dict:
	"""Dispatched by shared/offline_sync_service.py for the RxDB 'jsas'
	collection - field names match 1:1 (ERD §3.4 design note)."""
	doc = create_jsa(
		project=payload.get("project"),
		jsa_date=payload.get("jsa_date"),
		crew=payload.get("crew"),
		hazards=payload.get("hazards") or [],
		prepared_by=payload.get("prepared_by"),
	)
	return {"server_id": doc["name"], "sync_status": "synced"}


def list_jsas(project: str, user: str | None = None):
	assert_project_permission(project, ptype="read", user=user)
	return frappe.get_all("JSA", filters={"project": project},
	                       fields=["name", "jsa_date", "crew", "prepared_by"], order_by="jsa_date desc")
