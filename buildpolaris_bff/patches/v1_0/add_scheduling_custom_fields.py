import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

def execute():
    """
    FR-2.1..FR-2.3: extend native Task with WBS/CPM-output fields.
    Idempotent - create_custom_fields(update=True) merges rather than
    duplicating on re-run (bench migrate may run this more than once).
    """
    custom_fields = {
        "Task": [
            dict(fieldname="wbs_code", fieldtype="Data", label="WBS Code", insert_after="task_name", translatable=0, in_list_view=1),
            dict(fieldname="activity_type", fieldtype="Select", label="Activity Type", options="Task\nMilestone\nLevel of Effort\nWBS Summary", default="Task", insert_after="wbs_code"),
            dict(fieldname="constraint_type", fieldtype="Select", label="Constraint Type", options="\nSNET\nFNLT\nMSO\nMFO", insert_after="activity_type"),
            dict(fieldname="constraint_date", fieldtype="Date", label="Constraint Date", insert_after="constraint_type"),
            dict(fieldname="cpm_section", fieldtype="Section Break", label="Critical Path Method (computed)", insert_after="progress", collapsible=1),
            dict(fieldname="early_start", fieldtype="Date", label="Early Start", insert_after="cpm_section", read_only=1, in_list_view=1),
            dict(fieldname="early_finish", fieldtype="Date", label="Early Finish", insert_after="early_start", read_only=1),
            dict(fieldname="cpm_column_break", fieldtype="Column Break", insert_after="early_finish"),
            dict(fieldname="late_start", fieldtype="Date", label="Late Start", insert_after="cpm_column_break", read_only=1),
            dict(fieldname="late_finish", fieldtype="Date", label="Late Finish", insert_after="late_start", read_only=1),
            dict(fieldname="total_float", fieldtype="Float", label="Total Float (Days)", insert_after="late_finish", read_only=1, in_list_view=1),
            dict(fieldname="is_critical", fieldtype="Check", label="Is Critical", insert_after="total_float", read_only=1, in_list_view=1),
        ]
    }
    create_custom_fields(custom_fields, update=True)
