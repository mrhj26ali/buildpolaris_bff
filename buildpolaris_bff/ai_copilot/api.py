"""
AI Copilot - HTTP adapters only (NFR-MAINT.1).

Two distinct caller populations hit this file:
  - PWA-facing (session-cookie auth, ordinary Role checks): copilot chat,
    thread history, approve/reject decisions, ingestion status, audit trail.
  - AI-sidecar-facing (service credential + forwarded Scope Assertion,
    ARCH §4.2 Direction 2): propose_agent_action - the ONE entrypoint a
    task-specific agent uses to request a gated write.

MCP tool calls (reads) do NOT go through this file - they're a distinct
transport hosted at ai_copilot/mcp/mcp_server.py (ARCH §4.4).
"""
import frappe

from buildpolaris_bff.shared.api_envelope import success, api_guard
from buildpolaris_bff.shared.scope_assertion import verify_scope_assertion
from buildpolaris_bff.ai_copilot.services import (
	audit_service,
	copilot_gateway_service,
	proposal_service,
	approval_service,
)


# ---------------------------------------------------------------------------
# PWA-facing: copilot chat (UC-8.1)
# ---------------------------------------------------------------------------

@frappe.whitelist()
@api_guard
def send_message(text, thread_id=None, project=None):
	"""Streams back text/event-stream, not the standard {success,data,...}
	envelope -- see copilot_gateway_service.send_message()'s docstring.
	buildpolaris_pwa's sse.ts calls this exact dotted path with body
	{thread_id, text, project}."""
	return copilot_gateway_service.send_message(text, thread_id, project)


@frappe.whitelist()
@api_guard
def list_copilot_threads():
	return success(copilot_gateway_service.list_threads())


@frappe.whitelist()
@api_guard
def list_copilot_messages(thread_id):
	return success(copilot_gateway_service.list_thread_messages(thread_id))


# ---------------------------------------------------------------------------
# PWA-facing: gated-write approvals (UC-8.3, FR-8.6)
# ---------------------------------------------------------------------------

@frappe.whitelist()
@api_guard
def list_pending_approvals(project=None):
	return success(proposal_service.list_pending(project))


@frappe.whitelist()
@api_guard
def approve_agent_action(action):
	return success(approval_service.approve(action))


@frappe.whitelist()
@api_guard
def reject_agent_action(action, reason=None):
	return success(approval_service.reject(action, reason))


# ---------------------------------------------------------------------------
# PWA-facing: ingestion status + audit trail
# ---------------------------------------------------------------------------

@frappe.whitelist()
@api_guard
def get_ingestion_status(source_doctype, source_name):
	if not frappe.has_permission(source_doctype, "read", source_name):
		frappe.throw("Forbidden", frappe.PermissionError)
	rows = frappe.get_all(
		"AI Document Index",
		filters={"source_doctype": source_doctype, "source_name": source_name},
		fields=["name", "file", "status", "status_detail", "chunk_count", "model_version", "last_indexed_at"],
	)
	return success(rows)


@frappe.whitelist()
@api_guard
def get_agent_mutation_history(doctype, name):
	return success(audit_service.get_mutation_history(doctype, name))


# ---------------------------------------------------------------------------
# AI-sidecar-facing: Direction 2, propose a gated write (FR-8.6, ARCH §4.2)
# ---------------------------------------------------------------------------

@frappe.whitelist()
@api_guard
def propose_agent_action(agent_type, target_doctype, payload, scope_assertion,
                          model_version=None, confidence=None, tool_trace_id=None,
                          idempotency_key=None):
	"""Called by buildpolaris_ai's orchestrator when a task-specific agent
	(RFIDraftingAgent, etc.) has drafted a write. `scope_assertion` is the
	SAME assertion the BFF minted for this conversational turn
	(copilot_gateway_service.send_message) - `proposed_by` is always the
	assertion's asserted user, never the AI service account calling this
	endpoint."""
	if isinstance(payload, str):
		payload = frappe.parse_json(payload)

	claims = verify_scope_assertion(scope_assertion)
	confidence = float(confidence) if confidence is not None else None

	return success(proposal_service.propose(
		agent_type=agent_type,
		target_doctype=target_doctype,
		payload=payload,
		model_version=model_version,
		confidence=confidence,
		tool_trace_id=tool_trace_id,
		idempotency_key=idempotency_key,
		proposed_by=claims["user"],
	))
