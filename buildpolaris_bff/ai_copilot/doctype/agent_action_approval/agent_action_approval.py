import frappe
from frappe.model.document import Document


class AgentActionApproval(Document):
	"""FR-8.6 / NFR-EXT.3: the ONE gated-write primitive every agent uses.
	Business logic (propose/approve/reject/execute) lives in
	ai_copilot/services/{proposal,approval,execution}_service.py - this
	controller only holds invariants that must be true no matter what
	calls .save() directly."""

	def validate(self):
		if not self.idempotency_key:
			# Defense in depth: proposal_service.py always sets this, but a
			# direct .save() call (script, console) must not silently skip
			# NFR-SCALE.6's unique key.
			self.idempotency_key = self.tool_trace_id
