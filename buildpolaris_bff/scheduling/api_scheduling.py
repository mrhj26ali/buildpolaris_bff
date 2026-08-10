import json
import frappe
from frappe import _
from buildpolaris_bff.shared.api_utils import standard_response, handle_api_error
from buildpolaris_bff.shared.guards import require_authenticated_user
from buildpolaris_bff.scheduling.services.cpm_engine import calculate_cpm

@frappe.whitelist()
@require_authenticated_user
def run_cpm_engine(tasks, project_start_date):
    """
    Runs the CPM engine on a set of tasks and returns the calculated schedule.
    """
    try:
        if isinstance(tasks, str):
            tasks = json.loads(tasks)
            
        result = calculate_cpm(tasks, project_start_date)
        return standard_response(True, result, _("CPM calculation complete"))
    except Exception as e:
        return handle_api_error(e)

@frappe.whitelist()
@require_authenticated_user
def create_baseline(project, baseline_name):
    """
    Snapshots the current project schedule into a Schedule Baseline.
    """
    try:
        # Fetch current tasks for the project
        tasks = frappe.get_all(
            "Task", 
            filters={"project": project}, 
            fields=["name", "subject", "duration", "expected_start_date", "expected_end_date", "depends_on"]
        )
        
        baseline = frappe.get_doc({
            "doctype": "Schedule Baseline",
            "project": project,
            "baseline_name": baseline_name,
            "baseline_date": frappe.utils.now_datetime()
        }).insert(ignore_permissions=True)
        
        for task in tasks:
            frappe.get_doc({
                "doctype": "Baseline Activity Snapshot",
                "parent": baseline.name,
                "parenttype": "Schedule Baseline",
                "parentfield": "activities",
                "task": task.name,
                "subject": task.subject,
                "duration": task.duration,
                "baseline_start_date": task.expected_start_date,
                "baseline_end_date": task.expected_end_date
            }).insert(ignore_permissions=True)
            
        return standard_response(True, {"baseline": baseline.name}, _("Baseline created successfully"))
    except Exception as e:
        return handle_api_error(e)
