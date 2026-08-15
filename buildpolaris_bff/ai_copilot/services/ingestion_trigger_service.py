"""
File -> citable chunk (FR-8.10, UC-8.4, Flowcharts §5). Wired via
hooks.doc_events["File"]["after_insert"]. Only allow-listed source
DocTypes trigger ingestion - a File attached anywhere else is left alone.

Idempotent by content_hash (a re-upload of identical bytes is a no-op,
never a duplicate chunk set). Status is always visible on AI Document Index,
never silent - a failed extraction is flagged with a reason, never indexed
as empty content that could later be cited as if it existed (FR-8.10).

Implementation note vs. ARCH's "signed reference": rather than standing up
a separate signed-URL callback subsystem for buildpolaris_ai to fetch the
file back through, the BFF reads the file content itself and sends it
directly (base64) in the /ingest request body over the same authenticated
service-to-service channel. One fewer moving part for a single internal
consumer - the same "don't over-engineer for one consumer" call ARCH
itself makes deferring OAuth 2.1 (§4.4).
"""
import base64
import hashlib

import frappe
from frappe.utils import now_datetime

from buildpolaris_bff.shared.exceptions import AISidecarUnavailableError
from buildpolaris_bff.shared.security_log import get_trace_id, log_structured

ELIGIBLE_SOURCE_DOCTYPES = {"Commitment", "Submittal Package", "RFI"}

# Rows stuck Queued/Failed longer than this are re-enqueued by
# retry_failed_ingestion.run() (hourly, hooks.scheduler_events).
RETRY_THRESHOLD_MINUTES = 15


def on_file_after_insert(doc, method=None):
	"""hooks.doc_events["File"]["after_insert"]."""
	if doc.attached_to_doctype not in ELIGIBLE_SOURCE_DOCTYPES or not doc.attached_to_name:
		return

	try:
		content = doc.get_content()
	except Exception:
		log_structured("INGESTION_UNREADABLE_FILE", {"file": doc.name})
		return
	if not content:
		return

	content_hash = hashlib.sha256(content if isinstance(content, bytes) else content.encode("utf-8")).hexdigest()

	existing = frappe.db.get_value(
		"AI Document Index", {"file": doc.name, "content_hash": content_hash}, "name"
	)
	if existing:
		log_structured("INGESTION_IDEMPOTENT_SKIP", {"file": doc.name, "content_hash": content_hash})
		return  # No-op - idempotent, no duplicate chunks (FR-8.10).

	prior_for_file = frappe.db.get_value("AI Document Index", {"file": doc.name}, "name")
	if prior_for_file:
		index_doc = frappe.get_doc("AI Document Index", prior_for_file)
		index_doc.content_hash = content_hash
		index_doc.status = "Queued"
		index_doc.status_detail = None
		index_doc.save(ignore_permissions=True)
	else:
		index_doc = frappe.get_doc({
			"doctype": "AI Document Index",
			"file": doc.name,
			"source_doctype": doc.attached_to_doctype,
			"source_name": doc.attached_to_name,
			"content_hash": content_hash,
			"status": "Queued",
		}).insert(ignore_permissions=True)

	frappe.enqueue(
		"buildpolaris_bff.ai_copilot.services.ingestion_trigger_service.run_ingestion_job",
		queue="long", enqueue_after_commit=True,
		ai_document_index=index_doc.name, trace_id=get_trace_id(),
	)


def run_ingestion_job(ai_document_index: str, trace_id: str | None = None):
	"""Background job (Redis/RQ, ARCH §1.1: no message broker - a plain
	enqueued job)."""
	index_doc = frappe.get_doc("AI Document Index", ai_document_index)
	index_doc.status = "Processing"
	index_doc.save(ignore_permissions=True)
	frappe.db.commit()

	try:
		file_doc = frappe.get_doc("File", index_doc.file)
		content = file_doc.get_content()
		project = frappe.db.get_value(index_doc.source_doctype, index_doc.source_name, "project")
		company = frappe.db.get_value("Project", project, "company") if project else None

		result = _call_ai_sidecar("/ingest", {
			"file_id": index_doc.file,
			"source_doctype": index_doc.source_doctype,
			"source_name": index_doc.source_name,
			"content_hash": index_doc.content_hash,
			"company": company,
			"project": project,
			"file_name": file_doc.file_name,
			"content_b64": base64.b64encode(content if isinstance(content, bytes) else content.encode("utf-8")).decode("ascii"),
			"trace_id": trace_id or get_trace_id(),
		})

		if result.get("status") == "Indexed":
			index_doc.status = "Indexed"
			index_doc.chunk_count = result.get("chunk_count") or 0
			index_doc.model_version = result.get("model_version")
			index_doc.status_detail = None
			index_doc.last_indexed_at = now_datetime()
		else:
			# e.g. scanned/image-only with no extractable text layer -
			# stated explicitly, never silently indexed as empty (FR-8.10).
			index_doc.status = "Failed"
			index_doc.status_detail = result.get("status_detail") or "buildpolaris_ai reported no extractable content."
		index_doc.save(ignore_permissions=True)

	except AISidecarUnavailableError:
		# Sidecar down - revert to Queued so the hourly retry picks it back
		# up (NFR-SCALE.5: never blocks the rest of the platform).
		index_doc.status = "Queued"
		index_doc.save(ignore_permissions=True)
	except Exception:
		index_doc.status = "Failed"
		index_doc.status_detail = "Internal ingestion error - see Error Log for trace."
		index_doc.save(ignore_permissions=True)
		frappe.log_error(title=f"Ingestion failed for {ai_document_index}", message=frappe.get_traceback())
	finally:
		frappe.db.commit()


def _call_ai_sidecar(path: str, json_body: dict) -> dict:
	base_url = frappe.conf.get("buildpolaris_ai_base_url")
	if not base_url:
		raise AISidecarUnavailableError("buildpolaris_ai_base_url is not configured in site_config.json.")

	api_key = frappe.conf.get("buildpolaris_ai_service_api_key")
	api_secret = frappe.conf.get("buildpolaris_ai_service_api_secret")

	import requests
	try:
		response = requests.post(
			f"{base_url.rstrip('/')}{path}",
			json=json_body,
			headers={
				"Authorization": f"token {api_key}:{api_secret}" if api_key else "",
				"X-BP-Trace-Id": json_body.get("trace_id") or get_trace_id(),
			},
			timeout=120,  # extraction/embedding can legitimately take longer than a chat turn
		)
		response.raise_for_status()
		return response.json()
	except Exception as exc:
		raise AISidecarUnavailableError(str(exc))
