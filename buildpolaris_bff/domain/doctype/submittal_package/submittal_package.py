import frappe
from frappe.model.document import Document


class SubmittalPackage(Document):
    def validate(self):
        # FR-6: Revision cycle tracking
        if self.prior_package:
            prior = frappe.get_doc("Submittal Package", self.prior_package)
            if self.revision_number <= prior.revision_number:
                frappe.throw(
                    f"Revision number must be greater than prior package ({prior.revision_number})"
                )

    def on_update(self):
        if self.has_value_changed("status"):
            self._log_status_change()

    def _log_status_change(self):
        frappe.get_doc(
            {
                "doctype": "Escalation Log",
                "reference_doctype": "Submittal Package",
                "reference_name": self.name,
                "escalation_tier": 0,
                "escalated_at": frappe.utils.now_datetime(),
            }
        ).insert(ignore_permissions=True)