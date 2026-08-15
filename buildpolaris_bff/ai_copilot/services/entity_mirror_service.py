"""
FR-8.2: a queryable entity/relationship layer (Projects <-> Tasks <-> RFIs
<-> Costs <-> People) mirrored into buildpolaris_ai's graph store (AGE)
for the copilot's hybrid retrieval (Flowcharts §4). Hook-driven, never
polled - each mirrored DocType's after_insert/on_update/on_trash enqueues a
small background job (ARCH §1.1: no message broker, just frappe.enqueue).

MIRROR_FIELD_MAP is deliberately narrow per doctype - only fields useful
for graph traversal/context, never free-text narrative fields. Safety
Incident in particular mirrors project/severity/status only, never the
narrative or involved-person names (NFR-PRIV.1/PRIV.2) - that detail stays
in MariaDB, readable only through the normal permission-checked API, never
copied into the AI sidecar's less-tightly-scoped derived store.
"""
import frappe

from buildpolaris_bff.shared.exceptions import AISidecarUnavailableError
from buildpolaris_bff.shared.security_log import get_trace_id, log_structured

MIRROR_FIELD_MAP = {
	"Task": ["project", "subject", "exp_start_date", "exp_end_date",
	         "is_critical", "total_float", "parent_task", "wbs_code"],
	"RFI": ["project", "subject", "status", "assigned_to", "due_date"],
	"Commitment": ["project", "cost_code", "supplier", "status", "revised_amount"],
	"Change Event": ["project", "commitment", "category", "status", "amount_delta"],
	"Punch List Item": ["project", "location", "status", "assigned_to", "rfi"],
	"Safety Incident": ["project", "severity", "incident_date"],
}


def mirror_hook(doc, method=None):
	"""Registered in hooks.doc_events for every doctype in MIRROR_FIELD_MAP,
	against after_insert / on_update / on_trash."""
	if doc.doctype not in MIRROR_FIELD_MAP:
		return
	event = "delete" if method == "on_trash" else "upsert"
	frappe.enqueue(
		"buildpolaris_bff.ai_copilot.services.entity_mirror_service.run_mirror_job",
		queue="short", enqueue_after_commit=True,
		doctype=doc.doctype, name=doc.name, event=event, trace_id=get_trace_id(),
	)


def run_mirror_job(doctype: str, name: str, event: str, trace_id: str | None = None):
	try:
		payload = {"doctype": doctype, "name": name, "event": event}
		if event == "upsert":
			fields = MIRROR_FIELD_MAP.get(doctype, [])
			data = frappe.db.get_value(doctype, name, fields, as_dict=True) if fields else None
			if not data:
				return  # Record vanished before the job ran - nothing to mirror.
			payload["fields"] = data
		_call_ai_sidecar("/entity-mirror", payload, trace_id)
		log_structured("ENTITY_MIRROR_OK", {"doctype": doctype, "name": name, "event": event})
	except AISidecarUnavailableError:
		# NFR-SCALE.5: the copilot's context will simply be a step stale
		# until the sidecar is back - never blocks the write that triggered
		# this job, since that write already committed before we got here.
		log_structured("ENTITY_MIRROR_SIDECAR_DOWN", {"doctype": doctype, "name": name})
	except Exception:
		frappe.log_error(title=f"Entity mirror failed for {doctype} {name}", message=frappe.get_traceback())


def _call_ai_sidecar(path: str, json_body: dict, trace_id: str | None = None) -> dict:
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
				"X-BP-Trace-Id": trace_id or get_trace_id(),
			},
			timeout=15,
		)
		response.raise_for_status()
		return response.json()
	except Exception as exc:
		raise AISidecarUnavailableError(str(exc))
