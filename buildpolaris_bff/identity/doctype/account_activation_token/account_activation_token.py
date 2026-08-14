import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


class AccountActivationToken(Document):
	def validate(self):
		if not self.token_hash:
			frappe.throw(
				"token_hash is required - single-use secrets must never be "
				"stored in plaintext (NFR-SEC.3)."
			)

	def mark_used(self):
		self.used_at = now_datetime()
		self.save(ignore_permissions=True)

	def is_expired(self) -> bool:
		return bool(self.expires_at and self.expires_at < now_datetime())

	def is_used(self) -> bool:
		return bool(self.used_at)
