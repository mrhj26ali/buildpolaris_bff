from frappe.model.document import Document


class CostCode(Document):
    def validate(self):
        if self.revised_budget == 0 and self.original_budget > 0:
            self.revised_budget = self.original_budget
        self.variance = (self.revised_budget or 0) - (self.projected_final or 0)
