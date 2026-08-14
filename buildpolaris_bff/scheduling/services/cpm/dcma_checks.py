"""
DCMA 14-point schedule health check (FR-2.3), runnable on demand. Implements
the checks answerable from data BuildPolaris actually captures (logic,
leads, lags, relationship types, hard constraints, float, negative float,
high duration, invalid dates). Resource-loading-dependent checks (Resources,
Missed Tasks vs. baseline, CPLI, BEI) require actuals/resource data outside
this module's current scope and are intentionally NOT implemented as silent
zeros - they're listed under "not_implemented" so a report can't
misrepresent an unimplemented check as "passing."
"""
import frappe

from buildpolaris_bff.scheduling.services.cpm.critical_path import compute_cpm
from buildpolaris_bff.scheduling.services.cpm.network import build_network

HIGH_DURATION_THRESHOLD_DAYS = 44
HIGH_FLOAT_THRESHOLD_DAYS = 44


def run_dcma_check(project: str) -> dict:
	nodes = build_network(project)
	cpm = compute_cpm(project)

	findings = {
		"logic": _check_logic(nodes),
		"leads": _check_leads(project),
		"lags": _check_lags(project),
		"relationship_types": _check_relationship_types(project),
		"hard_constraints": _check_hard_constraints(project),
		"high_float": _check_high_float(cpm),
		"negative_float": _check_negative_float(cpm),
		"high_duration": _check_high_duration(nodes),
		"invalid_dates": _check_invalid_dates(nodes),
		"not_implemented": ["resources", "missed_tasks_vs_baseline", "cpli", "bei"],
	}
	total_flagged = sum(len(v) for k, v in findings.items() if isinstance(v, list) and k != "not_implemented")
	findings["summary"] = {"total_tasks": len(nodes), "total_flagged_items": total_flagged}
	return findings


def _check_logic(nodes: dict) -> list:
	if len(nodes) <= 1:
		return []
	return [n for n, node in nodes.items() if not node.predecessors and not node.successors]


def _check_leads(project: str) -> list:
	return frappe.get_all("Task Dependency", filters={"project": project, "lag_days": ["<", 0]},
	                       fields=["name", "predecessor", "successor", "lag_days"])


def _check_lags(project: str, threshold_days: int = 5) -> list:
	return frappe.get_all("Task Dependency", filters={"project": project, "lag_days": [">", threshold_days]},
	                       fields=["name", "predecessor", "successor", "lag_days"])


def _check_relationship_types(project: str) -> dict:
	rows = frappe.get_all("Task Dependency", filters={"project": project}, fields=["type"])
	total = len(rows) or 1
	fs_count = len([r for r in rows if r.type == "FS"])
	return {"total": len(rows), "fs_pct": round((fs_count / total) * 100, 1)}


def _check_hard_constraints(project: str) -> list:
	return frappe.get_all(
		"Task", filters={"project": project, "constraint_type": ["is", "set"]},
		fields=["name", "subject", "constraint_type", "constraint_date"],
	)


def _check_high_float(cpm: dict) -> list:
	return [{"task": n, "total_float": r["total_float"]} for n, r in cpm.items()
	        if r["total_float"] > HIGH_FLOAT_THRESHOLD_DAYS]


def _check_negative_float(cpm: dict) -> list:
	return [{"task": n, "total_float": r["total_float"]} for n, r in cpm.items()
	        if r["total_float"] < 0]


def _check_high_duration(nodes: dict) -> list:
	return [{"task": n, "duration": node.duration} for n, node in nodes.items()
	        if node.duration > HIGH_DURATION_THRESHOLD_DAYS]


def _check_invalid_dates(nodes: dict) -> list:
	return [n for n, node in nodes.items()
	        if node.exp_start_date and node.exp_end_date and node.exp_end_date < node.exp_start_date]
