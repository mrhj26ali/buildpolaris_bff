import frappe
from buildpolaris_bff.application import communications_service


@frappe.whitelist()
def get_rfi_list(project: str):
    """FR-14: RFI Log/Register."""
    return frappe.get_all(
        "RFI",
        filters={"project": project},
        fields=["name", "rfi_number", "subject", "status", "raised_by",
                "assigned_to", "requested_reply_date", "cost_impact", "schedule_impact"],
        order_by="creation desc",
    )


@frappe.whitelist()
def get_submittal_list(project: str):
    """FR-14: Submittal Register."""
    return frappe.get_all(
        "Submittal Package",
        filters={"project": project},
        fields=["name", "spec_section", "status", "revision_number",
                "ball_in_court", "required_by_date"],
        order_by="creation desc",
    )


@frappe.whitelist()
def get_transmittal_list(project: str):
    """FR-14: Transmittal Log."""
    return frappe.get_all(
        "Transmittal",
        filters={"project": project},
        fields=["name", "purpose", "transmission_method", "creation"],
        order_by="creation desc",
    )


@frappe.whitelist()
def get_action_item_list(project: str):
    """FR-14: Action Item Tracker."""
    return frappe.get_all(
        "Action Item",
        filters={"project": project},
        fields=["name", "subject", "assigned_to", "due_date", "priority", "status"],
        order_by="creation desc",
    )


@frappe.whitelist()
def get_route_history(reference_doctype: str, reference_name: str):
    """FR-3: Get full routing history for an RFI or Submittal."""
    return frappe.get_all(
        "Route Step",
        filters={
            "reference_doctype": reference_doctype,
            "reference_name": reference_name,
        },
        fields=["name", "reviewer", "decision", "routed_at"],
        order_by="routed_at asc",
    )