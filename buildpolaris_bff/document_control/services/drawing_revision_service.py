import frappe
from frappe.utils import now_datetime
from frappe.utils import now_datetime

def create_revision(drawing_id: str, revision_code: str,
                    native_file: str = None, rendition_file: str = None,
                    notes: str = None):
    """FR-2/FR-5: Upload a new revision (starts as WIP/S0)."""
    drawing = frappe.get_doc("Drawing", drawing_id)

    # Validate revision_code uniqueness per drawing
    existing = frappe.get_all(
        "Drawing Revision",
        filters={"drawing": drawing_id, "revision_code": revision_code},
        limit=1,
    )
    if existing:
        frappe.throw(f"Revision code '{revision_code}' already exists for this drawing")

    revision = frappe.get_doc({
        "doctype": "Drawing Revision",
        "drawing": drawing_id,
        "project": drawing.project,
        "revision_code": revision_code,
        "status": "WIP",
        "status_code": "S0",
        "native_file": native_file,
        "rendition_file": rendition_file,
        "notes": notes,
        "uploaded_by": frappe.session.user,
        "uploaded_at": now_datetime(),
    }).insert(ignore_permissions=True)

    # Update drawing revision count
    drawing.revision_count = (drawing.revision_count or 0) + 1
    drawing.save(ignore_permissions=True)

    return revision.name



def promote_to_shared(revision_id: str):
    """FR-3: WIP -> Shared (internal review gate by Doc Controller/PM)."""
    revision = frappe.get_doc("Drawing Revision", revision_id)
    if revision.status != "WIP":
        frappe.throw(f"Cannot promote revision in status '{revision.status}'. Must be WIP.")
    revision.status = "Shared"
    revision.status_code = "S1"
    revision.save(ignore_permissions=True)
    return {"status": "success", "revision_id": revision.name}



def publish_revision(revision_id: str, authorized_by: str = None):
    """FR-3/FR-4: Shared -> Published/IFC (A/E authorization) + auto-supersede prior."""
    revision = frappe.get_doc("Drawing Revision", revision_id)

    if revision.status != "Shared":
        frappe.throw(f"Cannot publish revision in status '{revision.status}'. Must be Shared first.")

    # FR-4: Auto-archive the current Published revision (supersession)
    current_published = frappe.get_all(
        "Drawing Revision",
        filters={
            "drawing": revision.drawing,
            "status": "Published",
        },
        fields=["name"],
    )
    for pub in current_published:
        old_rev = frappe.get_doc("Drawing Revision", pub.name)
        old_rev.status = "Archived"
        old_rev.status_code = "S2"
        old_rev.save(ignore_permissions=True)

    # Publish this revision
    revision.status = "Published"
    revision.status_code = "S2"
    revision.authorized_by = authorized_by or frappe.session.user
    revision.authorized_at = now_datetime()
    revision.save(ignore_permissions=True)

    # Update drawing's current_published pointer
    drawing = frappe.get_doc("Drawing", revision.drawing)
    drawing.current_revision = revision.name
    drawing.save(ignore_permissions=True)

    return {"status": "success", "revision_id": revision.name}


# ============================================================
# ANNOTATION OPERATIONS (FR-6)
# ============================================================


