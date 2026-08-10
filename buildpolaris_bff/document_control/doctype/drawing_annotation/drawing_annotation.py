from frappe.model.document import Document


class DrawingAnnotation(Document):
    def validate(self):
        # Cannot link to both RFI and Punch Item simultaneously
        if self.linked_rfi and self.linked_punch_item:
            import frappe
            frappe.throw("Annotation cannot be linked to both an RFI and a Punch Item")
