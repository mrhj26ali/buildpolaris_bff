"""
FR-3.7: Earned Value Management - computed on read, never cached (the live
dashboard). EVM Snapshot (write-only, populated nightly) is a SEPARATE
trend table - never read back into this path (ERD §3.1 warning).
"""
import frappe
from frappe.utils import flt, getdate, today

from buildpolaris_bff.shared.permissions import assert_project_permission
from buildpolaris_bff.scheduling.services.schedule_service import get_project_percent_complete


def compute_evm(project: str, as_of_date=None, user: str | None = None) -> dict:
	assert_project_permission(project, ptype="read", user=user)
	as_of_date = getdate(as_of_date or today())

	budget_at_completion = flt(frappe.db.sql(
		"select coalesce(sum(budget_amount), 0) from `tabCost Code` where project = %s", project
	)[0][0])

	pct_complete = get_project_percent_complete(project)  # 0-100, schedule-derived
	planned_pct = _planned_pct_complete(project, as_of_date)

	planned_value = budget_at_completion * (planned_pct / 100.0)
	earned_value = budget_at_completion * (pct_complete / 100.0)
	actual_cost = _actual_cost(project, as_of_date)

	cpi = (earned_value / actual_cost) if actual_cost else None
	spi = (earned_value / planned_value) if planned_value else None

	return {
		"project": project,
		"as_of_date": as_of_date,
		"budget_at_completion": budget_at_completion,
		"planned_value": planned_value,
		"earned_value": earned_value,
		"actual_cost": actual_cost,
		"cpi": cpi,
		"spi": spi,
		"percent_complete": pct_complete,
	}


def _planned_pct_complete(project: str, as_of_date) -> float:
	"""Time-phased planned % based on Task exp_start/exp_end vs as_of_date,
	weighted by duration - the schedule's OWN definition of 'should be done
	by now', independent of actual reported progress."""
	tasks = frappe.get_all(
		"Task", filters={"project": project, "is_group": 0},
		fields=["exp_start_date", "exp_end_date"],
	)
	total_duration = 0
	planned_done = 0
	for t in tasks:
		if not t.exp_start_date or not t.exp_end_date:
			continue
		start, end = getdate(t.exp_start_date), getdate(t.exp_end_date)
		duration = max((end - start).days, 1)
		total_duration += duration
		if as_of_date >= end:
			planned_done += duration
		elif as_of_date > start:
			planned_done += min((as_of_date - start).days, duration)
	return round((planned_done / total_duration) * 100, 2) if total_duration else 0.0


def _actual_cost(project: str, as_of_date) -> float:
	"""Actual Cost sourced from Financials (approved Pay Applications) -
	the 'combining Financials with Scheduling' half of FR-3.7."""
	result = frappe.db.sql(
		"""select coalesce(sum(pal.work_completed_this_period + pal.materials_stored), 0)
		   from `tabPay Application Line` pal
		   inner join `tabPay Application` pa on pa.name = pal.parent
		   where pa.project = %s and pa.status in ('Approved', 'Paid') and pa.period_end <= %s""",
		(project, as_of_date),
	)
	return flt(result[0][0]) if result else 0.0


def capture_nightly_snapshot():
	"""Populates the write-only EVM Snapshot trend table (ARCH: nightly
	job). Never read back into compute_evm() above."""
	projects = frappe.get_all("Project", filters={"status": "Open"}, pluck="name")
	for project in projects:
		try:
			evm = compute_evm(project, user="Administrator")
			frappe.get_doc({
				"doctype": "EVM Snapshot",
				"project": project,
				"snapshot_date": today(),
				"planned_value": evm["planned_value"],
				"earned_value": evm["earned_value"],
				"actual_cost": evm["actual_cost"],
				"cpi": evm["cpi"] or 0,
				"spi": evm["spi"] or 0,
			}).insert(ignore_permissions=True)
		except Exception:
			frappe.log_error(title=f"EVM snapshot failed for {project}", message=frappe.get_traceback())
	frappe.db.commit()
