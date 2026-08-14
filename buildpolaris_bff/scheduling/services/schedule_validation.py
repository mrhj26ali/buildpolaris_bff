"""FR-2.3's on-demand DCMA check, and FR-2.7's slippage/critical-path
change notification."""
import frappe

from buildpolaris_bff.shared.permissions import assert_project_permission
from buildpolaris_bff.scheduling.services.cpm.dcma_checks import run_dcma_check


def run_health_check(project: str, user: str | None = None) -> dict:
	assert_project_permission(project, ptype="read", user=user)
	return run_dcma_check(project)


def notify_schedule_change(project: str, changed_tasks: list):
	"""FR-2.7: notify the PM and affected task owners via Frappe's native
	Notification Log - no bespoke notification table."""
	pm_users = frappe.get_all(
		"User Permission", filters={"allow": "Project", "for_value": project}, pluck="user",
	)
	recipients = set(pm_users)

	for change in changed_tasks:
		task_owner = frappe.db.get_value("Task", change["task"], "_assign")
		if task_owner:
			recipients.add(task_owner)

	if not recipients:
		return

	subject = f"Schedule change on Project {project}: {len(changed_tasks)} task(s) affected"
	lines = []
	for c in changed_tasks:
		bits = []
		if c["became_critical"]:
			bits.append("became critical")
		if c["slipped"]:
			bits.append(f"slipped (float now {c['total_float']}d)")
		lines.append(f"- {c['task']}: {', '.join(bits)}")
	message = "\n".join(lines)

	for user in recipients:
		try:
			frappe.get_doc({
				"doctype": "Notification Log",
				"for_user": user,
				"type": "Alert",
				"document_type": "Project",
				"document_name": project,
				"subject": subject,
				"email_content": message,
			}).insert(ignore_permissions=True)
		except Exception:
			frappe.log_error(title=f"Schedule-change notify failed for {user}", message=frappe.get_traceback())
