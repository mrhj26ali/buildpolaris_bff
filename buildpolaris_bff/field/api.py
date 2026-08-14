import frappe
from buildpolaris_bff.field_execution.services import daily_log, punch_list, safety

@frappe.whitelist()
def get_daily_log_list(project: str): return frappe.get_all("Daily Log", filters={"project": project})
@frappe.whitelist()
def create_daily_log(**kwargs): return daily_log.create_daily_log(**kwargs)
@frappe.whitelist()
def submit_daily_log(log_id: str): return daily_log.submit_daily_log(log_id)
@frappe.whitelist()
def get_punch_list(project: str): return frappe.get_all("Punch List Item", filters={"project": project})
@frappe.whitelist()
def create_punch_item(**kwargs): return punch_list.create_punch_item(**kwargs)
@frappe.whitelist()
def close_punch_item(punch_item_id: str, notes: str = None): return punch_list.close_punch_item(punch_item_id, notes)
