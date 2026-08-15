from frappe.model.document import Document


class CopilotThread(Document):
	"""Every actor reaches AI capability through this one surface (FR-8.1).
	if_owner in every non-Admin permission row (JSON above) is the framework
	enforcement that a thread is private to the user who started it -
	copilot_gateway_service.py never needs its own app-level filter for
	this, matching FR-1.3's 'never an application-level filter' discipline."""
	pass
