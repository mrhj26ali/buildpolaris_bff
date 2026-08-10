from frappe.model.document import Document


class PayApplication(Document):
    def validate(self):
        self._calculate_totals()

    def _calculate_totals(self):
        total = 0
        for line in self.lines:
            line.total_completed = (line.previous_completed or 0) + (line.current_completed or 0)
            total += line.total_completed
        self.total_completed = total
        self.retainage_amount = total * ((self.retainage_percent or 0) / 100)
        current_period = sum(l.current_completed or 0 for l in self.lines)
        self.net_due = current_period - (current_period * ((self.retainage_percent or 0) / 100))
