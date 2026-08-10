import frappe
from frappe.utils import now_datetime

def create_warranty_document(project: str, supplier: str, system_scope: str = None, warranty_term_months: int = 12, file_url: str = None):
    closing_records = frappe.get_all("Closing Record", filters={"project": project}, limit=1)
    if not closing_records: 
        frappe.throw("Closeout must be initiated")
    closing = frappe.get_doc("Closing Record", closing_records[0].name)
    warranty_start = frappe.get_doc("Substantial Completion Certificate", closing.substantial_completion_certificate).warranty_start_date if closing.substantial_completion_certificate else None
    doc = frappe.get_doc({"doctype": "Warranty Document", "project": project, "closing_record": closing.name, "supplier": supplier, "system_scope": system_scope, "warranty_start_date": warranty_start, "warranty_term_months": warranty_term_months, "file_url": file_url, "status": "Submitted"}).insert(ignore_permissions=True)
    return doc.name

def create_om_manual(project: str, supplier: str, asset_reference: str = None, file_url: str = None):
    closing_records = frappe.get_all("Closing Record", filters={"project": project}, limit=1)
    if not closing_records: 
        frappe.throw("Closeout must be initiated")
    closing = frappe.get_doc("Closing Record", closing_records[0].name)
    doc = frappe.get_doc({"doctype": "OM Manual", "project": project, "closing_record": closing.name, "supplier": supplier, "asset_reference": asset_reference, "file_url": file_url, "status": "Submitted"}).insert(ignore_permissions=True)
    return doc.name

def create_affidavit(project: str, supplier: str, all_debts_satisfied: int = 1, exceptions: str = None, file_url: str = None):
    closing_records = frappe.get_all("Closing Record", filters={"project": project}, limit=1)
    if not closing_records: 
        frappe.throw("Closeout must be initiated")
    closing = frappe.get_doc("Closing Record", closing_records[0].name)
    doc = frappe.get_doc({"doctype": "Contractors Affidavit", "project": project, "closing_record": closing.name, "supplier": supplier, "all_debts_satisfied": all_debts_satisfied, "exceptions": exceptions, "sworn_at": now_datetime(), "file_url": file_url}).insert(ignore_permissions=True)
    return doc.name

def create_lien_waiver(project: str, supplier: str, waiver_type: str = "Unconditional", is_final: int = 1, pay_application: str = None, file_url: str = None):
    doc = frappe.get_doc({"doctype": "Lien Waiver", "project": project, "supplier": supplier, "waiver_type": waiver_type, "is_final": is_final, "pay_application": pay_application, "submitted_at": now_datetime(), "file_url": file_url}).insert(ignore_permissions=True)
    return doc.name

def create_consent_of_surety(project: str, surety_name: str, file_url: str = None):
    closing_records = frappe.get_all("Closing Record", filters={"project": project}, limit=1)
    if not closing_records:
        frappe.throw("Closeout must be initiated before creating consent of surety")
    closing = frappe.get_doc("Closing Record", closing_records[0].name)
    if not closing.project_has_payment_bond:
        frappe.throw("Only required for bonded projects")
    doc = frappe.get_doc({"doctype": "Consent Of Surety", "project": project, "closing_record": closing.name, "surety_name": surety_name, "consented_at": now_datetime(), "file_url": file_url}).insert(ignore_permissions=True)
    return doc.name