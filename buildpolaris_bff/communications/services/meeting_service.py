import frappe
from frappe.utils import now_datetime
from frappe.utils import now_datetime

def create_meeting_series(project: str, title: str, frequency: str = "Weekly"):
    """FR-10: Create a new Meeting Series."""
    series = frappe.get_doc({
        "doctype": "Meeting Series",
        "project": project,
        "title": title,
        "frequency": frequency,
    }).insert(ignore_permissions=True)
    return series.name



def record_meeting_minutes(series_id: str, meeting_date: str, notes: str = None):
    """FR-10: Record meeting minutes with auto sequence numbering."""
    minutes = frappe.get_doc({
        "doctype": "Meeting Minutes",
        "series": series_id,
        "meeting_date": meeting_date,
        "notes": notes,
        "status": "Draft",
    }).insert(ignore_permissions=True)
    return minutes.name



