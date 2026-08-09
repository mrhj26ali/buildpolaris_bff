import frappe


@frappe.whitelist()
def get_closeout_status(project: str):
    """Get aggregated closeout status for a project."""
    closing_records = frappe.get_all("Closing Record", filters={"project": project}, limit=1)
    if not closing_records:
        return {"initiated": False}

    closing = frappe.get_doc("Closing Record", closing_records[0].name)

    cert = None
    if closing.substantial_completion_certificate:
        cert_doc = frappe.get_doc("Substantial Completion Certificate", closing.substantial_completion_certificate)
        cert = {
            "name": cert_doc.name,
            "status": cert_doc.status,
            "substantial_completion_date": str(cert_doc.substantial_completion_date) if cert_doc.substantial_completion_date else None,
            "warranty_start_date": str(cert_doc.warranty_start_date) if cert_doc.warranty_start_date else None,
            "owner_signed": bool(cert_doc.owner_signed_at),
            "architect_signed": bool(cert_doc.architect_signed_at),
        }

    warranties = frappe.get_all("Warranty Document", filters={"project": project}, fields=["name", "supplier", "status"])
    om_manuals = frappe.get_all("OM Manual", filters={"project": project}, fields=["name", "supplier", "status"])
    affidavits = frappe.get_all("Contractors Affidavit", filters={"project": project}, fields=["name", "supplier", "all_debts_satisfied"])
    final_waivers = frappe.get_all("Lien Waiver", filters={"project": project, "is_final": 1}, fields=["name", "supplier"])
    surety_consents = frappe.get_all("Consent Of Surety", filters={"project": project}, fields=["name", "surety_name"])

    return {
        "initiated": True,
        "closing_record": closing.name,
        "status": closing.status,
        "punch_gate_cleared": bool(closing.punch_gate_cleared),
        "project_has_payment_bond": bool(closing.project_has_payment_bond),
        "certificate": cert,
        "warranties_count": len(warranties),
        "om_manuals_count": len(om_manuals),
        "affidavits_count": len(affidavits),
        "final_waivers_count": len(final_waivers),
        "surety_consents_count": len(surety_consents),
    }


@frappe.whitelist()
def get_warranty_documents(project: str):
    """FR-3: Get all warranty documents for a project."""
    return frappe.get_all(
        "Warranty Document",
        filters={"project": project},
        fields=["name", "supplier", "system_scope", "warranty_start_date",
                "warranty_term_months", "status"],
        order_by="creation desc",
    )


@frappe.whitelist()
def get_om_manuals(project: str):
    """FR-4: Get all O&M manuals for a project."""
    return frappe.get_all(
        "OM Manual",
        filters={"project": project},
        fields=["name", "supplier", "asset_reference", "status"],
        order_by="creation desc",
    )


@frappe.whitelist()
def get_affidavits(project: str):
    """FR-5: Get all affidavits for a project."""
    return frappe.get_all(
        "Contractors Affidavit",
        filters={"project": project},
        fields=["name", "supplier", "all_debts_satisfied", "sworn_at"],
        order_by="creation desc",
    )


@frappe.whitelist()
def get_lien_waivers(project: str):
    """FR-6: Get all lien waivers for a project."""
    return frappe.get_all(
        "Lien Waiver",
        filters={"project": project},
        fields=["name", "supplier", "waiver_type", "is_final", "submitted_at"],
        order_by="creation desc",
    )


@frappe.whitelist()
def get_closeout_record_set(project: str):
    """FR-9: Get consolidated closeout record set for Owner handover."""
    closing_records = frappe.get_all("Closing Record", filters={"project": project}, limit=1)
    if not closing_records:
        frappe.throw("Closeout not initiated for this project")

    return {
        "certificate": frappe.get_all("Substantial Completion Certificate", filters={"project": project}, fields=["*"]),
        "warranties": frappe.get_all("Warranty Document", filters={"project": project}, fields=["*"]),
        "om_manuals": frappe.get_all("OM Manual", filters={"project": project}, fields=["*"]),
        "affidavits": frappe.get_all("Contractors Affidavit", filters={"project": project}, fields=["*"]),
        "final_waivers": frappe.get_all("Lien Waiver", filters={"project": project, "is_final": 1}, fields=["*"]),
        "surety_consents": frappe.get_all("Consent Of Surety", filters={"project": project}, fields=["*"]),
    }
