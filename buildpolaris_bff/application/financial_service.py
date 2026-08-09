import frappe
from frappe.utils import now_datetime


# ============================================================
# COST CODE / BUDGET OPERATIONS
# ============================================================

@frappe.whitelist()
def create_cost_code(project: str, code: str, title: str,
                     original_budget: float = 0, parent_cost_code: str = None):
    """Create a budget cost code with MasterFormat/UniFormat classification."""
    cost_code = frappe.get_doc({
        "doctype": "Cost Code",
        "project": project,
        "code": code,
        "title": title,
        "original_budget": original_budget,
        "revised_budget": original_budget,
        "parent_cost_code": parent_cost_code,
    }).insert(ignore_permissions=True)
    return cost_code.name


# ============================================================
# COMMITMENT OPERATIONS (Subcontracts & POs)
# ============================================================

@frappe.whitelist()
def create_commitment(project: str, cost_code: str, vendor: str,
                      commitment_type: str = "Subcontract",
                      original_amount: float = 0, retainage_percent: float = 10,
                      description: str = None):
    """Create a new commitment (subcontract or purchase order)."""
    commitment = frappe.get_doc({
        "doctype": "Commitment",
        "project": project,
        "cost_code": cost_code,
        "vendor": vendor,
        "commitment_type": commitment_type,
        "original_amount": original_amount,
        "retainage_percent": retainage_percent,
        "description": description,
        "status": "Draft",
    }).insert(ignore_permissions=True)
    return commitment.name


@frappe.whitelist()
def approve_commitment(commitment_id: str):
    """Approve a commitment, making it active for pay applications."""
    commitment = frappe.get_doc("Commitment", commitment_id)
    if commitment.status != "Draft":
        frappe.throw(f"Cannot approve commitment in status '{commitment.status}'")
    commitment.status = "Approved"
    commitment.save(ignore_permissions=True)

    # Update cost code committed amount
    _update_cost_code_committed(commitment.cost_code)

    return {"status": "success", "commitment_id": commitment.name}


def _update_cost_code_committed(cost_code_id: str):
    """Recalculate the committed amount on the cost code."""
    commitments = frappe.get_all(
        "Commitment",
        filters={"cost_code": cost_code_id, "status": ["in", ["Approved", "Closed"]]},
        fields=["revised_amount"],
    )
    total_committed = sum(c.revised_amount or 0 for c in commitments)

    cost_code = frappe.get_doc("Cost Code", cost_code_id)
    cost_code.committed_amount = total_committed
    cost_code.save(ignore_permissions=True)


# ============================================================
# CHANGE EVENT OPERATIONS (Change Orders)
# ============================================================

@frappe.whitelist()
def create_change_event(project: str, title: str, amount: float = 0,
                        change_type: str = "Change Order",
                        cost_code: str = None, description: str = None,
                        linked_rfi: str = None, linked_commitment: str = None):
    """Create a change event. Links to RFI cost impacts (Module 3 UC-11)."""
    change_event = frappe.get_doc({
        "doctype": "Change Event",
        "project": project,
        "title": title,
        "amount": amount,
        "change_type": change_type,
        "cost_code": cost_code,
        "description": description,
        "linked_rfi": linked_rfi,
        "linked_commitment": linked_commitment,
        "status": "Draft",
    }).insert(ignore_permissions=True)
    return change_event.name


@frappe.whitelist()
def submit_change_event(change_event_id: str):
    """Submit a change event for approval."""
    ce = frappe.get_doc("Change Event", change_event_id)
    if ce.status != "Draft":
        frappe.throw(f"Cannot submit change event in status '{ce.status}'")
    ce.status = "Pending"
    ce.save(ignore_permissions=True)
    return {"status": "success", "change_event_id": ce.name}


@frappe.whitelist()
def approve_change_event(change_event_id: str, approved_by: str = None):
    """Approve a change event. Updates linked commitment's approved_changes."""
    ce = frappe.get_doc("Change Event", change_event_id)
    if ce.status != "Pending":
        frappe.throw(f"Cannot approve change event in status '{ce.status}'. Must be Pending first.")

    ce.status = "Approved"
    ce.approved_by = approved_by or frappe.session.user
    ce.approved_at = now_datetime()
    ce.save(ignore_permissions=True)

    # Update linked commitment's approved changes
    if ce.linked_commitment:
        commitment = frappe.get_doc("Commitment", ce.linked_commitment)
        approved_total = frappe.get_all(
            "Change Event",
            filters={"linked_commitment": ce.linked_commitment, "status": "Approved"},
            fields=["amount"],
        )
        commitment.approved_changes = sum(c.amount or 0 for c in approved_total)
        commitment.revised_amount = (commitment.original_amount or 0) + commitment.approved_changes
        commitment.save(ignore_permissions=True)

        # Update cost code committed amount
        _update_cost_code_committed(commitment.cost_code)

    return {"status": "success", "change_event_id": ce.name}


@frappe.whitelist()
def reject_change_event(change_event_id: str):
    """Reject a change event."""
    ce = frappe.get_doc("Change Event", change_event_id)
    if ce.status != "Pending":
        frappe.throw(f"Cannot reject change event in status '{ce.status}'")
    ce.status = "Rejected"
    ce.save(ignore_permissions=True)
    return {"status": "success", "change_event_id": ce.name}


# ============================================================
# PAY APPLICATION OPERATIONS (Progress Billing — AIA Style)
# ============================================================

@frappe.whitelist()
def create_pay_application(project: str, commitment_id: str,
                           period_start: str = None, period_end: str = None,
                           retainage_percent: float = None, lines: list = None):
    """Create a pay application with schedule of values lines."""
    commitment = frappe.get_doc("Commitment", commitment_id)

    # Auto-increment application number
    existing = frappe.get_all(
        "Pay Application",
        filters={"commitment": commitment_id},
        fields=["application_number"],
        order_by="application_number desc",
        limit=1,
    )
    next_num = (existing[0].application_number + 1) if existing else 1

    pay_app = frappe.get_doc({
        "doctype": "Pay Application",
        "project": project,
        "commitment": commitment_id,
        "application_number": next_num,
        "period_start": period_start,
        "period_end": period_end,
        "retainage_percent": retainage_percent if retainage_percent is not None else commitment.retainage_percent,
        "status": "Draft",
        "lines": [
            {
                "cost_code": l.get("cost_code"),
                "description": l.get("description", ""),
                "scheduled_value": l.get("scheduled_value", 0),
                "previous_completed": l.get("previous_completed", 0),
                "current_completed": l.get("current_completed", 0),
            }
            for l in (lines or [])
        ],
    }).insert(ignore_permissions=True)
    return pay_app.name


@frappe.whitelist()
def submit_pay_application(pay_app_id: str):
    """Submit a pay application for approval."""
    pay_app = frappe.get_doc("Pay Application", pay_app_id)
    if pay_app.status != "Draft":
        frappe.throw(f"Cannot submit pay application in status '{pay_app.status}'")
    if not pay_app.lines:
        frappe.throw("Cannot submit pay application without schedule of values lines")
    pay_app.status = "Submitted"
    pay_app.save(ignore_permissions=True)
    return {"status": "success", "pay_app_id": pay_app.name}


@frappe.whitelist()
def approve_pay_application(pay_app_id: str):
    """Approve a pay application."""
    pay_app = frappe.get_doc("Pay Application", pay_app_id)
    if pay_app.status != "Submitted":
        frappe.throw(f"Cannot approve pay application in status '{pay_app.status}'. Must be Submitted first.")
    pay_app.status = "Approved"
    pay_app.save(ignore_permissions=True)
    return {"status": "success", "pay_app_id": pay_app.name}
