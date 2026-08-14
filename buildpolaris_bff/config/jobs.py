"""
BuildPolaris scheduled jobs (wired in hooks.scheduler_events).
Job failures MUST surface to an operator-visible channel (NFR-OBS.2).
"""
import frappe


def escalate_overdue_communications():
	"""FR-4.5: escalate overdue RFIs and Action Items via the native
	ToDo/notification engine. Runs daily."""
	from buildpolaris_bff.communications.services.escalation_service import escalate_overdue_items

	try:
		escalate_overdue_items()
	except Exception:
		frappe.log_error(title="Daily escalation job failed", message=frappe.get_traceback())


def closeout_lookahead_digest():
	"""Closeout phase: look-ahead digests to PM/Owner ahead of Substantial
	Completion (FR-7.x). Implemented in the Closeout phase."""
	pass


def schedule_health_check():
	"""FR-2.3: hourly DCMA health check across active Projects. Only logs
	when a Project actually has flagged findings (negative float, cycles,
	etc.) - an operator-visible warning (NFR-OBS.2), not a failure."""
	from buildpolaris_bff.scheduling.services.schedule_validation import run_health_check

	projects = frappe.get_all("Project", filters={"status": "Open"}, pluck="name")
	for project in projects:
		try:
			findings = run_health_check(project, user="Administrator")
			if findings["summary"]["total_flagged_items"] > 0:
				frappe.log_error(
					title=f"[SCHEDULE HEALTH] {project}: {findings['summary']['total_flagged_items']} finding(s)",
					message=frappe.as_json(findings),
				)
		except Exception:
			frappe.log_error(
				title=f"Schedule health check failed for {project}",
				message=frappe.get_traceback(),
			)
	frappe.db.commit()
