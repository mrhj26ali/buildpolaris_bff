import frappe
from frappe.model.document import Document


class SubstantialCompletionCertificate(Document):
    def validate(self):
        # NFR-4: Signatures are immutable once recorded
        if self.is_new():
            return

        original = frappe.get_doc("Substantial Completion Certificate", self.name)

        if original.owner_signed_at and self.owner_signed_at != original.owner_signed_at:
            frappe.throw("Owner signature is immutable once recorded (NFR-4)")
        if original.architect_signed_at and self.architect_signed_at != original.architect_signed_at:
            frappe.throw("Architect signature is immutable once recorded (NFR-4)")
        if original.owner_signed_by and self.owner_signed_by != original.owner_signed_by:
            frappe.throw("Owner signer is immutable once recorded (NFR-4)")
        if original.architect_signed_by and self.architect_signed_by != original.architect_signed_by:
            frappe.throw("Architect signer is immutable once recorded (NFR-4)")

    def before_save(self):
        # Warranty start date is fixed to the certificate date, not upload date
        if self.substantial_completion_date and not self.warranty_start_date:
            self.warranty_start_date = self.substantial_completion_date

        # Auto-set status to Signed when both parties have signed
        if self.owner_signed_at and self.architect_signed_at:
            self.status = "Signed"
