import frappe


@frappe.whitelist()
def get_budget_summary(project: str):
    """Get aggregated budget summary for a project."""
    cost_codes = frappe.get_all(
        "Cost Code",
        filters={"project": project},
        fields=["name", "code", "title", "original_budget", "revised_budget",
                "committed_amount", "spent_to_date", "projected_final", "variance"],
        order_by="code asc",
    )
    total_budget = sum(cc.revised_budget or 0 for cc in cost_codes)
    total_committed = sum(cc.committed_amount or 0 for cc in cost_codes)

    return {
        "cost_codes": cost_codes,
        "total_budget": total_budget,
        "total_committed": total_committed,
        "remaining": total_budget - total_committed,
    }


@frappe.whitelist()
def get_commitment_list(project: str):
    """Get all commitments for a project."""
    return frappe.get_all(
        "Commitment",
        filters={"project": project},
        fields=["name", "vendor", "commitment_type", "original_amount",
                "approved_changes", "revised_amount", "retainage_percent", "status"],
        order_by="creation desc",
    )


@frappe.whitelist()
def get_change_event_list(project: str):
    """Get all change events for a project."""
    return frappe.get_all(
        "Change Event",
        filters={"project": project},
        fields=["name", "title", "change_type", "status", "amount",
                "linked_commitment", "approved_by", "approved_at"],
        order_by="creation desc",
    )


@frappe.whitelist()
def get_pay_application_list(project: str):
    """Get all pay applications for a project."""
    return frappe.get_all(
        "Pay Application",
        filters={"project": project},
        fields=["name", "commitment", "application_number", "status",
                "period_start", "period_end", "total_completed",
                "retainage_amount", "net_due"],
        order_by="creation desc",
    )


@frappe.whitelist()
def get_financial_dashboard(project: str):
    """Aggregated financial dashboard data."""
    budget = get_budget_summary(project)
    commitments = get_commitment_list(project)
    change_events = get_change_event_list(project)
    pay_apps = get_pay_application_list(project)

    total_change_orders = sum(ce.amount or 0 for ce in change_events if ce.status == "Approved")
    total_paid = sum(pa.net_due or 0 for pa in pay_apps if pa.status == "Approved")

    return {
        "budget": budget,
        "total_commitments": sum(c.revised_amount or 0 for c in commitments),
        "total_approved_changes": total_change_orders,
        "total_paid_to_date": total_paid,
        "open_change_events": len([ce for ce in change_events if ce.status == "Pending"]),
        "open_pay_apps": len([pa for pa in pay_apps if pa.status == "Submitted"]),
    }
