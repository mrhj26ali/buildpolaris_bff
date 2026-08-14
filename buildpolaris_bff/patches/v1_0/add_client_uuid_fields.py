"""
DATA 2.7 resolved decision: client_uuid on all four offline-writable DocTypes.

Added via create_custom_fields (version-controlled, NFR-MAINT.4). unique=1 so a
retried offline sync cannot double-create; reqd=0 at the schema level so
server-side creations still work, while the offline-sync API layer enforces
presence (api/v1/field.py + shared/idempotency.py).

Platform is pre-launch (REQ 5) -> no production rows to backfill.
"""
import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

OFFLINE_WRITABLE = ["Daily Log", "JSA", "Safety Incident", "Punch List Item"]


def execute():
    for dt in OFFLINE_WRITABLE:
        create_custom_fields({
            dt: [{
                "fieldname": "client_uuid",
                "fieldtype": "Data",
                "label": "Client UUID",
                "insert_after": "project",
                "unique": 1,
                "reqd": 0,
                "read_only": 1,
                "description": "Offline idempotency key (client-generated, matches Idempotency-Key)",
            }]
        }, update=True)
    frappe.db.commit()
