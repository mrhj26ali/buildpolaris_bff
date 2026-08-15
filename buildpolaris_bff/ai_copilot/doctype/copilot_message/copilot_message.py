import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


class CopilotMessage(Document):
	def validate(self):
		if not self.created_at:
			self.created_at = now_datetime()
		self._enforce_thread_ownership()

	def _enforce_thread_ownership(self):
		"""Defense in depth alongside the if_owner permission row: a message
		can never be filed under a thread it doesn't belong to, even via a
		direct .save() that bypassed copilot_gateway_service.py."""
		thread_user = frappe.db.get_value("Copilot Thread", self.thread, "user")
		if thread_user and self.user != thread_user:
			frappe.throw("Copilot Message.user must match its Thread's owner.")
