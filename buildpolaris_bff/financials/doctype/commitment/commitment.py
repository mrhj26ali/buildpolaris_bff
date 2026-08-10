from frappe.model.document import Document


class Commitment(Document):
    def validate(self):
        self.revised_amount = (self.original_amount or 0) + (self.approved_changes or 0)
