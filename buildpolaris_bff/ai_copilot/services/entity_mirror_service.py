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

Wire contract: buildpolaris_ai's POST /graph/sync (gateway/routers/
graph_sync.py) expects a GraphSyncEvent body -
{company, project, event_type, source_doctype, source_name, properties,
event_seq} - not the {doctype, name, event, fields} shape a previous
version of this module sent to a path (/entity-mirror) that doesn't even
exist on the sidecar. event_seq is used there purely for stale/out-of-
order detection, so it needs to be genuinely monotonic per entity - the
DocType's own `modified` timestamp (microsecond epoch) already is one,
tied to the actual write that triggered this job, so it's used here
rather than introducing new state just to have a counter.
"""
import frappe

from buildpolaris_bff.shared.exceptions import AISidecarUnavailableError
from buildpolaris_bff.shared.scope_assertion import mint_scope_assertion
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
	against after_insert / on_update / on_trash. `method` here is the
	real Frappe hook name - preserved as-is downstream (not collapsed
	into a generic upsert/delete) since buildpolaris_ai's GraphSyncEvent
	schema's event_type is itself a Literal over those three names."""
	if doc.doctype not in MIRROR_FIELD_MAP:
		return
	frappe.enqueue(
		"buildpolaris_bff.ai_copilot.services.entity_mirror_service.run_mirror_job",
		queue="short", enqueue_after_commit=True,
		doctype=doc.doctype, name=doc.name, hook_method=method or "on_update",
		modified=str(doc.modified), user=frappe.session.user, trace_id=get_trace_id(),
	)


def run_mirror_job(doctype: str, name: str, hook_method: str, modified: str,
                    user: str | None = None, trace_id: str | None = None):
	try:
		fields = MIRROR_FIELD_MAP.get(doctype, [])
		data = frappe.db.get_value(doctype, name, fields, as_dict=True) if fields else None

		if method != "on_trash" and not data:
			return  # Record vanished before the job ran - nothing to mirror.

		project = (data or {}).get("project")
		acting_user = user or "Administrator"
		# mint_scope_assertion() derives `company` from the acting user's own
		# bp_company field (shared/scope_assertion.py), and buildpolaris_ai's
		# /graph/sync rejects the event outright if body.company !=
		# assertion.company. So the payload's company MUST come from the
		# same source, not from Project.company, or a real user with a
		# different bp_company than the Project's owning company (or the
		# Administrator account, which has no bp_company at all) would make
		# every mirror job fail scope-match.
		company = _resolve_company_for_user(acting_user)
		if not company:
			log_structured("ENTITY_MIRROR_SKIPPED_NO_COMPANY", {"doctype": doctype, "name": name, "user": acting_user})
			return

		payload = {
			"company": company,
			"project": project,
			"event_type": method,  # "after_insert" | "on_update" | "on_trash"
			"source_doctype": doctype,
			"source_name": name,
			"properties": data or {},
			"event_seq": _event_seq(modified),
		}
		scope_assertion = mint_scope_assertion(project=project, user=acting_user)
		_call_ai_sidecar("/graph/sync", payload, scope_assertion, trace_id)
		log_structured("ENTITY_MIRROR_OK", {"doctype": doctype, "name": name, "event_type": method})
	except AISidecarUnavailableError:
		# NFR-SCALE.5: the copilot's context will simply be a step stale
		# until the sidecar is back - never blocks the write that triggered
		# this job, since that write already committed before we got here.
		log_structured("ENTITY_MIRROR_SIDECAR_DOWN", {"doctype": doctype, "name": name})
	except Exception:
		frappe.log_error(title=f"Entity mirror failed for {doctype} {name}", message=frappe.get_traceback())


def _resolve_company_for_user(user: str) -> str | None:
	if not frappe.db.has_column("User", "bp_company"):
		return None
	return frappe.db.get_value("User", user, "bp_company")


def _event_seq(modified_iso: str) -> int:
	"""Microsecond epoch of the DocType's own `modified` timestamp -
	monotonic per entity because it's tied to the actual database write,
	unlike a wall-clock read at job-run time (which could be reordered by
	queue scheduling under retries)."""
	dt = frappe.utils.get_datetime(modified_iso)
	return int(dt.timestamp() * 1_000_000)


def _call_ai_sidecar(path: str, json_body: dict, scope_assertion: str, trace_id: str | None = None) -> dict:
	"""ARCH §4.2 Direction 1 - see copilot_gateway_service.py's
	_stream_ai_sidecar() docstring for why this is X-Service-Key /
	X-Scope-Assertion headers, not Frappe token auth."""
	base_url = frappe.conf.get("buildpolaris_ai_base_url")
	if not base_url:
		raise AISidecarUnavailableError("buildpolaris_ai_base_url is not configured in site_config.json.")

	service_key = frappe.conf.get("buildpolaris_ai_service_key")
	if not service_key:
		raise AISidecarUnavailableError("buildpolaris_ai_service_key is not configured in site_config.json.")

	import requests
	try:
		response = requests.post(
			f"{base_url.rstrip('/')}{path}",
			json=json_body,
			headers={
				"X-Service-Key": service_key,
				"X-Scope-Assertion": scope_assertion,
				"X-BP-Trace-Id": trace_id or get_trace_id(),
			},
			timeout=15,
		)
		response.raise_for_status()
		return response.json()
	except Exception as exc:
		raise AISidecarUnavailableError(str(exc)) from exc
