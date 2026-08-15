"""
NFR-AIGOV.3 / ARCH §4.3: re-enqueue anything still Queued or Failed past a
threshold age. Wired hourly (hooks.scheduler_events). A row that reached a
genuine Failed(status_detail) state (e.g. no extractable text layer) is
re-tried too, in case a later re-upload replaced the underlying File with a
readable version and this simply hasn't fired yet.
"""
import frappe
from frappe.utils import add_to_date, now_datetime

from buildpolaris_bff.ai_copilot.services.ingestion_trigger_service import (
	RETRY_THRESHOLD_MINUTES,
	run_ingestion_job,
)


def run():
	threshold = add_to_date(now_datetime(), minutes=-RETRY_THRESHOLD_MINUTES)
	rows = frappe.get_all(
		"AI Document Index",
		filters={"status": ["in", ["Queued", "Failed"]], "modified": ["<", threshold]},
		fields=["name"],
	)
	for row in rows:
		try:
			run_ingestion_job(row.name)
		except Exception:
			frappe.log_error(
				title=f"Retry ingestion failed for {row.name}", message=frappe.get_traceback()
			)
	frappe.db.commit()
