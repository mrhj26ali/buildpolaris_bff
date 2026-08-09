import frappe


@frappe.whitelist()
def get_daily_log_list(project: str):
    """FR-4.1: Get all daily logs for a project."""
    return frappe.get_all(
        "Daily Log",
        filters={"project": project},
        fields=["name", "log_date", "status", "weather_conditions",
                "workforce_count", "submitted_by"],
        order_by="log_date desc",
    )


@frappe.whitelist()
def get_punch_list(project: str):
    """FR-4.3: Get punch list items for a project."""
    return frappe.get_all(
        "Punch List Item",
        filters={"project": project},
        fields=["name", "title", "location", "assigned_to", "priority",
                "status", "due_date", "closed_at"],
        order_by="creation desc",
    )


@frappe.whitelist()
def get_safety_incident_list(project: str):
    """FR-4.4: Get safety incidents for a project."""
    return frappe.get_all(
        "Safety Incident",
        filters={"project": project},
        fields=["name", "incident_date", "incident_type", "severity",
                "status", "osha_recordable", "location"],
        order_by="incident_date desc",
    )


@frappe.whitelist()
def get_jsa_list(project: str):
    """Get JSAs for a project."""
    return frappe.get_all(
        "JSA",
        filters={"project": project},
        fields=["name", "title", "status", "approved_by", "approved_at"],
        order_by="creation desc",
    )


@frappe.whitelist()
def get_safety_statistics(project: str):
    """FR-4.4: Safety statistics for dashboard reporting."""
    incidents = frappe.get_all(
        "Safety Incident",
        filters={"project": project},
        fields=["incident_type", "osha_recordable"],
    )
    total = len(incidents)
    recordable = len([i for i in incidents if i.osha_recordable])
    near_misses = len([i for i in incidents if i.incident_type == "Near Miss"])

    return {
        "total_incidents": total,
        "osha_recordable": recordable,
        "near_misses": near_misses,
        "lost_time": len([i for i in incidents if i.incident_type == "Lost Time"]),
        "first_aid": len([i for i in incidents if i.incident_type == "First Aid"]),
    }
