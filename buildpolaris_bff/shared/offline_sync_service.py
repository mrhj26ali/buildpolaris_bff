"""
BFF-side re-validation/apply for PWA outbox replays (UC-6.5, FR-6.5).

The PWA does the syncing; this module ONLY re-validates and applies what
arrives - a queued offline write is a DELAY of server-side validation, never
a bypass of it (ERD §5.4). Renamed from the draft's `sync_engine.py`, which
collided conceptually with the PWA's own client-side SyncEngine.ts.

Covers exactly the four Field Execution collections that are the RxDB
writable boundary (ERD §3.4 design note): Daily Log, JSA, Safety Incident,
Punch List Item. Each has its own apply_offline_write() in its own service
module, following the same one-doctype-one-service pattern as the rest of
the platform.
"""
import importlib

from buildpolaris_bff.shared.exceptions import ValidationError
from buildpolaris_bff.shared.idempotency import idempotent_write
from buildpolaris_bff.shared.permissions import assert_project_permission

_SYNC_TARGETS = {
	"Daily Log": ("buildpolaris_bff.field.services.daily_log_service", "apply_offline_write"),
	"JSA": ("buildpolaris_bff.field.services.jsa_service", "apply_offline_write"),
	"Safety Incident": ("buildpolaris_bff.field.services.safety_incident_service", "apply_offline_write"),
	"Punch List Item": ("buildpolaris_bff.field.services.punch_list_service", "apply_offline_write"),
}


def _resolve(doctype: str):
	target = _SYNC_TARGETS.get(doctype)
	if not target:
		raise ValidationError(f"'{doctype}' is not an offline-syncable collection.")
	module_path, fn_name = target
	module = importlib.import_module(module_path)
	return getattr(module, fn_name)


def apply_offline_write(doctype: str, payload: dict, local_uuid: str, idempotency_key: str | None = None) -> dict:
	"""Re-validate and apply one queued PWA write (ERD §6 'Field write'
	sequence). Never silently drops a write (NFR-UX.3) - any failure raises,
	which the PWA surfaces as a visible sync-conflict/error state.
	"""
	project = payload.get("project")
	if not project:
		raise ValidationError("Offline write payload is missing 'project'.")

	# Permission is re-checked HERE, on the server, even though this write
	# was already "allowed" locally while offline (ERD §5.4: never a bypass).
	assert_project_permission(project, ptype="read")

	apply_fn = _resolve(doctype)
	key = idempotency_key or f"offline:{doctype}:{local_uuid}"

	def _do_apply():
		return apply_fn(payload=payload, local_uuid=local_uuid)

	return idempotent_write(key, payload, _do_apply)
