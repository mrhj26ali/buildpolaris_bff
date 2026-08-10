import frappe
from frappe import _
from frappe.query_builder import DocType
from frappe.query_builder.functions import Sum


SYSTEM_FIELDS = {
    "name",
    "owner",
    "creation",
    "modified",
    "modified_by",
    "docstatus",
    "idx",
    "workflow_state",
    "amended_from",
}

LAYOUT_FIELDTYPES = {
    "Section Break",
    "Column Break",
    "Tab Break",
    "HTML",
    "Button",
}

PROJECT_FIELD_CANDIDATES = ["project", "project_link"]
COMPANY_FIELD_CANDIDATES = ["company"]
COST_CODE_FIELD_CANDIDATES = ["cost_code", "cost_code_link", "cost_code_id"]
CODE_FIELD_CANDIDATES = ["code", "cost_code", "cost_code_id", "code_id"]
LABEL_FIELD_CANDIDATES = ["label", "title", "cost_code_name", "name1"]
DESCRIPTION_FIELD_CANDIDATES = ["description", "details", "remarks"]
AMOUNT_FIELD_CANDIDATES = [
    "amount",
    "value",
    "total_amount",
    "committed_amount",
    "approved_amount",
    "commitment_amount",
    "contract_amount",
    "original_amount",
    "application_amount",
    "claimed_amount",
    "current_amount",
    "gross_amount",
    "net_amount",
    "total",
    "grand_total",
]
SUPPLIER_FIELD_CANDIDATES = ["supplier", "vendor", "party", "subcontractor"]
STATUS_FIELD_CANDIDATES = ["status", "state"]
DATE_FIELD_CANDIDATES = [
    "date",
    "commitment_date",
    "transaction_date",
    "application_date",
    "posting_date",
]
PERIOD_START_FIELD_CANDIDATES = ["period_start", "start_date", "from_date"]
PERIOD_END_FIELD_CANDIDATES = ["period_end", "end_date", "to_date"]
COMMITMENT_FIELD_CANDIDATES = ["commitment", "commitment_link", "commitment_id"]
QUANTITY_FIELD_CANDIDATES = [
    "quantity",
    "qty",
    "completed_qty",
    "quantity_completed",
    "work_done",
]
RATE_FIELD_CANDIDATES = [
    "rate",
    "unit_rate",
    "unit_price",
    "price",
    "price_per_unit",
]

AMOUNT_FIELDTYPES = {"Currency", "Float"}


def meta_fields(doctype: str) -> dict:
    """
    Return meta fields keyed by fieldname.
    """
    return {
        df.fieldname: df
        for df in frappe.get_meta(doctype).fields
        if df.fieldname
    }


def sanitize_payload(doctype: str, data: dict) -> dict:
    """
    Keep only fields that exist on the DocType and are not system/layout fields.
    """
    if not isinstance(data, dict):
        return {}

    fields = meta_fields(doctype)

    return {
        key: value
        for key, value in data.items()
        if key in fields
        and key not in SYSTEM_FIELDS
        and fields[key].fieldtype not in LAYOUT_FIELDTYPES
    }


def get_fieldname(doctype: str, candidates: list[str]) -> str | None:
    """
    Return the first fieldname from candidates that exists on the DocType.
    """
    fields = meta_fields(doctype)

    for candidate in candidates:
        if candidate in fields:
            return candidate

    return None


def map_field(doctype: str, candidates: list[str], data: dict, value):
    """
    Map a canonical value to the first matching DocType field.
    """
    if value is None:
        return

    fieldname = get_fieldname(doctype, candidates)

    if fieldname:
        data[fieldname] = value


def get_amount_field(doctype: str) -> str | None:
    """
    Discover the best amount-like field on the DocType.
    """
    fieldname = get_fieldname(doctype, AMOUNT_FIELD_CANDIDATES)

    if fieldname:
        return fieldname

    fields = meta_fields(doctype)

    for fieldname, df in fields.items():
        if fieldname in SYSTEM_FIELDS:
            continue

        if df.fieldtype in LAYOUT_FIELDTYPES:
            continue

        if df.fieldtype in AMOUNT_FIELDTYPES:
            return fieldname

    return None


def map_amount_field(doctype: str, data: dict, amount):
    """
    Map amount to the discovered amount field.
    """
    fieldname = get_amount_field(doctype)

    if fieldname:
        data[fieldname] = float(amount or 0)


def map_amount_with_components(doctype: str, data: dict, amount):
    """
    Map amount and, when relevant, quantity/rate fields.

    This supports child tables where amount may be calculated as:
        quantity * rate
    """
    amount_value = float(amount or 0)

    map_amount_field(doctype, data, amount_value)

    quantity_field = get_fieldname(doctype, QUANTITY_FIELD_CANDIDATES)
    rate_field = get_fieldname(doctype, RATE_FIELD_CANDIDATES)

    if quantity_field and rate_field:
        data[quantity_field] = 1.0
        data[rate_field] = amount_value


def sanitize_filters(doctype: str, filters: dict) -> dict:
    """
    Keep only filters that exist on the DocType.
    """
    if not isinstance(filters, dict):
        return {}

    fields = meta_fields(doctype)

    return {
        key: value
        for key, value in filters.items()
        if key in fields
    }


def project_filter(doctype: str, project: str) -> dict | None:
    """
    Build a project filter for the given DocType.

    Returns None when the DocType has no project-like field.
    This prevents accidental cross-project data access.
    """
    fieldname = get_fieldname(doctype, PROJECT_FIELD_CANDIDATES)

    if not fieldname:
        return None

    return {fieldname: project}


def safe_fields(doctype: str, requested: list[str] | None = None) -> list[str]:
    """
    Return only fields that exist on the DocType.
    Always include the standard `name` field.
    """
    fields = meta_fields(doctype)
    selected = []

    if requested:
        selected = [field for field in requested if field in fields]

    if not selected:
        selected = [
            fieldname
            for fieldname, df in fields.items()
            if fieldname not in SYSTEM_FIELDS
            and df.fieldtype not in LAYOUT_FIELDTYPES
        ][:20]

    if "name" not in selected:
        selected.insert(0, "name")

    return selected


def get_child_table_field_info(doctype: str, child_doctype: str) -> tuple[str | None, str | None]:
    """
    Discover the child table field that links parent to child doctype.

    Returns:
        fieldname, options
    """
    meta = frappe.get_meta(doctype)

    table_fields = [
        df
        for df in meta.fields
        if df.fieldtype in ("Table", "Table MultiSelect")
    ]

    # Exact match first.
    for df in table_fields:
        if df.options == child_doctype:
            return df.fieldname, df.options

    # Fuzzy match by words in the child doctype name.
    child_words = set(child_doctype.lower().split())

    for df in table_fields:
        if not df.options:
            continue

        option_words = set(df.options.lower().split())

        if child_words & option_words:
            return df.fieldname, df.options

    # Fallback by conventional field names.
    for df in table_fields:
        if any(keyword in df.fieldname.lower() for keyword in ("line", "item", "detail", "row")):
            return df.fieldname, df.options

    # Last resort: first table field.
    if table_fields:
        return table_fields[0].fieldname, table_fields[0].options

    return None, None


def get_child_table_field(doctype: str, child_doctype: str) -> str | None:
    """
    Return only the child table fieldname.
    """
    fieldname, _ = get_child_table_field_info(doctype, child_doctype)
    return fieldname


def resolve_child_doctype(parent_doctype: str, expected_child_doctype: str) -> str:
    """
    Resolve the actual child doctype used by the parent table field.
    """
    _, options = get_child_table_field_info(parent_doctype, expected_child_doctype)
    return options or expected_child_doctype


def create_document(
    doctype: str,
    data: dict,
    child_doctype: str | None = None,
    child_rows: list[dict] | None = None,
):
    """
    Create a document using sanitized payload fields.
    """
    doc = frappe.new_doc(doctype)
    doc.update(sanitize_payload(doctype, data))

    if child_doctype and child_rows:
        table_field, actual_child_doctype = get_child_table_field_info(doctype, child_doctype)

        if table_field:
            child_doctype_to_use = actual_child_doctype or child_doctype

            for row in child_rows:
                doc.append(table_field, sanitize_payload(child_doctype_to_use, row))

    doc.insert(ignore_permissions=True)

    return doc


def list_documents(
    doctype: str,
    filters: dict,
    fields: list[str] | None = None,
    order_by: str = "modified desc",
    limit: int = 100,
) -> list[dict]:
    """
    List documents using safe fields and sanitized filters.
    """
    filters = sanitize_filters(doctype, filters)
    fields = safe_fields(doctype, fields)

    return frappe.get_all(
        doctype,
        filters=filters,
        fields=fields,
        order_by=order_by,
        limit=limit,
        ignore_permissions=True,
    )


def _apply_filters(query, dt, filters: dict):
    """
    Apply simple equality or `in` filters to a query-builder query.
    """
    for key, value in filters.items():
        if isinstance(value, list) and len(value) == 2 and value[0] == "in":
            query = query.where(dt[key].isin(value[1]))
        else:
            query = query.where(dt[key] == value)

    return query


def sum_amount(doctype: str, filters: dict) -> float:
    """
    Sum the discovered amount-like field on the DocType.
    """
    filters = sanitize_filters(doctype, filters)
    amount_field = get_amount_field(doctype)

    if not amount_field:
        return 0.0

    dt = DocType(doctype)
    query = frappe.qb.from_(dt).select(Sum(dt[amount_field]).as_("total"))
    query = _apply_filters(query, dt, filters)

    result = query.run(as_dict=True)

    if not result:
        return 0.0

    return float(result[0].total or 0.0)


def sum_child_amount_from_parents(
    parent_doctype: str,
    child_doctype: str,
    parent_filters: dict,
) -> float:
    """
    Sum child table amounts for parents matching the given parent filters.
    """
    parent_filters = sanitize_filters(parent_doctype, parent_filters)

    if not parent_filters:
        return 0.0

    actual_child_doctype = resolve_child_doctype(parent_doctype, child_doctype)
    child_amount_field = get_amount_field(actual_child_doctype)

    if not child_amount_field:
        return 0.0

    parent_dt = DocType(parent_doctype)
    parent_query = frappe.qb.from_(parent_dt).select(parent_dt.name)
    parent_query = _apply_filters(parent_query, parent_dt, parent_filters)

    parent_rows = parent_query.run(as_dict=True)

    if not parent_rows:
        return 0.0

    parent_names = [row.name for row in parent_rows]

    child_dt = DocType(actual_child_doctype)
    child_query = (
        frappe.qb.from_(child_dt)
        .select(Sum(child_dt[child_amount_field]).as_("total"))
        .where(child_dt.parent.isin(parent_names))
    )

    try:
        child_query = child_query.where(child_dt.parenttype == parent_doctype)
    except Exception:
        pass

    result = child_query.run(as_dict=True)

    if not result:
        return 0.0

    return float(result[0].total or 0.0)
