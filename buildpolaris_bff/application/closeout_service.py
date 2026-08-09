import frappe
from frappe.utils import now_datetime


# ============================================================
# CLOSEOUT INITIATION (UC-1, UC-2)
# ============================================================

@frappe.whitelist()
def initiate_closeout(project: str, project_has_payment_bond: int = 0):
    """Initiate the closeout process for a project."""
    # Check if closeout already exists
    existing = frappe.get_all("Closing Record", filters={"project": project}, limit=1)
    if existing:
        frappe.throw(f"Closeout already initiated for this project: {existing[0].name}")

    closing = frappe.get_doc({
        "doctype": "Closing Record",
        "project": project,
        "status": "Initiated",
        "project_has_payment_bond": project_has_payment_bond,
        "initiated_at": now_datetime(),
    }).insert(ignore_permissions=True)
    return closing.name


# ============================================================
# SUBSTANTIAL COMPLETION (FR-1, UC-1, NFR-4)
# ============================================================

@frappe.whitelist()
def issue_substantial_completion(project: str, substantial_completion_date: str,
                                 responsibility_terms: str = None):
    """FR-1: Issue Substantial Completion Certificate.
    S1: Reached WITH punch items still open (punch snapshot attached, not required empty).
    """
    closing_records = frappe.get_all("Closing Record", filters={"project": project}, limit=1)
    if not closing_records:
        frappe.throw("Closeout must be initiated before issuing Substantial Completion")
    closing = frappe.get_doc("Closing Record", closing_records[0].name)

    # Capture punch list snapshot (S1: SC is reached with open punch items)
    open_punch_items = frappe.get_all(
        "Punch List Item",
        filters={"project": project, "status": ["!=", "Closed"]},
        fields=["name", "title", "priority", "status"],
    )
    punch_snapshot = "\n".join(
        [f"- {item.title} ({item.priority}, {item.status})" for item in open_punch_items]
    ) if open_punch_items else "No open punch items at time of issuance."

    cert = frappe.get_doc({
        "doctype": "Substantial Completion Certificate",
        "project": project,
        "closing_record": closing.name,
        "substantial_completion_date": substantial_completion_date,
        "warranty_start_date": substantial_completion_date,
        "responsibility_terms": responsibility_terms,
        "punch_snapshot": punch_snapshot,
        "status": "PendingSignature",
        "pm_initiated_by": frappe.session.user,
    }).insert(ignore_permissions=True)

    # Link certificate to closing record
    closing.substantial_completion_certificate = cert.name
    closing.status = "SubstantialComplete"
    closing.save(ignore_permissions=True)

    return cert.name


@frappe.whitelist()
def sign_substantial_completion(certificate_id: str, signer_role: str, signer_user: str = None):
    """NFR-4: Record immutable signature on Substantial Completion Certificate.
    signer_role: 'Owner' or 'Architect'
    """
    cert = frappe.get_doc("Substantial Completion Certificate", certificate_id)

    if cert.status == "Signed":
        frappe.throw("Certificate is already fully signed")

    signer = signer_user or frappe.session.user
    now = now_datetime()

    if signer_role == "Owner":
        if cert.owner_signed_at:
            frappe.throw("Owner has already signed — signature is immutable (NFR-4)")
        cert.owner_signed_by = signer
        cert.owner_signed_at = now
    elif signer_role == "Architect":
        if cert.architect_signed_at:
            frappe.throw("Architect has already signed — signature is immutable (NFR-4)")
        cert.architect_signed_by = signer
        cert.architect_signed_at = now
    else:
        frappe.throw(f"Invalid signer role: {signer_role}. Must be 'Owner' or 'Architect'.")

    cert.save(ignore_permissions=True)
    return {"status": "success", "certificate_status": cert.status}


# ============================================================
# FINAL COMPLETION PUNCH GATE (FR-2, UC-2)
# ============================================================

@frappe.whitelist()
def check_final_completion_gate(project: str):
    """FR-2: Final Completion Punch Gate — ALL punch items must be Closed.
    Distinct from Substantial Completion (FR-1) which allows open punch items.
    """
    open_items = frappe.get_all(
        "Punch List Item",
        filters={"project": project, "status": ["!=", "Closed"]},
        fields=["name", "title", "priority", "status"],
    )

    if open_items:
        return {
            "cleared": False,
            "open_count": len(open_items),
            "blockers": open_items,
        }

    # Gate cleared — update closing record
    closing_records = frappe.get_all("Closing Record", filters={"project": project}, limit=1)
    if closing_records:
        closing = frappe.get_doc("Closing Record", closing_records[0].name)
        closing.punch_gate_cleared = 1
        closing.save(ignore_permissions=True)

    return {"cleared": True, "open_count": 0, "blockers": []}


# ============================================================
# DOCUMENT COLLECTION (FR-3, FR-4, FR-5, FR-6, FR-7)
# ============================================================

@frappe.whitelist()
def create_warranty_document(project: str, supplier: str, system_scope: str = None,
                             warranty_term_months: int = 12, file_url: str = None):
    """FR-3: Create warranty document. Warranty start date sourced from Substantial Completion Certificate."""
    closing_records = frappe.get_all("Closing Record", filters={"project": project}, limit=1)
    if not closing_records:
        frappe.throw("Closeout must be initiated before collecting warranty documents")
    closing = frappe.get_doc("Closing Record", closing_records[0].name)

    # Get warranty start date from Substantial Completion Certificate
    warranty_start = None
    if closing.substantial_completion_certificate:
        cert = frappe.get_doc("Substantial Completion Certificate", closing.substantial_completion_certificate)
        warranty_start = cert.warranty_start_date

    doc = frappe.get_doc({
        "doctype": "Warranty Document",
        "project": project,
        "closing_record": closing.name,
        "supplier": supplier,
        "system_scope": system_scope,
        "warranty_start_date": warranty_start,
        "warranty_term_months": warranty_term_months,
        "file_url": file_url,
        "status": "Submitted",
    }).insert(ignore_permissions=True)
    return doc.name


@frappe.whitelist()
def create_om_manual(project: str, supplier: str, asset_reference: str = None,
                     file_url: str = None):
    """FR-4: Create O&M manual entry."""
    closing_records = frappe.get_all("Closing Record", filters={"project": project}, limit=1)
    if not closing_records:
        frappe.throw("Closeout must be initiated before collecting O&M manuals")
    closing = frappe.get_doc("Closing Record", closing_records[0].name)

    doc = frappe.get_doc({
        "doctype": "OM Manual",
        "project": project,
        "closing_record": closing.name,
        "supplier": supplier,
        "asset_reference": asset_reference,
        "file_url": file_url,
        "status": "Submitted",
    }).insert(ignore_permissions=True)
    return doc.name


@frappe.whitelist()
def create_affidavit(project: str, supplier: str, all_debts_satisfied: int = 1,
                     exceptions: str = None, file_url: str = None):
    """FR-5: Create Contractor's Affidavit of Payment of Debts and Claims."""
    closing_records = frappe.get_all("Closing Record", filters={"project": project}, limit=1)
    if not closing_records:
        frappe.throw("Closeout must be initiated before collecting affidavits")
    closing = frappe.get_doc("Closing Record", closing_records[0].name)

    doc = frappe.get_doc({
        "doctype": "Contractors Affidavit",
        "project": project,
        "closing_record": closing.name,
        "supplier": supplier,
        "all_debts_satisfied": all_debts_satisfied,
        "exceptions": exceptions,
        "sworn_at": now_datetime(),
        "file_url": file_url,
    }).insert(ignore_permissions=True)
    return doc.name


@frappe.whitelist()
def create_lien_waiver(project: str, supplier: str, waiver_type: str = "Unconditional",
                       is_final: int = 1, pay_application: str = None, file_url: str = None):
    """FR-6: Create lien waiver. Module 7 gates on is_final=true rows only."""
    doc = frappe.get_doc({
        "doctype": "Lien Waiver",
        "project": project,
        "supplier": supplier,
        "waiver_type": waiver_type,
        "is_final": is_final,
        "pay_application": pay_application,
        "submitted_at": now_datetime(),
        "file_url": file_url,
    }).insert(ignore_permissions=True)
    return doc.name


@frappe.whitelist()
def create_consent_of_surety(project: str, surety_name: str, file_url: str = None):
    """FR-7: Create Consent of Surety. Only required if project has payment bond."""
    closing_records = frappe.get_all("Closing Record", filters={"project": project}, limit=1)
    if not closing_records:
        frappe.throw("Closeout must be initiated before collecting surety consent")
    closing = frappe.get_doc("Closing Record", closing_records[0].name)

    if not closing.project_has_payment_bond:
        frappe.throw("Consent of Surety is only required for bonded projects (FR-7)")

    doc = frappe.get_doc({
        "doctype": "Consent Of Surety",
        "project": project,
        "closing_record": closing.name,
        "surety_name": surety_name,
        "consented_at": now_datetime(),
        "file_url": file_url,
    }).insert(ignore_permissions=True)
    return doc.name


# ============================================================
# FINAL RETAINAGE RELEASE (FR-8, UC-7)
# ============================================================

@frappe.whitelist()
def release_final_retainage(project: str):
    """FR-8: Release final retainage. Gated by FR-2, FR-5, FR-6, FR-7."""
    closing_records = frappe.get_all("Closing Record", filters={"project": project}, limit=1)
    if not closing_records:
        frappe.throw("Closeout must be initiated before releasing retainage")
    closing = frappe.get_doc("Closing Record", closing_records[0].name)

    # FR-2 Gate: Final completion punch gate must be cleared
    if not closing.punch_gate_cleared:
        frappe.throw("Final Completion Punch Gate (FR-2) must be cleared before retainage release")

    # FR-5 Gate: Affidavit must exist
    affidavits = frappe.get_all("Contractors Affidavit", filters={"project": project}, limit=1)
    if not affidavits:
        frappe.throw("Contractor's Affidavit (FR-5) must be collected before retainage release")

    # FR-6 Gate: Final lien waivers must exist
    final_waivers = frappe.get_all("Lien Waiver", filters={"project": project, "is_final": 1}, limit=1)
    if not final_waivers:
        frappe.throw("Final Lien Waiver (FR-6) must be collected before retainage release")

    # FR-7 Gate: Consent of Surety required if bonded
    if closing.project_has_payment_bond:
        surety_consents = frappe.get_all("Consent Of Surety", filters={"project": project}, limit=1)
        if not surety_consents:
            frappe.throw("Consent of Surety (FR-7) must be collected before retainage release (project is bonded)")

    # All gates passed — mark as FinalComplete
    closing.status = "FinalComplete"
    closing.completed_at = now_datetime()
    closing.save(ignore_permissions=True)

    return {"status": "success", "closing_record": closing.name, "completed_at": str(closing.completed_at)}
