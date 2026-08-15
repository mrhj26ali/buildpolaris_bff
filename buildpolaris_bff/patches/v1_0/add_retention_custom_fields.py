import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

def execute():
    """
    NFR-RETAIN.1: financial/legal closeout records (Commitments, Pay
    Applications, Lien Waivers, Consent of Surety, Contractor's Affidavit,
    Change Events) must retain for a tenant-configurable period aligned to
    jurisdiction - not a single hardcoded value. Idempotent (update=True).
    """
    create_custom_fields(
        {
            "Company": [
                dict(
                    fieldname="bp_legal_retention_section", fieldtype="Section Break",
                    label="BuildPolaris Legal Retention", insert_after="country", collapsible=1,
                ),
                dict(
                    fieldname="bp_legal_retention_years", fieldtype="Int",
                    label="Legal/Financial Record Retention (Years)", default="7",
                    description=(
                        "NFR-RETAIN.1: statute-of-limitations-driven retention for "
                        "Commitments, Pay Applications, Lien Waivers, Consent of Surety, "
                        "Contractor's Affidavit, and Change Events. Configurable per tenant "
                        "jurisdiction. Deactivating a user or archiving a Project never "
                        "deletes these records (NFR-RETAIN.2) - this value is informational "
                        "for a human-approved deletion process, never an auto-delete trigger."
                    ),
                    insert_after="bp_legal_retention_section",
                ),
            ]
        },
        update=True,
    )
