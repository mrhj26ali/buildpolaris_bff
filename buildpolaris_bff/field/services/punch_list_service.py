import frappe
from frappe.utils import now_datetime

def create_punch_item(project: str, title: str, description: str = None, location: str = None, assigned_to: str = None, priority: str = "Medium", due_date: str = None, linked_rfi: str = None, photo_url: str = None):
    item = frappe.get_doc({"doctype": "Punch List Item", "project": project, "title": title, "description": description, "location": location, "assigned_to": assigned_to, "priority": priority, "due_date": due_date, "linked_rfi": linked_rfi, "photo_url": photo_url, "status": "Open"}).insert(ignore_permissions=True)
    return item.name

def close_punch_item(punch_item_id: str, notes: str = None):
    item = frappe.get_doc("Punch List Item", punch_item_id)
    if item.status == "Closed": frappe.throw("Punch list item is already closed")
    item.status = "Closed"
    item.closed_at = now_datetime()
    if notes: item.notes = notes
    item.save(ignore_permissions=True)
    return {"status": "success", "punch_item_id": item.name}

def check_punch_closeout_gate(project: str):
    open_items = frappe.get_all("Punch List Item", filters={"project": project, "status": ["!=", "Closed"]}, fields=["name", "title", "priority", "status"])
    return {"cleared": len(open_items) == 0, "open_count": len(open_items), "blockers": open_items}
