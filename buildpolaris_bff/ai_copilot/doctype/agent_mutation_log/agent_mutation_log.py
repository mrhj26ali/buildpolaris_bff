from frappe.model.document import Document


class AgentMutationLog(Document):
	"""Write-once audit trail (NFR-AUD.2). Only ever inserted by
	ai_copilot/services/audit_service.py - never edited after creation."""
	pass
