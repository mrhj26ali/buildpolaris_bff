from frappe.model.document import Document
from frappe.utils import now_datetime


class SubstantialCompletionCertificate(Document):
	def validate(self):
		"""FR-7.2: signed_at is set automatically once all three required
		sign-offs (PM, Owner, Architect) are present - whether set via the
		service layer or directly, this invariant always holds."""
		if self.pm_signoff and self.owner_signoff and self.architect_signoff and not self.signed_at:
			self.signed_at = now_datetime()
