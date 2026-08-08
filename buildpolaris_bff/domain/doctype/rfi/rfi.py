import frappe
from frappe.model.document import Document


class RFI(Document):
    def before_save(self):
        # FR-1: Sequential per-project RFI numbering
        if not self.rfi_number and self.project:
            last_rfi = frappe.get_all(
                "RFI",
                filters={"project": self.project},
                fields=["rfi_number"],
                order_by="creation desc",
                limit=1,
            )
            if last_rfi and last_rfi[0].rfi_number:
                try:
                    last_num = int(last_rfi[0].rfi_number.split("-")[-1])
                    self.rfi_number = f"RFI-{self.project}-{str(last_num + 1).zfill(4)}"
                except (ValueError, IndexError):
                    self.rfi_number = f"RFI-{self.project}-0001"
            else:
                self.rfi_number = f"RFI-{self.project}-0001"

    def on_update(self):
        # FR-13: Trigger escalation check on status change
        if self.has_value_changed("status"):
            self._log_status_change()

    def _log_status_change(self):
        frappe.get_doc(
            {
                "doctype": "Escalation Log",
                "reference_doctype": "RFI",
                "reference_name": self.name,
                "escalation_tier": 0,
                "escalated_at": frappe.utils.now_datetime(),
            }
        ).insert(ignore_permissions=True)