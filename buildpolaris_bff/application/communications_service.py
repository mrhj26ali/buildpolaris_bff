import frappe
from frappe.utils import now_datetime


@frappe.whitelist()
def create_rfi(project: str, subject: str, description: str = None,
               reference_doctype: str = None, reference_name: str = None,
               sender_recommendation: str = None, cost_impact: int = 0,
               schedule_impact: int = 0, requested_reply_date: str = None,
               watchers: list = None):
    """FR-1: Create a new RFI with Draft status."""
    rfi = frappe.get_doc({
        "doctype": "RFI",
        "project": project,
        "subject": subject,
        "description": description,
        "reference_doctype": reference_doctype,
        "reference_name": reference_name,
        "sender_recommendation": sender_recommendation,
        "cost_impact": cost_impact,
        "schedule_impact": schedule_impact,
        "requested_reply_date": requested_reply_date,
        "raised_by": frappe.session.user,
        "status": "Draft",
    }).insert(ignore_permissions=True)

    # FR-2: Add watchers
    if watchers:
        for user in watchers:
            frappe.get_doc({
                "doctype": "RFI Watcher",
                "rfi": rfi.name,
                "user": user,
                "watching": 1,
            }).insert(ignore_permissions=True)

    return rfi.name


@frappe.whitelist()
def submit_rfi(rfi_id: str):
    """FR-1: Transition RFI from Draft to Open."""
    rfi = frappe.get_doc("RFI", rfi_id)
    if rfi.status != "Draft":
        frappe.throw(f"Cannot submit RFI in status {rfi.status}")
    rfi.status = "Open"
    rfi.save(ignore_permissions=True)
    return {"status": "success", "rfi_id": rfi.name}


@frappe.whitelist()
def answer_rfi(rfi_id: str, receivers_reply: str):
    """FR-1: Transition RFI to Answered."""
    rfi = frappe.get_doc("RFI", rfi_id)
    if rfi.status != "Open":
        frappe.throw(f"Cannot answer RFI in status {rfi.status}")
    rfi.receivers_reply = receivers_reply
    rfi.status = "Answered"
    rfi.save(ignore_permissions=True)
    return {"status": "success", "rfi_id": rfi.name}


@frappe.whitelist()
def close_rfi(rfi_id: str):
    """FR-1: Transition RFI to Closed."""
    rfi = frappe.get_doc("RFI", rfi_id)
    if rfi.status != "Answered":
        frappe.throw(f"Cannot close RFI in status {rfi.status}")
    rfi.status = "Closed"
    rfi.save(ignore_permissions=True)
    return {"status": "success", "rfi_id": rfi.name}


@frappe.whitelist()
def route_item(project: str, reference_doctype: str, reference_name: str,
               reviewer: str, decision: str = None):
    """FR-3: Record a routing step using the unified RouteStep entity."""
    route_step = frappe.get_doc({
        "doctype": "Route Step",
        "project": project,
        "reference_doctype": reference_doctype,
        "reference_name": reference_name,
        "reviewer": reviewer,
        "decision": decision,
        "routed_at": now_datetime(),
    }).insert(ignore_permissions=True)

    # Update ball_in_court on the referenced document
    doc = frappe.get_doc(reference_doctype, reference_name)
    doc.ball_in_court = reviewer
    doc.save(ignore_permissions=True)

    return route_step.name


@frappe.whitelist()
def create_submittal(project: str, spec_section: str, items: list,
                     linked_task: str = None, required_by_date: str = None):
    """FR-4: Create a new Submittal Package with line items."""
    package = frappe.get_doc({
        "doctype": "Submittal Package",
        "project": project,
        "spec_section": spec_section,
        "linked_task": linked_task,
        "required_by_date": required_by_date,
        "status": "Draft",
        "items": items,
    }).insert(ignore_permissions=True)
    return package.name


@frappe.whitelist()
def resubmit_package(prior_package_id: str, notes: str = None):
    """FR-6: Create a new revision cycle referencing the prior package."""
    prior = frappe.get_doc("Submittal Package", prior_package_id)
    new_package = frappe.get_doc({
        "doctype": "Submittal Package",
        "project": prior.project,
        "spec_section": prior.spec_section,
        "revision_number": prior.revision_number + 1,
        "prior_package": prior.name,
        "linked_task": prior.linked_task,
        "required_by_date": prior.required_by_date,
        "status": "Draft",
        "items": prior.items,
    }).insert(ignore_permissions=True)
    return new_package.name


@frappe.whitelist()
def create_transmittal(project: str, purpose: str, transmission_method: str,
                       content_types: str = None, recipients: list = None):
    """FR-8: Create a new Transmittal with recipients."""
    transmittal = frappe.get_doc({
        "doctype": "Transmittal",
        "project": project,
        "purpose": purpose,
        "transmission_method": transmission_method,
        "content_types": content_types,
        "recipients": [
            {"user": r, "acknowledged": 0} for r in (recipients or [])
        ],
    }).insert(ignore_permissions=True)
    return transmittal.name


@frappe.whitelist()
def acknowledge_transmittal(transmittal_id: str, recipient_user: str):
    """FR-9: Record click-wrap acknowledgment with immutable timestamp."""
    transmittal = frappe.get_doc("Transmittal", transmittal_id)
    for recipient in transmittal.recipients:
        if recipient.user == recipient_user:
            if recipient.acknowledged:
                frappe.throw("Already acknowledged")
            recipient.acknowledged = 1
            recipient.acknowledged_at = now_datetime()
            break
    transmittal.save(ignore_permissions=True)
    return {"status": "success"}


@frappe.whitelist()
def create_meeting_series(project: str, title: str, frequency: str = "Weekly"):
    """FR-10: Create a new Meeting Series."""
    series = frappe.get_doc({
        "doctype": "Meeting Series",
        "project": project,
        "title": title,
        "frequency": frequency,
    }).insert(ignore_permissions=True)
    return series.name


@frappe.whitelist()
def record_meeting_minutes(series_id: str, meeting_date: str, notes: str = None):
    """FR-10: Record meeting minutes with auto sequence numbering."""
    minutes = frappe.get_doc({
        "doctype": "Meeting Minutes",
        "series": series_id,
        "meeting_date": meeting_date,
        "notes": notes,
        "status": "Draft",
    }).insert(ignore_permissions=True)
    return minutes.name


@frappe.whitelist()
def create_action_item(project: str, subject: str, assigned_to: str = None,
                       due_date: str = None, priority: str = "Medium",
                       minutes_id: str = None, description: str = None):
    """FR-11: Create a new Action Item."""
    item = frappe.get_doc({
        "doctype": "Action Item",
        "project": project,
        "subject": subject,
        "assigned_to": assigned_to,
        "due_date": due_date,
        "priority": priority,
        "minutes": minutes_id,
        "description": description,
        "status": "Open",
    }).insert(ignore_permissions=True)
    return item.name