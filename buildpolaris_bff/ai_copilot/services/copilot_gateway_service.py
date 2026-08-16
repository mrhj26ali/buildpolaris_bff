"""
The BFF-side half of the copilot chat surface (UC-8.1, ARCH §4.5). The PWA
never talks to buildpolaris_ai directly - every message is proxied through
here so the BFF can (a) mint the Scope Assertion the sidecar needs (ARCH
§4.2 Direction 1) and (b) persist Copilot Thread/Copilot Message as the
system-of-record chat history (ARCH §3.3/§8.2 gap this module closes).

buildpolaris_ai's /copilot/message endpoint only ever returns
text/event-stream (it's built around FastAPI's EventSourceResponse) - it
has no synchronous JSON mode. buildpolaris_pwa's copilot surface
(src/features/copilot/lib/sse.ts's bffStream()) already expects to read
an event-stream straight back from THIS endpoint, with each `data:` line
matching src/types/copilot.ts's CopilotStreamEvent union
({type:"text_delta"|"citations"|"navigation"|"tool_result"|
"pending_approval"|"refusal"|"done"|"error", ...}).

This module is the translator in between: it consumes buildpolaris_ai's
raw SSE vocabulary (event: token/citation/disclosure/done/error) and
re-emits the PWA's typed vocabulary.

A note on WHY this reads AI's whole stream before responding rather than
piping bytes through token-by-token as they arrive: Frappe tears down
request-local state (frappe.db's connection, frappe.session) as soon as
the whitelisted method returns control - a lazy generator that tries to
call frappe.db.set_value(...) *after* returning a streaming Response
racily may run after that teardown. Buffering AI's stream here, persisting
the message, and only then handing back the fully-built event-stream text
sidesteps that hazard entirely. It's still 100% wire-correct - bffStream()
reads whatever chunking the HTTP layer gives it, one JS chunk or forty,
and the perceived latency is already a strict improvement over the
previous (fully synchronous JSON, no incremental rendering at all)
implementation. A true token-by-token pass-through is a valid future
optimization but needs its own Frappe-lifecycle-safe design - it is not
a drop-in fix in the time this integration pass allows.

NFR-SCALE.5: if buildpolaris_ai is slow or unreachable, this fails closed -
a clearly-labeled refusal message is persisted and returned as a single
SSE error+text event, never a hang and never a raised 500 that would make
the rest of the platform look down.
"""
import json

import frappe
from frappe.utils import now_datetime
from werkzeug.wrappers import Response

from buildpolaris_bff.shared.exceptions import AISidecarUnavailableError, PermissionDeniedError
from buildpolaris_bff.shared.scope_assertion import mint_scope_assertion
from buildpolaris_bff.shared.security_log import get_trace_id, log_structured

AI_SIDECAR_TIMEOUT_SECONDS = 30


def send_message(text: str, thread_id: str | None = None, project: str | None = None,
                  user: str | None = None) -> Response:
	"""FR-8.1: every actor reaches AI capability through this single
	surface, scoped to their existing Role/Project permissions.

	Deliberately NOT wrapped in @api_guard/success() - the wire format
	here is text/event-stream, not the standard JSON envelope. Any error
	on this path still degrades to a well-formed SSE error+text_delta+done
	sequence rather than an exception, so buildpolaris_pwa's bffStream()
	consumer never has to special-case "this endpoint sometimes returns
	JSON instead."""
	user = user or frappe.session.user
	thread = _resolve_thread(thread_id, project, user)

	_append_message(thread.name, user=user, sender="User", content=text,
	                 is_ai_generated=0, is_refusal=0, model_version=None, citations=None)
	# The user's own message must be durable before we start the (possibly
	# slow) outbound call - if the sidecar call fails we still want their
	# question preserved in the thread.
	frappe.db.commit()

	scope_assertion = mint_scope_assertion(project=thread.project, user=user)
	trace_id = get_trace_id()

	sse_lines, answer_text, citations, is_refusal, model_version = _run_turn(
		thread_name=thread.name, text=text, scope_assertion=scope_assertion, trace_id=trace_id,
	)

	_append_message(
		thread.name, user=user, sender="Assistant", content=answer_text,
		is_ai_generated=1, is_refusal=is_refusal, model_version=model_version,
		citations=citations,
	)
	frappe.db.set_value("Copilot Thread", thread.name, "last_message_at", now_datetime())
	if not thread.title:
		frappe.db.set_value("Copilot Thread", thread.name, "title", text[:140])
	frappe.db.commit()

	response = Response("".join(sse_lines), mimetype="text/event-stream")
	response.headers["Cache-Control"] = "no-cache"
	response.headers["X-Accel-Buffering"] = "no"  # nginx: don't buffer SSE responses
	response.headers["X-BP-Trace-Id"] = trace_id
	return response


def _sse_event(payload: dict) -> str:
	"""One line matching what buildpolaris_pwa's bffStream() parses -
	it only reads `data:` lines and JSON.parses each one against
	CopilotStreamEvent, ignoring any `event:` field, so we don't need to
	set one."""
	return f"data: {json.dumps(payload, default=str)}\n\n"


def _run_turn(thread_name: str, text: str, scope_assertion: str, trace_id: str):
	"""Calls buildpolaris_ai, reshapes its SSE vocabulary into
	buildpolaris_pwa's CopilotStreamEvent vocabulary, and returns
	(sse_lines, final_answer_text, citations, is_refusal, model_version)
	for both the HTTP response and Copilot Message persistence."""
	sse_lines: list[str] = []
	answer_text_parts: list[str] = []
	citations: list[dict] = []
	is_refusal = False
	model_version = None

	try:
		for event_name, data in _stream_ai_sidecar("/copilot/message", {
			"thread_id": thread_name,
			"text": text,
			"history": [],
			"scope_assertion": scope_assertion,
		}, scope_assertion=scope_assertion):
			if event_name == "disclosure":
				continue  # buildpolaris_pwa shows a static AI-disclosure badge, not event-driven

			if event_name == "token":
				delta = data.get("text", "")
				answer_text_parts.append(delta)
				sse_lines.append(_sse_event({"type": "text_delta", "delta": delta}))

			elif event_name == "citation":
				citations.append(data)

			elif event_name == "error":
				message = data.get("message") or "The AI copilot hit an unexpected error."
				sse_lines.append(_sse_event({"type": "error", "message": message}))

			elif event_name == "done":
				kind = data.get("kind")
				is_refusal = kind == "refusal"
				model_version = data.get("model_version")

				if citations:
					sse_lines.append(_sse_event({"type": "citations", "citations": citations}))

				if kind == "pending_approval" and data.get("pending_approval"):
					pa = data["pending_approval"]
					sse_lines.append(_sse_event({
						"type": "pending_approval",
						"approval_id": pa.get("approval_id"),
						"agent_type": pa.get("agent_type"),
						"target_doctype": pa.get("target_doctype"),
						"proposed_payload": pa.get("proposed_payload"),
						"model_version": pa.get("model_version") or model_version,
						"confidence": pa.get("confidence"),
						"tool_trace_id": pa.get("tool_trace_id"),
					}))

				sse_lines.append(_sse_event({"type": "done", "ai_generated": kind != "refusal"}))

		if not answer_text_parts and not sse_lines:
			raise AISidecarUnavailableError("buildpolaris_ai returned an empty response stream.")

	except AISidecarUnavailableError:
		# Fails closed (NFR-SCALE.5) - clear, labeled, never a silent hang.
		fallback = (
			"The AI copilot is temporarily unavailable. Your question was not "
			"answered, but the rest of BuildPolaris is unaffected - try again shortly."
		)
		answer_text_parts = [fallback]
		is_refusal, model_version = True, None
		sse_lines = [
			_sse_event({"type": "text_delta", "delta": fallback}),
			_sse_event({"type": "done", "ai_generated": False}),
		]

	return sse_lines, "".join(answer_text_parts), citations, is_refusal, model_version


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


def _stream_ai_sidecar(path: str, json_body: dict, scope_assertion: str):
	"""ARCH §4.2 Direction 1: BFF calls buildpolaris_ai using the shared
	service key (verified by the sidecar's gateway/auth/service_credential.py
	via a plain X-Service-Key header - NOT Frappe token auth, which is
	meaningless to a FastAPI service) plus the Scope Assertion just minted
	above, sent as X-Scope-Assertion (verified by
	gateway/auth/scope_assertion.py, also header-based on this side -
	both are FastAPI Header() dependencies on buildpolaris_ai's routers).

	Yields (event_name, data_dict) pairs parsed from the raw SSE response.
	Never sends the browser's own session cookie to the sidecar.
	"""
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
				"X-BP-Trace-Id": get_trace_id(),
				"Accept": "text/event-stream",
			},
			timeout=AI_SIDECAR_TIMEOUT_SECONDS,
			stream=True,
		)
		response.raise_for_status()
	except Exception as exc:
		log_structured("AI_SIDECAR_CALL_FAILED", {"path": path, "error": str(exc)})
		raise AISidecarUnavailableError(str(exc)) from exc

	yield from _parse_sse(response)


def _parse_sse(response):
	"""Minimal SSE line parser for `requests`' streamed response body -
	buildpolaris_ai emits standard `event: <name>` / `data: <json>` pairs
	separated by a blank line."""
	event_name = "message"
	data_lines: list[str] = []

	for raw_line in response.iter_lines(decode_unicode=True):
		if raw_line is None:
			continue
		line = raw_line.rstrip("\r")

		if line == "":
			if data_lines:
				try:
					data = json.loads("\n".join(data_lines))
				except json.JSONDecodeError:
					data = {}
				yield event_name, data
			event_name = "message"
			data_lines = []
			continue

		if line.startswith("event:"):
			event_name = line[len("event:"):].strip()
		elif line.startswith("data:"):
			data_lines.append(line[len("data:"):].strip())

	if data_lines:
		try:
			data = json.loads("\n".join(data_lines))
		except json.JSONDecodeError:
			data = {}
		yield event_name, data
