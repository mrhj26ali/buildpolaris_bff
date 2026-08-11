# SECURITY: The sync engine uses ignore_permissions=True for document
# writes because it operates as a trusted backend service. All mutations
# are pre-authorized at the BFF API layer via require_project_access
# before reaching this module. See NFR-SEC.2 in the requirements doc.
import frappe
from datetime import datetime

from frappe import _
from frappe.utils import get_datetime, now_datetime


ALLOWED_DOCTYPES = {
    "Daily Log",
    "Punch List Item",
    "JSA",
}

SYSTEM_FIELDS = {
    "name",
    "owner",
    "creation",
    "modified",
    "modified_by",
    "docstatus",
    "idx",
    "workflow_state",
    "amended_from",
}

LAYOUT_FIELDTYPES = {
    "Section Break",
    "Column Break",
    "Tab Break",
    "HTML",
    "Button",
}


def _allowed_fieldnames(doctype: str) -> set[str]:
    """
    Return writable field names from the DocType meta.

    This prevents the PWA from writing arbitrary or system-owned fields.
    """
    meta = frappe.get_meta(doctype)

    return {
        df.fieldname
        for df in meta.fields
        if df.fieldname
        and df.fieldtype not in LAYOUT_FIELDTYPES
    } - SYSTEM_FIELDS


def sanitize_payload(doctype: str, data: dict) -> dict:
    """
    Keep only fields that belong to the DocType and are not system fields.
    """
    if not isinstance(data, dict):
        return {}

    allowed = _allowed_fieldnames(doctype)

    return {
        key: value
        for key, value in data.items()
        if key in allowed
    }


def _to_datetime_from_ms(ms_timestamp) -> datetime | None:
    """
    Convert JavaScript millisecond timestamp to Python datetime.
    """
    if not ms_timestamp:
        return None

    try:
        return datetime.fromtimestamp(float(ms_timestamp) / 1000.0)
    except Exception:
        return None


def _to_ms_timestamp(dt_value) -> int:
    """
    Convert datetime to JavaScript millisecond timestamp.
    """
    if not dt_value:
        return 0

    if isinstance(dt_value, str):
        dt_value = get_datetime(dt_value)

    return int(dt_value.timestamp() * 1000)


def process_mutations(mutations: list[dict], last_sync_timestamp=0) -> dict:
    """
    Process a batch of offline mutations from the PWA.

    The PWA sends local IDs and, when known, mapped server names.
    The server applies changes, detects conflicts by modified timestamp,
    and returns applied mappings, conflicts, and errors.
    """
    if not isinstance(mutations, list):
        mutations = []

    applied = []
    conflicts = []
    errors = []

    last_sync_dt = _to_datetime_from_ms(last_sync_timestamp)

    for index, mutation in enumerate(mutations):
        if not isinstance(mutation, dict):
            errors.append(
                {
                    "local_id": f"mutation-{index}",
                    "error": "invalid_mutation",
                    "message": _("Mutation must be an object"),
                }
            )
            continue

        local_id = mutation.get("local_id") or f"mutation-{index}"
        server_name = mutation.get("server_name")
        doctype = mutation.get("doctype")
        action = mutation.get("action")
        data = sanitize_payload(doctype, mutation.get("data") or {})

        if not doctype or not action:
            errors.append(
                {
                    "local_id": local_id,
                    "error": "invalid_mutation",
                    "message": _("doctype and action are required"),
                }
            )
            continue

        if doctype not in ALLOWED_DOCTYPES:
            errors.append(
                {
                    "local_id": local_id,
                    "doctype": doctype,
                    "error": "doctype_not_allowed",
                    "message": _("Sync is not enabled for this doctype"),
                }
            )
            continue

        try:
            if action == "delete":
                if server_name and frappe.db.exists(doctype, server_name):
                    doc = frappe.get_doc(doctype, server_name)
                    doc_modified = get_datetime(doc.modified)

                    if last_sync_dt and doc_modified > last_sync_dt:
                        conflicts.append(
                            {
                                "local_id": local_id,
                                "server_name": server_name,
                                "server_modified": _to_ms_timestamp(doc_modified),
                                "server_data": doc.as_dict(),
                            }
                        )
                        continue

                    frappe.delete_doc(doctype, server_name, ignore_permissions=True)

                    applied.append(
                        {
                            "local_id": local_id,
                            "server_name": server_name,
                            "action": "deleted",
                        }
                    )

                continue

            if server_name and frappe.db.exists(doctype, server_name):
                doc = frappe.get_doc(doctype, server_name)
                doc_modified = get_datetime(doc.modified)

                if last_sync_dt and doc_modified > last_sync_dt:
                    conflicts.append(
                        {
                            "local_id": local_id,
                            "server_name": server_name,
                            "server_modified": _to_ms_timestamp(doc_modified),
                            "server_data": doc.as_dict(),
                        }
                    )
                    continue

                doc.update(data)
                doc.save(ignore_permissions=True)

                applied.append(
                    {
                        "local_id": local_id,
                        "server_name": doc.name,
                        "server_modified": _to_ms_timestamp(doc.modified),
                        "action": "updated",
                    }
                )
            else:
                doc = frappe.new_doc(doctype)
                doc.update(data)
                doc.insert(ignore_permissions=True)

                applied.append(
                    {
                        "local_id": local_id,
                        "server_name": doc.name,
                        "server_modified": _to_ms_timestamp(doc.modified),
                        "action": "created",
                    }
                )

        except frappe.MandatoryError as e:
            errors.append(
                {
                    "local_id": local_id,
                    "doctype": doctype,
                    "error": "mandatory_missing",
                    "message": str(e),
                }
            )
            frappe.log_error(
                title=f"BuildPolaris Field Sync Mandatory Error: {doctype}",
                message=frappe.get_traceback(),
            )

        except frappe.LinkValidationError as e:
            errors.append(
                {
                    "local_id": local_id,
                    "doctype": doctype,
                    "error": "invalid_link",
                    "message": str(e),
                }
            )
            frappe.log_error(
                title=f"BuildPolaris Field Sync Link Error: {doctype}",
                message=frappe.get_traceback(),
            )

        except Exception:
            errors.append(
                {
                    "local_id": local_id,
                    "doctype": doctype,
                    "error": "unexpected",
                    "message": _("Unexpected sync error"),
                }
            )
            frappe.log_error(
                title=f"BuildPolaris Field Sync Error: {doctype}",
                message=frappe.get_traceback(),
            )

    return {
        "applied": applied,
        "conflicts": conflicts,
        "errors": errors,
        "server_timestamp": _to_ms_timestamp(now_datetime()),
    }
