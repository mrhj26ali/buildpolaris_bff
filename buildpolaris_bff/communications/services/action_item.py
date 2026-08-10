import frappe

def create_action_item(project: str, subject: str, assigned_to: str = None, due_date: str = None, priority: str = "Medium", minutes_id: str = None, description: str = None):
    item = frappe.get_doc({"doctype": "Action Item", "project": project, "subject": subject, "assigned_to": assigned_to, "due_date": due_date, "priority": priority, "minutes": minutes_id, "description": description, "status": "Open"}).insert(ignore_permissions=True)
    return item.name
