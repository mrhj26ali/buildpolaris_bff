import frappe
from frappe.utils import now_datetime
from frappe.utils import now_datetime

def create_drawing(project: str, sheet_number: str, title: str,
                   discipline: str = "General", classification_code: str = None):
    """FR-1: Create a new drawing container in the register."""
    drawing = frappe.get_doc({
        "doctype": "Drawing",
        "project": project,
        "sheet_number": sheet_number,
        "title": title,
        "discipline": discipline,
        "classification_code": classification_code,
        "status": "Active",
    }).insert(ignore_permissions=True)
    return drawing.name


# ============================================================
# REVISION OPERATIONS (FR-2 through FR-5)
# ============================================================


