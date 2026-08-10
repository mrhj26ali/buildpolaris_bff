import frappe
from frappe.utils import now_datetime

def create_daily_log(project: str, log_date: str, weather_conditions: str = None, temperature: str = None, workforce_count: int = 0, work_performed: str = None, delays: str = None, visitors: str = None, notes: str = None, gps_latitude: float = None, gps_longitude: float = None, photos: list = None):
    log = frappe.get_doc({"doctype": "Daily Log", "project": project, "log_date": log_date, "weather_conditions": weather_conditions, "temperature": temperature, "workforce_count": workforce_count, "work_performed": work_performed, "delays": delays, "visitors": visitors, "notes": notes, "gps_latitude": gps_latitude, "gps_longitude": gps_longitude, "status": "Draft", "photos": [{"file_url": p.get("file_url", ""), "caption": p.get("caption", ""), "gps_lat": p.get("gps_lat"), "gps_lng": p.get("gps_lng"), "captured_at": p.get("captured_at", now_datetime())} for p in (photos or [])]}).insert(ignore_permissions=True)
    return log.name

def submit_daily_log(log_id: str):
    log = frappe.get_doc("Daily Log", log_id)
    if log.status != "Draft": frappe.throw(f"Cannot submit daily log in status {log.status}")
    log.status = "Submitted"
    log.save(ignore_permissions=True)
    return {"status": "success", "log_id": log.name}
