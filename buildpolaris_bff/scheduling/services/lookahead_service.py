"""FR-2.6: rolling 2-3 week look-ahead, filtered from the master schedule."""
import frappe
from frappe.utils import add_days, getdate, today

from buildpolaris_bff.shared.permissions import assert_project_permission


def get_lookahead(project: str, weeks: int = 3, as_of_date=None, user: str | None = None):
	assert_project_permission(project, ptype="read", user=user)

	start = getdate(as_of_date or today())
	end = add_days(start, weeks * 7)

	tasks = frappe.get_all(
		"Task",
		filters={
			"project": project, "is_group": 0,
			"exp_start_date": ["<=", end],
			"exp_end_date": [">=", start],
		},
		fields=["name", "subject", "exp_start_date", "exp_end_date", "progress",
		        "is_critical", "total_float"],
		order_by="exp_start_date asc",
	)

	weekly_buckets = []
	cursor = start
	for _ in range(weeks):
		week_end = add_days(cursor, 6)
		weekly_buckets.append({
			"week_start": cursor, "week_end": week_end,
			"tasks": [t for t in tasks if t.exp_start_date <= week_end and t.exp_end_date >= cursor],
		})
		cursor = add_days(cursor, 7)

	return {"project": project, "window_start": start, "window_end": end, "weeks": weekly_buckets}
