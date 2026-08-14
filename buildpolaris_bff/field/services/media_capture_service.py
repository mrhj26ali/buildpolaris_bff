"""
FR-6.6: photo capture geotags the entry from device GPS; EXIF/GPS metadata
is cross-checked/backfilled into queryable fields at ingest time. NFR-PRIV.2:
supports deletion of a specific capture without deleting its parent
Daily Log / Safety Incident record.
"""
import frappe

from buildpolaris_bff.shared.exceptions import ValidationError
from buildpolaris_bff.shared.permissions import assert_project_permission
from buildpolaris_bff.shared.security_log import log_security_event

_ALLOWED_PARENTS = {"Daily Log": "media", "Safety Incident": "media"}


def add_media_capture(parent_doctype, parent_name, file, latitude=None, longitude=None,
                       captured_at=None, added_by=None):
	added_by = added_by or frappe.session.user
	if parent_doctype not in _ALLOWED_PARENTS:
		raise ValidationError(f"Media Capture cannot attach to '{parent_doctype}'.")

	project = frappe.db.get_value(parent_doctype, parent_name, "project")
	assert_project_permission(project, ptype="write", user=added_by)

	if not frappe.db.exists("File", file):
		raise ValidationError(f"File '{file}' does not exist.")

	# Client-supplied GPS (device Geolocation API, captured at the moment
	# of the photo) takes precedence; EXIF is the fallback/cross-check
	# when the client didn't supply coordinates (FR-6.6).
	if latitude is None or longitude is None:
		from buildpolaris_bff.field.services.exif_extraction_service import extract_exif
		exif = extract_exif(file)
		latitude = latitude if latitude is not None else exif.get("latitude")
		longitude = longitude if longitude is not None else exif.get("longitude")
		captured_at = captured_at or exif.get("captured_at")

	doc = frappe.get_doc(parent_doctype, parent_name)
	fieldname = _ALLOWED_PARENTS[parent_doctype]
	doc.append(fieldname, {
		"file": file, "latitude": latitude, "longitude": longitude, "captured_at": captured_at,
	})
	doc.save()
	return doc.as_dict()


def delete_media_capture(parent_doctype, parent_name, row_name, deleted_by=None):
	"""NFR-PRIV.2: deletion of a specific capture without deleting the
	parent record. Pixel-level redaction (blurring faces while keeping the
	image) is a future image-processing enhancement; deletion satisfies the
	NFR's 'on request, without deleting the parent' requirement today."""
	deleted_by = deleted_by or frappe.session.user
	if parent_doctype not in _ALLOWED_PARENTS:
		raise ValidationError(f"Media Capture cannot attach to '{parent_doctype}'.")

	project = frappe.db.get_value(parent_doctype, parent_name, "project")
	assert_project_permission(project, ptype="write", user=deleted_by)

	doc = frappe.get_doc(parent_doctype, parent_name)
	fieldname = _ALLOWED_PARENTS[parent_doctype]
	rows = doc.get(fieldname) or []
	doc.set(fieldname, [r for r in rows if r.name != row_name])
	doc.save()

	log_security_event("MEDIA_CAPTURE_DELETED", {
		"parent_doctype": parent_doctype, "parent_name": parent_name,
		"row": row_name, "deleted_by": deleted_by,
	})
	return doc.as_dict()
