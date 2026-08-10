import json

import frappe
from frappe import _

from buildpolaris_bff.financials.services import financial_service as svc
from buildpolaris_bff.shared.api_utils import handle_api_error, standard_response
from buildpolaris_bff.shared.guards import require_project_access


@frappe.whitelist()
@require_project_access("project")
def get_budget_summary(project: str):
    try:
        result = svc.get_budget_summary(project)
        return standard_response(True, result, _("Financial summary retrieved"))
    except Exception as e:
        return handle_api_error(e)


@frappe.whitelist()
@require_project_access("project")
def list_cost_codes(project: str):
    try:
        result = svc.list_cost_codes(project)
        return standard_response(True, result, _("Cost codes retrieved"))
    except Exception as e:
        return handle_api_error(e)


@frappe.whitelist()
@require_project_access("project")
def create_cost_code(project: str, code: str, label: str | None = None, description: str | None = None):
    try:
        result = svc.create_cost_code(project, code, label, description)
        return standard_response(True, result, _("Cost code created"))
    except Exception as e:
        return handle_api_error(e)


@frappe.whitelist()
@require_project_access("project")
def list_commitments(project: str):
    try:
        result = svc.list_commitments(project)
        return standard_response(True, result, _("Commitments retrieved"))
    except Exception as e:
        return handle_api_error(e)


@frappe.whitelist()
@require_project_access("project")
def create_commitment(
    project: str,
    cost_code: str,
    amount: float,
    supplier: str | None = None,
    date: str | None = None,
    description: str | None = None,
    status: str | None = None,
    title: str | None = None,
):
    try:
        result = svc.create_commitment(
            project=project,
            cost_code=cost_code,
            amount=amount,
            supplier=supplier,
            date=date,
            description=description,
            status=status,
            title=title,
        )
        return standard_response(True, result, _("Commitment created"))
    except Exception as e:
        return handle_api_error(e)


@frappe.whitelist()
@require_project_access("project")
def list_change_events(project: str):
    try:
        result = svc.list_change_events(project)
        return standard_response(True, result, _("Change events retrieved"))
    except Exception as e:
        return handle_api_error(e)


@frappe.whitelist()
@require_project_access("project")
def create_change_event(
    project: str,
    cost_code: str,
    amount: float,
    description: str | None = None,
    status: str | None = None,
    title: str | None = None,
):
    try:
        result = svc.create_change_event(
            project=project,
            cost_code=cost_code,
            amount=amount,
            description=description,
            status=status,
            title=title,
        )
        return standard_response(True, result, _("Change event created"))
    except Exception as e:
        return handle_api_error(e)


@frappe.whitelist()
@require_project_access("project")
def list_pay_applications(project: str):
    try:
        result = svc.list_pay_applications(project)
        return standard_response(True, result, _("Pay applications retrieved"))
    except Exception as e:
        return handle_api_error(e)


@frappe.whitelist()
@require_project_access("project")
def create_pay_application(
    project: str,
    commitment: str,
    period_start: str | None = None,
    period_end: str | None = None,
    lines=None,
    status: str | None = None,
    title: str | None = None,
):
    try:
        if isinstance(lines, str):
            lines = json.loads(lines)

        result = svc.create_pay_application(
            project=project,
            commitment=commitment,
            period_start=period_start,
            period_end=period_end,
            lines=lines,
            status=status,
            title=title,
        )
        return standard_response(True, result, _("Pay application created"))
    except Exception as e:
        return handle_api_error(e)
