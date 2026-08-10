import frappe
from frappe.utils import now_datetime
from frappe.utils import now_datetime

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



