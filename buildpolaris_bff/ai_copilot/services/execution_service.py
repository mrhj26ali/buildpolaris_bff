"""
Execution half of the shared ActionApprovalGate (FR-8.6). Deliberately
generic - target_doctype + proposed_payload is a JSON blob, not a typed
per-agent call, precisely so "adding a new agent" (FR-8.5) never means
"adding a new execution path" (ERD §3.6 design note, NFR-EXT.3).

Runs under the APPROVER's own Frappe permissions (no ignore_permissions on
the business write itself) - the gate never escalates privilege beyond what
the human clicking "Approve" already has (NFR-SEC.8). If the approver
lacks create/write access to the target record, this raises
frappe.PermissionError and the approval stays Pending for someone who does.
"""
import json

import frappe

from buildpolaris_bff.ai_copilot.services.proposal_service import AGENT_WRITABLE_DOCTYPES


def execute(doctype: str, payload, executing_user: str | None = None) -> str:
	if doctype not in AGENT_WRITABLE_DOCTYPES:
		frappe.throw(f"Agents may not write to {doctype}.", frappe.PermissionError)

	data = json.loads(payload) if isinstance(payload, str) else (payload or {})
	name = data.get("name")

	if name and frappe.db.exists(doctype, name):
		doc = frappe.get_doc(doctype, name)
		doc.update({k: v for k, v in data.items() if k != "name"})
		doc.save()  # framework permission check runs as executing_user's session
		return doc.name

	doc = frappe.get_doc({"doctype": doctype, **{k: v for k, v in data.items() if k != "name"}})
	doc.insert()
	return doc.name
