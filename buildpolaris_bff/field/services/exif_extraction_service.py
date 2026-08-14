"""
FR-6.6: extract EXIF/GPS metadata from an uploaded photo into queryable
fields (latitude, longitude, captured_at) at ingest time - never left
inside the binary blob for later retroactive extraction.

Best-effort: Pillow is an optional dependency (`pip install Pillow
--break-system-packages`). If it isn't installed, or the file has no EXIF
block (HEIC without a JPEG fallback, GPS stripped by the device), this
returns {} and callers fall back to client-supplied GPS - it never blocks
the upload.
"""
import frappe

try:
	from PIL import Image
	from PIL.ExifTags import GPSTAGS, TAGS
	_PIL_AVAILABLE = True
except ImportError:
	_PIL_AVAILABLE = False


def extract_exif(file_doc_name: str) -> dict:
	if not _PIL_AVAILABLE:
		return {}

	try:
		file_doc = frappe.get_doc("File", file_doc_name)
		file_path = file_doc.get_full_path()
		image = Image.open(file_path)
		exif_data = image._getexif()
	except Exception:
		return {}

	if not exif_data:
		return {}

	result = {}
	gps_info = {}
	for tag_id, value in exif_data.items():
		tag = TAGS.get(tag_id, tag_id)
		if tag == "GPSInfo":
			for gps_tag_id, gps_value in value.items():
				gps_info[GPSTAGS.get(gps_tag_id, gps_tag_id)] = gps_value
		elif tag == "DateTimeOriginal":
			result["captured_at"] = value

	if gps_info:
		lat = _to_degrees(gps_info.get("GPSLatitude"))
		lon = _to_degrees(gps_info.get("GPSLongitude"))
		if lat is not None and gps_info.get("GPSLatitudeRef") == "S":
			lat = -lat
		if lon is not None and gps_info.get("GPSLongitudeRef") == "W":
			lon = -lon
		if lat is not None:
			result["latitude"] = lat
		if lon is not None:
			result["longitude"] = lon

	return result


def _to_degrees(value):
	if not value:
		return None
	try:
		d, m, s = value
		return float(d) + float(m) / 60.0 + float(s) / 3600.0
	except Exception:
		return None
