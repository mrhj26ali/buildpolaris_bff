import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

def execute():
    """
    FR-1, FR-2, FR-5: Extend native Task DocType with Scheduling fields.
    Runs exactly once per site via `bench migrate`.
    """
    custom_fields = {
        "Task": [
            dict(fieldname="wbs_code", fieldtype="Data", label="WBS Code", insert_after="task_name", translatable=0, in_list_view=1),
            dict(fieldname="activity_type", fieldtype="Select", label="Activity Type", options="Task\nMilestone\nLevel of Effort\nWBS Summary", default="Task", insert_after="wbs_code"),
            dict(fieldname="total_float", fieldtype="Float", label="Total Float (Days)", insert_after="progress", read_only=1, in_list_view=1),
            dict(fieldname="is_critical", fieldtype="Check", label="Is Critical", insert_after="total_float", read_only=1, in_list_view=1),
            dict(fieldname="constraint_type", fieldtype="Select", label="Constraint Type", options="\nSNET\nFNLT\nMSO\nMFO", insert_after="is_critical"),
            dict(fieldname="constraint_date", fieldtype="Date", label="Constraint Date", insert_after="constraint_type"),
        ]
    }
    create_custom_fields(custom_fields, update=True)