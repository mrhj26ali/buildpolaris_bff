import frappe
from frappe.utils import now_datetime, today


@frappe.whitelist()
def create_daily_log(project: str, log_date: str, weather_conditions: str = None,
                     temperature: str = None, workforce_count: int = 0,
                     work_performed: str = None, delays: str = None,
                     visitors: str = None, notes: str = None,
                     gps_latitude: float = None, gps_longitude: float = None,
                     photos: list = None):
    """FR-4.1: Create a daily log entry. Supports offline-first via Draft status."""
    log = frappe.get_doc({
        "doctype": "Daily Log",
        "project": project,
        "log_date": log_date,
        "weather_conditions": weather_conditions,
        "temperature": temperature,
        "workforce_count": workforce_count,
        "work_performed": work_performed,
        "delays": delays,
        "visitors": visitors,
        "notes": notes,
        "gps_latitude": gps_latitude,
        "gps_longitude": gps_longitude,
        "status": "Draft",
        "photos": [
            {
                "file_url": p.get("file_url", ""),
                "caption": p.get("caption", ""),
                "gps_lat": p.get("gps_lat"),
                "gps_lng": p.get("gps_lng"),
                "captured_at": p.get("captured_at", now_datetime()),
            }
            for p in (photos or [])
        ],
    }).insert(ignore_permissions=True)
    return log.name


@frappe.whitelist()
def submit_daily_log(log_id: str):
    """FR-4.1: Transition daily log from Draft to Submitted."""
    log = frappe.get_doc("Daily Log", log_id)
    if log.status != "Draft":
        frappe.throw(f"Cannot submit daily log in status {log.status}")
    log.status = "Submitted"
    log.save(ignore_permissions=True)
    return {"status": "success", "log_id": log.name}


@frappe.whitelist()
def create_punch_item(project: str, title: str, description: str = None,
                      location: str = None, assigned_to: str = None,
                      priority: str = "Medium", due_date: str = None,
                      linked_rfi: str = None, photo_url: str = None):
    """FR-4.3: Create a new punch list item."""
    item = frappe.get_doc({
        "doctype": "Punch List Item",
        "project": project,
        "title": title,
        "description": description,
        "location": location,
        "assigned_to": assigned_to,
        "priority": priority,
        "due_date": due_date,
        "linked_rfi": linked_rfi,
        "photo_url": photo_url,
        "status": "Open",
    }).insert(ignore_permissions=True)
    return item.name


@frappe.whitelist()
def close_punch_item(punch_item_id: str, notes: str = None):
    """FR-4.3 / UC-29: Close a punch list item."""
    item = frappe.get_doc("Punch List Item", punch_item_id)
    if item.status == "Closed":
        frappe.throw("Punch list item is already closed")
    item.status = "Closed"
    item.closed_at = now_datetime()
    if notes:
        item.notes = notes
    item.save(ignore_permissions=True)
    return {"status": "success", "punch_item_id": item.name}


@frappe.whitelist()
def check_punch_closeout_gate(project: str):
    """FR-7.1 / UC-29: Check if all punch items are closed."""
    open_items = frappe.get_all(
        "Punch List Item",
        filters={"project": project, "status": ["!=", "Closed"]},
        fields=["name", "title", "priority", "status"],
    )
    return {
        "cleared": len(open_items) == 0,
        "open_count": len(open_items),
        "blockers": open_items,
    }


@frappe.whitelist()
def create_safety_incident(project: str, incident_date: str, incident_type: str,
                           description: str = None, location: str = None,
                           injured_party: str = None, employer: str = None,
                           root_cause: str = None, corrective_action: str = None,
                           photo_url: str = None, witness_statements: str = None):
    """FR-4.4: Create a safety incident report (OSHA-aligned)."""
    incident = frappe.get_doc({
        "doctype": "Safety Incident",
        "project": project,
        "incident_date": incident_date,
        "incident_type": incident_type,
        "description": description,
        "location": location,
        "injured_party": injured_party,
        "employer": employer,
        "root_cause": root_cause,
        "corrective_action": corrective_action,
        "photo_url": photo_url,
        "witness_statements": witness_statements,
        "status": "Draft",
    }).insert(ignore_permissions=True)
    return incident.name


@frappe.whitelist()
def report_safety_incident(incident_id: str):
    """FR-4.4: Transition safety incident from Draft to Reported."""
    incident = frappe.get_doc("Safety Incident", incident_id)
    if incident.status != "Draft":
        frappe.throw(f"Cannot report incident in status {incident.status}")
    incident.status = "Reported"
    incident.save(ignore_permissions=True)
    return {"status": "success", "incident_id": incident.name}


@frappe.whitelist()
def create_jsa(project: str, title: str, task_description: str = None,
               hazards: list = None):
    """Create a new Job Safety Analysis."""
    jsa = frappe.get_doc({
        "doctype": "JSA",
        "project": project,
        "title": title,
        "task_description": task_description,
        "status": "Draft",
        "hazards": [
            {
                "hazard_description": h.get("hazard_description", ""),
                "risk_level": h.get("risk_level", "Medium"),
                "control_measure": h.get("control_measure", ""),
            }
            for h in (hazards or [])
        ],
    }).insert(ignore_permissions=True)
    return jsa.name


@frappe.whitelist()
def approve_jsa(jsa_id: str, approved_by: str = None):
    """Approve a JSA. Requires hazards to be identified."""
    jsa = frappe.get_doc("JSA", jsa_id)
    if jsa.status == "Approved":
        frappe.throw("JSA is already approved")
    jsa.status = "Approved"
    jsa.approved_by = approved_by or frappe.session.user
    jsa.approved_at = now_datetime()
    jsa.save(ignore_permissions=True)
    return {"status": "success", "jsa_id": jsa.name}
