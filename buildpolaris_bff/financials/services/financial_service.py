import frappe

from buildpolaris_bff.financials.services import repository as repo


def _add_company(doctype: str, data: dict, project: str):
    """
    Add company to payload when the DocType has a company field.
    """
    company = frappe.db.get_value("Project", project, "company")

    if company:
        repo.map_field(doctype, repo.COMPANY_FIELD_CANDIDATES, data, company)


def _commitment_names_for_project(project: str) -> list[str]:
    """
    Return commitment document names belonging to a project.
    """
    commitment_filters = repo.project_filter("Commitment", project)

    if not commitment_filters:
        return []

    rows = frappe.get_all(
        "Commitment",
        filters=commitment_filters,
        fields=["name"],
        limit=1000,
        ignore_permissions=True,
    )

    return [row.name for row in rows]


def _pay_application_filters(project: str) -> dict | None:
    """
    Build filters for Pay Applications belonging to a project.

    Some schemas store `project` directly on Pay Application.
    Other schemas link Pay Application to Commitment, and Commitment stores project.
    """
    direct_filters = repo.project_filter("Pay Application", project)

    if direct_filters:
        return direct_filters

    commitment_field = repo.get_fieldname("Pay Application", repo.COMMITMENT_FIELD_CANDIDATES)

    if not commitment_field:
        return None

    commitment_names = _commitment_names_for_project(project)

    if not commitment_names:
        return None

    return {commitment_field: ["in", commitment_names]}


def _sum_pay_applications(project: str) -> float:
    """
    Sum pay applications for a project.

    Priority:
      1. Parent amount field, when populated.
      2. Pay Application Line child rows.
    """
    filters = _pay_application_filters(project)

    if not filters:
        return 0.0

    parent_total = 0.0

    if repo.get_amount_field("Pay Application"):
        parent_total = repo.sum_amount("Pay Application", filters)

    if parent_total:
        return parent_total

    return repo.sum_child_amount_from_parents(
        "Pay Application",
        "Pay Application Line",
        filters,
    )


def create_cost_code(
    project: str,
    code: str,
    label: str | None = None,
    description: str | None = None,
) -> dict:
    data = {"project": project}

    repo.map_field("Cost Code", repo.CODE_FIELD_CANDIDATES, data, code)
    repo.map_field("Cost Code", repo.LABEL_FIELD_CANDIDATES, data, label or description)
    repo.map_field("Cost Code", repo.DESCRIPTION_FIELD_CANDIDATES, data, description)

    _add_company("Cost Code", data, project)

    doc = repo.create_document("Cost Code", data)

    return {"name": doc.name}


def list_cost_codes(project: str) -> list[dict]:
    filters = repo.project_filter("Cost Code", project)

    if filters is None:
        return []

    return repo.list_documents(
        "Cost Code",
        filters,
        fields=["name", "code", "label", "description"],
    )


def create_commitment(
    project: str,
    cost_code: str,
    amount: float,
    supplier: str | None = None,
    date: str | None = None,
    description: str | None = None,
    status: str | None = None,
    title: str | None = None,
) -> dict:
    data = {"project": project}

    repo.map_field("Commitment", repo.COST_CODE_FIELD_CANDIDATES, data, cost_code)
    repo.map_amount_field("Commitment", data, amount)
    repo.map_field("Commitment", repo.SUPPLIER_FIELD_CANDIDATES, data, supplier)
    repo.map_field("Commitment", repo.DATE_FIELD_CANDIDATES, data, date)
    repo.map_field("Commitment", repo.DESCRIPTION_FIELD_CANDIDATES, data, description)
    repo.map_field("Commitment", repo.STATUS_FIELD_CANDIDATES, data, status)
    repo.map_field(
        "Commitment",
        repo.LABEL_FIELD_CANDIDATES,
        data,
        title or description or f"Commitment {amount}",
    )

    _add_company("Commitment", data, project)

    doc = repo.create_document("Commitment", data)

    return {"name": doc.name}


def list_commitments(project: str) -> list[dict]:
    filters = repo.project_filter("Commitment", project)

    if filters is None:
        return []

    return repo.list_documents(
        "Commitment",
        filters,
        fields=["name", "cost_code", "supplier", "amount", "date", "description", "status"],
    )


def create_change_event(
    project: str,
    cost_code: str,
    amount: float,
    description: str | None = None,
    status: str | None = None,
    title: str | None = None,
) -> dict:
    data = {"project": project}

    repo.map_field("Change Event", repo.COST_CODE_FIELD_CANDIDATES, data, cost_code)
    repo.map_amount_field("Change Event", data, amount)
    repo.map_field("Change Event", repo.DESCRIPTION_FIELD_CANDIDATES, data, description)
    repo.map_field("Change Event", repo.STATUS_FIELD_CANDIDATES, data, status)
    repo.map_field(
        "Change Event",
        repo.LABEL_FIELD_CANDIDATES,
        data,
        title or description or f"Change Event {amount}",
    )

    _add_company("Change Event", data, project)

    doc = repo.create_document("Change Event", data)

    return {"name": doc.name}


def list_change_events(project: str) -> list[dict]:
    filters = repo.project_filter("Change Event", project)

    if filters is None:
        return []

    return repo.list_documents(
        "Change Event",
        filters,
        fields=["name", "cost_code", "amount", "description", "status"],
    )


def create_pay_application(
    project: str,
    commitment: str,
    period_start: str | None = None,
    period_end: str | None = None,
    lines: list[dict] | None = None,
    status: str | None = None,
    title: str | None = None,
) -> dict:
    data = {"project": project}

    repo.map_field("Pay Application", repo.COMMITMENT_FIELD_CANDIDATES, data, commitment)
    repo.map_field("Pay Application", repo.PERIOD_START_FIELD_CANDIDATES, data, period_start)
    repo.map_field("Pay Application", repo.PERIOD_END_FIELD_CANDIDATES, data, period_end)
    repo.map_field("Pay Application", repo.STATUS_FIELD_CANDIDATES, data, status)
    repo.map_field(
        "Pay Application",
        repo.LABEL_FIELD_CANDIDATES,
        data,
        title or f"Pay Application {period_start or ''}",
    )

    _add_company("Pay Application", data, project)

    child_rows = []
    total = 0.0

    for line in lines or []:
        row = {}
        amount = float(line.get("amount") or 0)
        total += amount

        repo.map_field(
            "Pay Application Line",
            repo.COST_CODE_FIELD_CANDIDATES,
            row,
            line.get("cost_code"),
        )
        repo.map_amount_with_components("Pay Application Line", row, amount)
        repo.map_field(
            "Pay Application Line",
            repo.DESCRIPTION_FIELD_CANDIDATES,
            row,
            line.get("description"),
        )

        child_rows.append(row)

    # Store application total on parent if an amount-like field exists.
    repo.map_amount_field("Pay Application", data, total)

    doc = repo.create_document(
        "Pay Application",
        data,
        child_doctype="Pay Application Line",
        child_rows=child_rows,
    )

    return {
        "name": doc.name,
        "total": total,
    }


def list_pay_applications(project: str) -> list[dict]:
    filters = _pay_application_filters(project)

    if filters is None:
        return []

    return repo.list_documents(
        "Pay Application",
        filters,
        fields=["name", "commitment", "period_start", "period_end", "amount", "status"],
    )


def get_budget_summary(project: str) -> dict:
    cost_codes = list_cost_codes(project)

    commitment_filters = repo.project_filter("Commitment", project)
    commitment_total = (
        repo.sum_amount("Commitment", commitment_filters)
        if commitment_filters
        else 0.0
    )

    change_filters = repo.project_filter("Change Event", project)
    change_total = (
        repo.sum_amount("Change Event", change_filters)
        if change_filters
        else 0.0
    )

    approved_change_total = 0.0
    status_field = repo.get_fieldname("Change Event", repo.STATUS_FIELD_CANDIDATES)

    if change_filters:
        if status_field:
            approved_filters = dict(change_filters)
            approved_filters[status_field] = ["in", ["Approved", "Accepted", "Confirmed"]]
            approved_change_total = repo.sum_amount("Change Event", approved_filters)
        else:
            approved_change_total = change_total

    pay_application_total = _sum_pay_applications(project)

    return {
        "project": project,
        "cost_codes": cost_codes,
        "total_committed": commitment_total,
        "total_change_events": change_total,
        "approved_change_events": approved_change_total,
        "total_pay_applications": pay_application_total,
        "projected_total": commitment_total + approved_change_total,
    }
