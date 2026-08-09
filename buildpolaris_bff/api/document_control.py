import frappe


@frappe.whitelist()
def get_drawing_register(project: str):
    """FR-1: Get the full drawing register for a project."""
    return frappe.get_all(
        "Drawing",
        filters={"project": project, "status": "Active"},
        fields=["name", "sheet_number", "discipline", "title",
                "classification_code", "current_revision", "revision_count"],
        order_by="sheet_number asc",
    )


@frappe.whitelist()
def get_revision_history(drawing_id: str):
    """FR-2: Get all revisions for a drawing."""
    return frappe.get_all(
        "Drawing Revision",
        filters={"drawing": drawing_id},
        fields=["name", "revision_code", "status", "status_code",
                "uploaded_by", "uploaded_at", "authorized_by", "authorized_at"],
        order_by="creation desc",
    )


@frappe.whitelist()
def get_published_drawings(project: str):
    """FR-4: Get only the current Published (IFC) revision set for field users."""
    drawings = frappe.get_all(
        "Drawing",
        filters={"project": project, "status": "Active", "current_revision": ["is", "set"]},
        fields=["name", "sheet_number", "title", "discipline", "current_revision"],
        order_by="sheet_number asc",
    )
    return drawings


@frappe.whitelist()
def get_annotations(revision_id: str):
    """FR-6: Get all annotations for a specific revision."""
    return frappe.get_all(
        "Drawing Annotation",
        filters={"revision": revision_id},
        fields=["name", "annotation_type", "author", "geometry",
                "comment", "sync_status", "linked_rfi", "linked_punch_item"],
        order_by="creation desc",
    )
