"""
The BFF-side half of the copilot chat surface (UC-8.1, ARCH §4.5). The PWA
never talks to buildpolaris_ai directly - every message is proxied through
here so the BFF can (a) mint the Scope Assertion the sidecar needs (ARCH
§4.2 Direction 1) and (b) persist Copilot Thread/Copilot Message as the
system-of-record chat history (ARCH §3.3/§8.2 gap this module closes).

NFR-SCALE.5: if buildpolaris_ai is slow or unreachable, this fails closed -
a clearly-labeled refusal message is persisted and returned, never a hang
and never a raised 500 that would make the rest of the platform look down.
"""
import json

import frappe
from frappe.utils import now_datetime

from buildpolaris_bff.shared.exceptions import AISidecarUnavailableError, PermissionDeniedError
from buildpolaris_bff.shared.scope_assertion import mint_scope_assertion
from buildpolaris_bff.shared.security_log import get_trace_id, log_structured

AI_SIDECAR_TIMEOUT_SECONDS = 20


def send_message(message: str, thread_id: str | None = None, project: str | None = None,
                  user: str | None = None) -> dict:
	"""FR-8.1: every actor reaches AI capability through this single
	surface, scoped to their existing Role/Project permissions."""
	user = user or frappe.session.user
	thread = _resolve_thread(thread_id, project, user)

	_append_message(thread.name, user=user, sender="User", content=message,
	                 is_ai_generated=0, is_refusal=0, model_version=None, citations=None)

	scope_assertion = mint_scope_assertion(project=thread.project, user=user)
	trace_id = get_trace_id()

	try:
		result = _call_ai_sidecar("/copilot/message", {
			"thread_id": thread.name,
			"message": message,
			"scope_assertion": scope_assertion,
			"trace_id": trace_id,
		})
		answer_text = result.get("answer_text", "")
		citations = result.get("citations") or []
		is_refusal = bool(result.get("is_refusal"))
		model_version = result.get("model_version")
	except AISidecarUnavailableError:
		# Fails closed (NFR-SCALE.5) - clear, labeled, never a silent hang.
		answer_text = (
			"The AI copilot is temporarily unavailable. Your question was not "
			"answered, but the rest of BuildPolaris is unaffected - try again "
			"shortly."
		)
		citations, is_refusal, model_version = [], True, None

	assistant_message = _append_message(
		thread.name, user=user, sender="Assistant", content=answer_text,
		is_ai_generated=1, is_refusal=is_refusal, model_version=model_version,
		citations=citations,
	)

	frappe.db.set_value("Copilot Thread", thread.name, "last_message_at", now_datetime())
	if not thread.title:
		frappe.db.set_value("Copilot Thread", thread.name, "title", message[:140])

	return {"thread_id": thread.name, "message": assistant_message}


def list_threads(user: str | None = None) -> list:
	"""No ignore_permissions - Copilot Thread's if_owner permission row
	(doctype JSON) does the actual scoping; this is a straight pass-through
	so the framework, not application code, is the enforcement point."""
	return frappe.get_list(
		"Copilot Thread", fields=["name", "title", "project", "started_at", "last_message_at"],
		order_by="last_message_at desc", user=user,
	)


def list_thread_messages(thread_id: str, user: str | None = None) -> list:
	user = user or frappe.session.user
	if not frappe.has_permission("Copilot Thread", "read", thread_id, user=user):
		raise PermissionDeniedError("No access to this copilot thread.")

	rows = frappe.get_all(
		"Copilot Message", filters={"thread": thread_id},
		fields=["name", "sender", "content", "citations", "is_ai_generated",
		        "is_refusal", "model_version", "created_at"],
		order_by="created_at asc",
	)
	for r in rows:
		if r.citations:
			try:
				r.citations = json.loads(r.citations)
			except Exception:
				r.citations = []
	return rows


def _resolve_thread(thread_id: str | None, project: str | None, user: str):
	if thread_id:
		thread = frappe.get_doc("Copilot Thread", thread_id)
		if thread.user != user:
			raise PermissionDeniedError("This copilot thread belongs to another user.")
		return thread

	return frappe.get_doc({
		"doctype": "Copilot Thread",
		"user": user,
		"project": project,
		"started_at": now_datetime(),
		"last_message_at": now_datetime(),
	}).insert(ignore_permissions=True)


def _append_message(thread_name, user, sender, content, is_ai_generated, is_refusal,
                     model_version, citations) -> dict:
	doc = frappe.get_doc({
		"doctype": "Copilot Message",
		"thread": thread_name,
		"user": user,
		"sender": sender,
		"content": content,
		"is_ai_generated": is_ai_generated,
		"is_refusal": is_refusal,
		"model_version": model_version,
		"citations": json.dumps(citations, default=str) if citations else None,
	}).insert(ignore_permissions=True)
	out = doc.as_dict()
	out["citations"] = citations or []
	return out


def _call_ai_sidecar(path: str, json_body: dict) -> dict:
	"""ARCH §4.2 Direction 1: BFF calls buildpolaris_ai using a service
	credential (API key/secret minted for the low-privilege 'BuildPolaris AI
	Service' account, see install.py) plus the Scope Assertion just minted
	above. Never sends the browser's own session cookie to the sidecar."""
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
				"X-BP-Trace-Id": get_trace_id(),
			},
			timeout=AI_SIDECAR_TIMEOUT_SECONDS,
		)
		response.raise_for_status()
		return response.json()
	except Exception as exc:
		log_structured("AI_SIDECAR_CALL_FAILED", {"path": path, "error": str(exc)})
		frappe.log_error(title="buildpolaris_ai unreachable", message=frappe.get_traceback())
		raise AISidecarUnavailableError(str(exc))
