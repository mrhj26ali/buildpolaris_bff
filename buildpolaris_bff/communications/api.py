import frappe
from buildpolaris_bff.communications.services import rfi, submittal, transmittal, action_item

@frappe.whitelist()
def get_rfi_list(project: str): return rfi.get_list(project) if hasattr(rfi, 'get_list') else frappe.get_all("RFI", filters={"project": project})
@frappe.whitelist()
def create_rfi(**kwargs): return rfi.create_rfi(**kwargs)
@frappe.whitelist()
def submit_rfi(rfi_id: str): return rfi.submit_rfi(rfi_id)
@frappe.whitelist()
def answer_rfi(rfi_id: str, receivers_reply: str): return rfi.answer_rfi(rfi_id, receivers_reply)
@frappe.whitelist()
def close_rfi(rfi_id: str): return rfi.close_rfi(rfi_id)
@frappe.whitelist()
def get_submittal_list(project: str): return frappe.get_all("Submittal Package", filters={"project": project})
@frappe.whitelist()
def get_transmittal_list(project: str): return frappe.get_all("Transmittal", filters={"project": project})
@frappe.whitelist()
def get_action_item_list(project: str): return frappe.get_all("Action Item", filters={"project": project})
