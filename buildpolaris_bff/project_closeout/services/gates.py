import frappe
from frappe.utils import now_datetime

def initiate_closeout(project: str, project_has_payment_bond: int = 0):
    existing = frappe.get_all("Closing Record", filters={"project": project}, limit=1)
    if existing: frappe.throw(f"Closeout already initiated for this project: {existing[0].name}")
    closing = frappe.get_doc({"doctype": "Closing Record", "project": project, "status": "Initiated", "project_has_payment_bond": project_has_payment_bond, "initiated_at": now_datetime()}).insert(ignore_permissions=True)
    return closing.name

def issue_substantial_completion(project: str, substantial_completion_date: str, responsibility_terms: str = None):
    closing_records = frappe.get_all("Closing Record", filters={"project": project}, limit=1)
    if not closing_records: frappe.throw("Closeout must be initiated before issuing Substantial Completion")
    closing = frappe.get_doc("Closing Record", closing_records[0].name)
    open_punch_items = frappe.get_all("Punch List Item", filters={"project": project, "status": ["!=", "Closed"]}, fields=["name", "title", "priority", "status"])
    punch_snapshot = "\n".join([f"- {item.title} ({item.priority}, {item.status})" for item in open_punch_items]) if open_punch_items else "No open punch items at time of issuance."
    cert = frappe.get_doc({"doctype": "Substantial Completion Certificate", "project": project, "closing_record": closing.name, "substantial_completion_date": substantial_completion_date, "warranty_start_date": substantial_completion_date, "responsibility_terms": responsibility_terms, "punch_snapshot": punch_snapshot, "status": "PendingSignature", "pm_initiated_by": frappe.session.user}).insert(ignore_permissions=True)
    closing.substantial_completion_certificate = cert.name
    closing.status = "SubstantialComplete"
    closing.save(ignore_permissions=True)
    return cert.name

def sign_substantial_completion(certificate_id: str, signer_role: str, signer_user: str = None):
    cert = frappe.get_doc("Substantial Completion Certificate", certificate_id)
    if cert.status == "Signed": frappe.throw("Certificate is already fully signed")
    signer = signer_user or frappe.session.user
    now = now_datetime()
    if signer_role == "Owner":
        if cert.owner_signed_at: frappe.throw("Owner has already signed")
        cert.owner_signed_by = signer; cert.owner_signed_at = now
    elif signer_role == "Architect":
        if cert.architect_signed_at: frappe.throw("Architect has already signed")
        cert.architect_signed_by = signer; cert.architect_signed_at = now
    else: frappe.throw(f"Invalid signer role: {signer_role}")
    cert.save(ignore_permissions=True)
    return {"status": "success", "certificate_status": cert.status}

def check_final_completion_gate(project: str):
    open_items = frappe.get_all("Punch List Item", filters={"project": project, "status": ["!=", "Closed"]}, fields=["name", "title", "priority", "status"])
    if open_items: return {"cleared": False, "open_count": len(open_items), "blockers": open_items}
    closing_records = frappe.get_all("Closing Record", filters={"project": project}, limit=1)
    if closing_records:
        closing = frappe.get_doc("Closing Record", closing_records[0].name)
        closing.punch_gate_cleared = 1
        closing.save(ignore_permissions=True)
    return {"cleared": True, "open_count": 0, "blockers": []}

def release_final_retainage(project: str):
    closing_records = frappe.get_all("Closing Record", filters={"project": project}, limit=1)
    if not closing_records: frappe.throw("Closeout must be initiated")
    closing = frappe.get_doc("Closing Record", closing_records[0].name)
    if not closing.punch_gate_cleared: frappe.throw("Punch Gate must be cleared")
    if not frappe.get_all("Contractors Affidavit", filters={"project": project}, limit=1): frappe.throw("Affidavit required")
    if not frappe.get_all("Lien Waiver", filters={"project": project, "is_final": 1}, limit=1): frappe.throw("Final Waiver required")
    if closing.project_has_payment_bond and not frappe.get_all("Consent Of Surety", filters={"project": project}, limit=1): frappe.throw("Surety Consent required")
    closing.status = "FinalComplete"
    closing.completed_at = now_datetime()
    closing.save(ignore_permissions=True)
    return {"status": "success", "closing_record": closing.name, "completed_at": str(closing.completed_at)}
