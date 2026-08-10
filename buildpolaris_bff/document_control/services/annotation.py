import frappe
from frappe.utils import now_datetime
from frappe.utils import now_datetime

def create_annotation(revision_id: str, annotation_type: str,
                      geometry: str = None, comment: str = None):
    """FR-6: Create a drawing annotation (markup)."""
    revision = frappe.get_doc("Drawing Revision", revision_id)

    annotation = frappe.get_doc({
        "doctype": "Drawing Annotation",
        "revision": revision_id,
        "project": revision.project,
        "author": frappe.session.user,
        "annotation_type": annotation_type,
        "geometry": geometry,
        "comment": comment,
        "sync_status": "Synced",
    }).insert(ignore_permissions=True)
    return annotation.name



def convert_annotation_to_rfi(annotation_id: str, subject: str,
                              description: str = None):
    """FR-6 / Module 3 UC-1: Convert annotation to RFI."""
    annotation = frappe.get_doc("Drawing Annotation", annotation_id)
    if annotation.linked_rfi:
        frappe.throw("Annotation is already linked to an RFI")

    from buildpolaris_bff.communications.services.rfi import create_rfi
    rfi_id = create_rfi(
        project=annotation.project,
        subject=subject,
        description=description or annotation.comment,
    )

    annotation.linked_rfi = rfi_id
    annotation.save(ignore_permissions=True)
    return {"status": "success", "rfi_id": rfi_id, "annotation_id": annotation_id}



def convert_annotation_to_punch_item(annotation_id: str, title: str,
                                     description: str = None,
                                     priority: str = "Medium"):
    """FR-6 / Module 4 UC-18: Convert annotation to Punch List Item."""
    annotation = frappe.get_doc("Drawing Annotation", annotation_id)
    if annotation.linked_punch_item:
        frappe.throw("Annotation is already linked to a Punch List Item")

    from buildpolaris_bff.field_execution.services.punch_list import create_punch_item
    punch_id = create_punch_item(
        project=annotation.project,
        title=title,
        description=description or annotation.comment,
        priority=priority,
    )

    annotation.linked_punch_item = punch_id
    annotation.save(ignore_permissions=True)
    return {"status": "success", "punch_item_id": punch_id, "annotation_id": annotation_id}


