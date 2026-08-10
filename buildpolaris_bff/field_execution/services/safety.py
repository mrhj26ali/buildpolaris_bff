import frappe
from frappe.utils import now_datetime

def create_safety_incident(project: str, incident_date: str, incident_type: str, description: str = None, location: str = None, injured_party: str = None, employer: str = None, root_cause: str = None, corrective_action: str = None, photo_url: str = None, witness_statements: str = None):
    incident = frappe.get_doc({"doctype": "Safety Incident", "project": project, "incident_date": incident_date, "incident_type": incident_type, "description": description, "location": location, "injured_party": injured_party, "employer": employer, "root_cause": root_cause, "corrective_action": corrective_action, "photo_url": photo_url, "witness_statements": witness_statements, "status": "Draft"}).insert(ignore_permissions=True)
    return incident.name

def report_safety_incident(incident_id: str):
    incident = frappe.get_doc("Safety Incident", incident_id)
    if incident.status != "Draft": frappe.throw(f"Cannot report incident in status {incident.status}")
    incident.status = "Reported"
    incident.save(ignore_permissions=True)
    return {"status": "success", "incident_id": incident.name}

def create_jsa(project: str, title: str, task_description: str = None, hazards: list = None):
    jsa = frappe.get_doc({"doctype": "JSA", "project": project, "title": title, "task_description": task_description, "status": "Draft", "hazards": [{"hazard_description": h.get("hazard_description", ""), "risk_level": h.get("risk_level", "Medium"), "control_measure": h.get("control_measure", "")} for h in (hazards or [])]}).insert(ignore_permissions=True)
    return jsa.name

def approve_jsa(jsa_id: str, approved_by: str = None):
    jsa = frappe.get_doc("JSA", jsa_id)
    if jsa.status == "Approved": frappe.throw("JSA is already approved")
    jsa.status = "Approved"
    jsa.approved_by = approved_by or frappe.session.user
    jsa.approved_at = now_datetime()
    jsa.save(ignore_permissions=True)
    return {"status": "success", "jsa_id": jsa.name}
