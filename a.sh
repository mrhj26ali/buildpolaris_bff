#!/usr/bin/env bash
# ============================================================================
# BuildPolaris BFF — PHASE 2b: scheduling/ + financials/ full implementation
# Run from: ~/frappe-bench/apps/buildpolaris_bff
# Requires: Phase 1 + Phase 2a already applied.
# ============================================================================
set -euo pipefail

ROOT="$HOME/frappe-bench/apps/buildpolaris_bff"
MOD="$ROOT/buildpolaris_bff"

if [ ! -d "$MOD/scheduling" ] || [ ! -d "$MOD/financials" ] || [ ! -f "$MOD/shared/permissions.py" ]; then
  echo "ERROR: expected Phase 1 + Phase 2a to already be applied."
  exit 1
fi

cd "$MOD"
echo "=== [1/6] patches: extend Task custom fields with CPM output fields ==="

cat > patches/v1_0/add_scheduling_custom_fields.py <<'PYEOF'
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
PYEOF

echo "=== [2/6] scheduling/ DocType JSONs ==="

cat > scheduling/doctype/task_dependency/task_dependency.json <<'JSONEOF'
{
 "actions": [],
 "autoname": "hash",
 "creation": "2026-08-13 00:00:00",
 "doctype": "DocType",
 "engine": "InnoDB",
 "field_order": ["project", "predecessor", "successor", "column_break_1", "type", "lag_days"],
 "fields": [
  {"fieldname": "project", "fieldtype": "Link", "label": "Project", "options": "Project", "reqd": 1, "in_list_view": 1},
  {"fieldname": "predecessor", "fieldtype": "Link", "label": "Predecessor", "options": "Task", "reqd": 1, "in_list_view": 1},
  {"fieldname": "successor", "fieldtype": "Link", "label": "Successor", "options": "Task", "reqd": 1, "in_list_view": 1},
  {"fieldname": "column_break_1", "fieldtype": "Column Break"},
  {"fieldname": "type", "fieldtype": "Select", "label": "Type", "options": "FS\nSS\nFF\nSF", "default": "FS", "reqd": 1, "in_list_view": 1},
  {"fieldname": "lag_days", "fieldtype": "Int", "label": "Lag (Days)", "default": "0"}
 ],
 "index_web_pages_for_search": 0,
 "links": [],
 "modified": "2026-08-13 00:00:00",
 "modified_by": "Administrator",
 "module": "Scheduling",
 "name": "Task Dependency",
 "owner": "Administrator",
 "permissions": [
  {"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1},
  {"role": "BuildPolaris Admin", "read": 1, "write": 1, "create": 1, "delete": 1},
  {"role": "BuildPolaris Project Manager", "read": 1, "write": 1, "create": 1, "delete": 1},
  {"role": "BuildPolaris Owner", "read": 1},
  {"role": "BuildPolaris Site Superintendent", "read": 1},
  {"role": "BuildPolaris Subcontractor", "read": 1}
 ],
 "sort_field": "modified",
 "sort_order": "DESC",
 "states": [],
 "track_changes": 1
}
JSONEOF

cat > scheduling/doctype/baseline_task_snapshot/baseline_task_snapshot.json <<'JSONEOF'
{
 "actions": [],
 "autoname": "hash",
 "creation": "2026-08-13 00:00:00",
 "doctype": "DocType",
 "engine": "InnoDB",
 "istable": 1,
 "field_order": ["task", "planned_start", "planned_finish", "planned_duration"],
 "fields": [
  {"fieldname": "task", "fieldtype": "Link", "label": "Task", "options": "Task", "reqd": 1, "in_list_view": 1},
  {"fieldname": "planned_start", "fieldtype": "Date", "label": "Planned Start", "in_list_view": 1},
  {"fieldname": "planned_finish", "fieldtype": "Date", "label": "Planned Finish", "in_list_view": 1},
  {"fieldname": "planned_duration", "fieldtype": "Int", "label": "Planned Duration (Days)", "in_list_view": 1}
 ],
 "index_web_pages_for_search": 0,
 "links": [],
 "modified": "2026-08-13 00:00:00",
 "modified_by": "Administrator",
 "module": "Scheduling",
 "name": "Baseline Task Snapshot",
 "owner": "Administrator",
 "permissions": [
  {"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1}
 ],
 "sort_field": "modified",
 "sort_order": "DESC",
 "states": [],
 "track_changes": 0
}
JSONEOF

cat > scheduling/doctype/schedule_baseline/schedule_baseline.json <<'JSONEOF'
{
 "actions": [],
 "autoname": "naming_series:",
 "creation": "2026-08-13 00:00:00",
 "doctype": "DocType",
 "engine": "InnoDB",
 "field_order": ["naming_series", "project", "label", "captured_at", "section_break_snapshots", "snapshots"],
 "fields": [
  {"fieldname": "naming_series", "fieldtype": "Select", "label": "Series", "options": "BASE-.YYYY.-.#####", "hidden": 1},
  {"fieldname": "project", "fieldtype": "Link", "label": "Project", "options": "Project", "reqd": 1, "in_list_view": 1},
  {"fieldname": "label", "fieldtype": "Data", "label": "Label", "reqd": 1, "in_list_view": 1},
  {"fieldname": "captured_at", "fieldtype": "Datetime", "label": "Captured At", "read_only": 1, "in_list_view": 1},
  {"fieldname": "section_break_snapshots", "fieldtype": "Section Break", "label": "Task Snapshots"},
  {"fieldname": "snapshots", "fieldtype": "Table", "label": "Snapshots", "options": "Baseline Task Snapshot"}
 ],
 "index_web_pages_for_search": 0,
 "links": [],
 "modified": "2026-08-13 00:00:00",
 "modified_by": "Administrator",
 "module": "Scheduling",
 "name": "Schedule Baseline",
 "owner": "Administrator",
 "permissions": [
  {"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1},
  {"role": "BuildPolaris Admin", "read": 1, "write": 1, "create": 1, "delete": 1},
  {"role": "BuildPolaris Project Manager", "read": 1, "write": 1, "create": 1},
  {"role": "BuildPolaris Owner", "read": 1}
 ],
 "sort_field": "modified",
 "sort_order": "DESC",
 "states": [],
 "track_changes": 1
}
JSONEOF

echo "=== [3/6] scheduling/ DocType controllers + cpm/ + services ==="

cat > scheduling/doctype/task_dependency/task_dependency.py <<'PYEOF'
import frappe
from frappe.model.document import Document

VALID_TYPES = {"FS", "SS", "FF", "SF"}


class TaskDependency(Document):
	def validate(self):
		if self.type not in VALID_TYPES:
			frappe.throw(f"type must be one of {VALID_TYPES}.")
		if self.predecessor == self.successor:
			frappe.throw("A task cannot depend on itself.")
PYEOF

cat > scheduling/doctype/schedule_baseline/schedule_baseline.py <<'PYEOF'
from frappe.model.document import Document


class ScheduleBaseline(Document):
	pass
PYEOF

cat > scheduling/doctype/baseline_task_snapshot/baseline_task_snapshot.py <<'PYEOF'
from frappe.model.document import Document


class BaselineTaskSnapshot(Document):
	pass
PYEOF

# ---------------------------------------------------------------------------
cat > scheduling/services/cpm/network.py <<'PYEOF'
"""
Builds an in-memory CPM network from native Task + Task Dependency records
for one Project. Shared by both the server-authoritative computation
(critical_path.py, called from schedule_service.py) and the what-if preview
path (what_if_service.py) - same algorithm, same code, so the two SERVER
call sites are guaranteed identical per FR-2.3 (client Web Worker parity is
a PWA-side concern, mirrored from this same algorithm/tests).
"""
from dataclasses import dataclass, field

import frappe
from frappe.utils import getdate


@dataclass
class TaskNode:
	name: str
	duration: int
	exp_start_date: object = None
	exp_end_date: object = None
	predecessors: list = field(default_factory=list)  # (pred_name, type, lag_days)
	successors: list = field(default_factory=list)    # (succ_name, type, lag_days)


def build_network(project: str, task_overrides: dict | None = None) -> dict:
	"""Returns {task_name: TaskNode}. `task_overrides` lets what_if_service
	substitute candidate duration/date edits without touching the DB."""
	task_overrides = task_overrides or {}

	tasks = frappe.get_all(
		"Task",
		filters={"project": project, "is_group": 0},
		fields=["name", "duration", "exp_start_date", "exp_end_date"],
	)

	nodes = {}
	for t in tasks:
		override = task_overrides.get(t.name, {})
		duration = override.get("duration", t.duration) or _infer_duration(t)
		start_val = override.get("exp_start_date", t.exp_start_date)
		end_val = override.get("exp_end_date", t.exp_end_date)
		nodes[t.name] = TaskNode(
			name=t.name,
			duration=max(int(duration or 1), 1),
			exp_start_date=getdate(start_val) if start_val else None,
			exp_end_date=getdate(end_val) if end_val else None,
		)

	deps = frappe.get_all(
		"Task Dependency", filters={"project": project},
		fields=["predecessor", "successor", "type", "lag_days"],
	)
	for d in deps:
		if d.predecessor not in nodes or d.successor not in nodes:
			continue  # dependency references a group task or a task outside this filter set
		nodes[d.predecessor].successors.append((d.successor, d.type, d.lag_days or 0))
		nodes[d.successor].predecessors.append((d.predecessor, d.type, d.lag_days or 0))

	return nodes


def _infer_duration(task_row) -> int:
	if task_row.exp_start_date and task_row.exp_end_date:
		return max((task_row.exp_end_date - task_row.exp_start_date).days, 1)
	return 1


def topological_order(nodes: dict) -> list:
	"""Kahn's algorithm. Raises ValueError on a cycle - CPM is undefined for
	cyclic logic; DCMA check #1 (logic) surfaces missing/bad logic
	separately as a health-check finding rather than a hard save-time
	failure, but a true cycle can't be topologically computed at all."""
	in_degree = {name: len(node.predecessors) for name, node in nodes.items()}
	queue = [name for name, deg in in_degree.items() if deg == 0]
	order = []

	while queue:
		current = queue.pop(0)
		order.append(current)
		for succ_name, _type, _lag in nodes[current].successors:
			in_degree[succ_name] -= 1
			if in_degree[succ_name] == 0:
				queue.append(succ_name)

	if len(order) != len(nodes):
		raise ValueError("Cyclic dependency detected - CPM cannot be computed.")

	return order
PYEOF

cat > scheduling/services/cpm/forward_pass.py <<'PYEOF'
"""Forward pass: Early Start / Early Finish per node, honoring FS/SS/FF/SF
typed lag (FR-2.2, FR-2.3)."""
from datetime import timedelta

from frappe.utils import getdate, today


def run_forward_pass(nodes: dict, order: list, project_start=None) -> dict:
	project_start = getdate(project_start or today())
	early = {}  # name -> (ES, EF)

	for name in order:
		node = nodes[name]
		if not node.predecessors:
			es = node.exp_start_date or project_start
		else:
			candidates = []
			for pred_name, dep_type, lag in node.predecessors:
				pred_es, pred_ef = early[pred_name]
				if dep_type == "FS":
					candidates.append(pred_ef + timedelta(days=lag))
				elif dep_type == "SS":
					candidates.append(pred_es + timedelta(days=lag))
				elif dep_type == "FF":
					candidates.append(pred_ef + timedelta(days=lag) - timedelta(days=node.duration))
				elif dep_type == "SF":
					candidates.append(pred_es + timedelta(days=lag) - timedelta(days=node.duration))
			es = max(candidates) if candidates else project_start
			if node.exp_start_date and node.exp_start_date > es:
				es = node.exp_start_date  # a hard constraint never lets CPM pull a task earlier than set
		ef = es + timedelta(days=node.duration)
		early[name] = (es, ef)

	return early
PYEOF

cat > scheduling/services/cpm/backward_pass.py <<'PYEOF'
"""Backward pass: Late Start / Late Finish per node."""
from datetime import timedelta


def run_backward_pass(nodes: dict, order: list, early: dict) -> dict:
	project_finish = max(ef for _es, ef in early.values()) if early else None
	late = {}

	for name in reversed(order):
		node = nodes[name]
		if not node.successors:
			lf = project_finish
		else:
			candidates = []
			for succ_name, dep_type, lag in node.successors:
				succ_ls, succ_lf = late[succ_name]
				if dep_type == "FS":
					candidates.append(succ_ls - timedelta(days=lag))
				elif dep_type == "SS":
					candidates.append(succ_ls - timedelta(days=lag) + timedelta(days=node.duration))
				elif dep_type == "FF":
					candidates.append(succ_lf - timedelta(days=lag))
				elif dep_type == "SF":
					candidates.append(succ_lf - timedelta(days=lag) + timedelta(days=node.duration))
			lf = min(candidates) if candidates else project_finish
		ls = lf - timedelta(days=node.duration)
		late[name] = (ls, lf)

	return late
PYEOF

cat > scheduling/services/cpm/critical_path.py <<'PYEOF'
"""
Orchestrates network -> forward pass -> backward pass -> float/critical
flag - the ONE authoritative CPM implementation (FR-2.3). Both the server
persistence path (schedule_service.py) and the server-side what-if preview
(what_if_service.py) call this same function, so there is exactly one
algorithm to keep in sync with the PWA's Web Worker mirror.
"""
from buildpolaris_bff.scheduling.services.cpm.backward_pass import run_backward_pass
from buildpolaris_bff.scheduling.services.cpm.forward_pass import run_forward_pass
from buildpolaris_bff.scheduling.services.cpm.network import build_network, topological_order


def compute_cpm(project: str, task_overrides: dict | None = None, project_start=None) -> dict:
	"""Returns {task_name: {early_start, early_finish, late_start,
	late_finish, total_float, is_critical}}."""
	nodes = build_network(project, task_overrides=task_overrides)
	if not nodes:
		return {}

	order = topological_order(nodes)
	early = run_forward_pass(nodes, order, project_start=project_start)
	late = run_backward_pass(nodes, order, early)

	results = {}
	for name in nodes:
		es, ef = early[name]
		ls, lf = late[name]
		total_float = (ls - es).days
		results[name] = {
			"early_start": es,
			"early_finish": ef,
			"late_start": ls,
			"late_finish": lf,
			"total_float": total_float,
			"is_critical": total_float <= 0,
		}
	return results
PYEOF

cat > scheduling/services/cpm/dcma_checks.py <<'PYEOF'
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
PYEOF

# ---------------------------------------------------------------------------
cat > scheduling/services/schedule_task_service.py <<'PYEOF'
"""FR-2.1: WBS as native ERPNext Task records under a Project."""
import frappe

from buildpolaris_bff.shared.permissions import assert_project_permission, assert_role


def create_task(project, subject, exp_start_date=None, exp_end_date=None, duration=None,
                 is_group=0, parent_task=None, created_by=None):
	created_by = created_by or frappe.session.user
	assert_project_permission(project, ptype="write", user=created_by)
	assert_role("BuildPolaris Project Manager", "BuildPolaris Admin", user=created_by)

	doc = frappe.get_doc({
		"doctype": "Task",
		"project": project,
		"subject": subject,
		"exp_start_date": exp_start_date,
		"exp_end_date": exp_end_date,
		"duration": duration,
		"is_group": is_group,
		"parent_task": parent_task,
	})
	doc.insert()
	return doc.as_dict()


def update_task(task: str, updates: dict, updated_by: str | None = None):
	updated_by = updated_by or frappe.session.user
	doc = frappe.get_doc("Task", task)
	assert_project_permission(doc.project, ptype="write", user=updated_by)
	assert_role("BuildPolaris Project Manager", "BuildPolaris Admin", user=updated_by)

	allowed_fields = {"subject", "exp_start_date", "exp_end_date", "duration", "progress",
	                   "wbs_code", "activity_type", "constraint_type", "constraint_date"}
	for k, v in updates.items():
		if k in allowed_fields:
			doc.set(k, v)
	doc.save()
	return doc.as_dict()


def list_tasks(project: str, user: str | None = None):
	assert_project_permission(project, ptype="read", user=user)
	return frappe.get_all(
		"Task",
		filters={"project": project},
		fields=["name", "subject", "exp_start_date", "exp_end_date", "duration", "progress",
		        "is_group", "parent_task", "early_start", "early_finish", "late_start",
		        "late_finish", "total_float", "is_critical", "wbs_code", "activity_type"],
		order_by="exp_start_date asc",
	)
PYEOF

cat > scheduling/services/task_dependency_service.py <<'PYEOF'
"""
FR-2.2: typed dependencies with lag, held in Task Dependency (native
Task.depends_on can't type or lag). Every save mirrors a simplified entry
back into Task.depends_on so ERPNext's own Task/Gantt views stay consistent
for anyone who opens the Desk UI directly.
"""
import frappe

from buildpolaris_bff.shared.exceptions import ValidationError
from buildpolaris_bff.shared.permissions import assert_project_permission, assert_role

VALID_TYPES = {"FS", "SS", "FF", "SF"}


def create_dependency(project, predecessor, successor, type="FS", lag_days=0, created_by=None):
	created_by = created_by or frappe.session.user
	assert_project_permission(project, ptype="write", user=created_by)
	assert_role("BuildPolaris Project Manager", "BuildPolaris Admin", user=created_by)

	if type not in VALID_TYPES:
		raise ValidationError(f"type must be one of {VALID_TYPES}.")
	if predecessor == successor:
		raise ValidationError("A task cannot depend on itself.")
	if frappe.db.exists("Task Dependency", {"predecessor": predecessor, "successor": successor}):
		raise ValidationError("This dependency already exists.")

	_assert_no_cycle(project, predecessor, successor)

	doc = frappe.get_doc({
		"doctype": "Task Dependency",
		"project": project,
		"predecessor": predecessor,
		"successor": successor,
		"type": type,
		"lag_days": lag_days,
	})
	doc.insert()

	_mirror_to_native_task(successor, predecessor)
	return doc.as_dict()


def delete_dependency(dependency: str, deleted_by: str | None = None):
	deleted_by = deleted_by or frappe.session.user
	doc = frappe.get_doc("Task Dependency", dependency)
	assert_project_permission(doc.project, ptype="write", user=deleted_by)
	assert_role("BuildPolaris Project Manager", "BuildPolaris Admin", user=deleted_by)

	predecessor, successor = doc.predecessor, doc.successor
	frappe.delete_doc("Task Dependency", dependency, ignore_permissions=True)
	_unmirror_from_native_task(successor, predecessor)
	return {"deleted": dependency}


def _mirror_to_native_task(successor: str, predecessor: str):
	task_doc = frappe.get_doc("Task", successor)
	existing = {row.task for row in (task_doc.get("depends_on") or [])}
	if predecessor not in existing:
		task_doc.append("depends_on", {"task": predecessor})
		task_doc.flags.ignore_links = True
		task_doc.save(ignore_permissions=True)


def _unmirror_from_native_task(successor: str, predecessor: str):
	task_doc = frappe.get_doc("Task", successor)
	rows = task_doc.get("depends_on") or []
	task_doc.set("depends_on", [r for r in rows if r.task != predecessor])
	task_doc.save(ignore_permissions=True)


def _assert_no_cycle(project: str, predecessor: str, successor: str):
	"""BFS from `successor` forward through existing dependencies - if we
	reach `predecessor`, adding predecessor->successor would close a cycle."""
	edges = frappe.get_all("Task Dependency", filters={"project": project},
	                        fields=["predecessor", "successor"])
	adjacency = {}
	for e in edges:
		adjacency.setdefault(e.predecessor, []).append(e.successor)

	stack = [successor]
	seen = set()
	while stack:
		current = stack.pop()
		if current == predecessor:
			raise ValidationError("This dependency would create a cyclic schedule (not computable).")
		if current in seen:
			continue
		seen.add(current)
		stack.extend(adjacency.get(current, []))
PYEOF

cat > scheduling/services/schedule_service.py <<'PYEOF'
"""
Orchestrates CPM recomputation and persists results to native Task fields
(FR-2.3). Also the schedule-percent-complete read used by
financials/services/evm_service.py (FR-3.7's Scheduling half).
"""
import frappe
from frappe.utils import flt

from buildpolaris_bff.shared.permissions import assert_project_permission
from buildpolaris_bff.scheduling.services.cpm.critical_path import compute_cpm


def recompute_schedule(project: str, triggered_by: str | None = None) -> dict:
	"""FR-2.3: server-side CPM is the authoritative result. Persists
	early/late start/finish, total_float, is_critical onto Task, and fires
	FR-2.7 notifications when slippage or a critical-path change is
	detected relative to the PRIOR persisted state."""
	triggered_by = triggered_by or frappe.session.user
	assert_project_permission(project, ptype="write", user=triggered_by)

	previous = {
		row.name: {"total_float": row.total_float, "is_critical": row.is_critical}
		for row in frappe.get_all(
			"Task", filters={"project": project, "is_group": 0},
			fields=["name", "total_float", "is_critical"],
		)
	}

	results = compute_cpm(project)

	changed_tasks = []
	for task_name, r in results.items():
		before = previous.get(task_name, {})
		became_critical = (not before.get("is_critical")) and r["is_critical"]
		slipped = before.get("total_float") is not None and r["total_float"] < flt(before.get("total_float"))
		if became_critical or slipped:
			changed_tasks.append({
				"task": task_name, "became_critical": became_critical, "slipped": slipped,
				"total_float": r["total_float"],
			})

		frappe.db.set_value("Task", task_name, {
			"early_start": r["early_start"],
			"early_finish": r["early_finish"],
			"late_start": r["late_start"],
			"late_finish": r["late_finish"],
			"total_float": r["total_float"],
			"is_critical": 1 if r["is_critical"] else 0,
		}, update_modified=False)

	frappe.db.commit()

	if changed_tasks:
		from buildpolaris_bff.scheduling.services.schedule_validation import notify_schedule_change
		notify_schedule_change(project, changed_tasks)

	return results


def get_project_percent_complete(project: str, as_of_date=None, user: str | None = None) -> float:
	"""Duration-weighted average of Task.progress - the schedule-derived
	half of FR-3.7's EVM calculation."""
	if user:
		assert_project_permission(project, ptype="read", user=user)

	tasks = frappe.get_all(
		"Task", filters={"project": project, "is_group": 0},
		fields=["duration", "progress"],
	)
	total_duration = sum(flt(t.duration) or 1 for t in tasks)
	if not total_duration:
		return 0.0
	weighted = sum((flt(t.duration) or 1) * flt(t.progress) for t in tasks)
	return round(weighted / total_duration, 2)
PYEOF

cat > scheduling/services/baseline_service.py <<'PYEOF'
"""FR-2.4: snapshot the current schedule as a named Baseline."""
import frappe
from frappe.utils import now_datetime

from buildpolaris_bff.shared.permissions import assert_project_permission, assert_role


def create_baseline(project: str, label: str, created_by: str | None = None):
	created_by = created_by or frappe.session.user
	assert_project_permission(project, ptype="write", user=created_by)
	assert_role("BuildPolaris Project Manager", "BuildPolaris Admin", user=created_by)

	tasks = frappe.get_all(
		"Task", filters={"project": project, "is_group": 0},
		fields=["name", "exp_start_date", "exp_end_date", "duration"],
	)

	doc = frappe.get_doc({
		"doctype": "Schedule Baseline",
		"naming_series": "BASE-.YYYY.-.#####",
		"project": project,
		"label": label,
		"captured_at": now_datetime(),
	})
	for t in tasks:
		doc.append("snapshots", {
			"task": t.name,
			"planned_start": t.exp_start_date,
			"planned_finish": t.exp_end_date,
			"planned_duration": t.duration,
		})
	doc.insert()
	return doc.as_dict()


def get_baseline_variance(baseline: str, user: str | None = None):
	"""Supports the ERD's stated purpose ('variance tracking over time') -
	compares each snapshot's planned dates to the task's CURRENT dates."""
	doc = frappe.get_doc("Schedule Baseline", baseline)
	assert_project_permission(doc.project, ptype="read", user=user)

	variance = []
	for snap in doc.snapshots:
		current = frappe.db.get_value("Task", snap.task, ["exp_start_date", "exp_end_date"], as_dict=True)
		if not current:
			continue
		variance.append({
			"task": snap.task,
			"planned_start": snap.planned_start,
			"current_start": current.exp_start_date,
			"start_variance_days": (current.exp_start_date - snap.planned_start).days
				if (current.exp_start_date and snap.planned_start) else None,
			"planned_finish": snap.planned_finish,
			"current_finish": current.exp_end_date,
			"finish_variance_days": (current.exp_end_date - snap.planned_finish).days
				if (current.exp_end_date and snap.planned_finish) else None,
		})
	return variance


def list_baselines(project: str, user: str | None = None):
	assert_project_permission(project, ptype="read", user=user)
	return frappe.get_all("Schedule Baseline", filters={"project": project},
	                       fields=["name", "label", "captured_at"], order_by="captured_at desc")
PYEOF

cat > scheduling/services/what_if_service.py <<'PYEOF'
"""
Server-side what-if preview (FR-2.3): recomputes CPM against candidate task
edits WITHOUT persisting - never writes to Task. Uses the exact same cpm/
package as the persisted path, so results are guaranteed identical to
recompute_schedule()'s algorithm (only the input differs).
"""
from buildpolaris_bff.shared.permissions import assert_project_permission
from buildpolaris_bff.scheduling.services.cpm.critical_path import compute_cpm


def preview_schedule_change(project: str, task_edits: list, user: str | None = None) -> dict:
	"""task_edits: [{"task": <name>, "duration": int?, "exp_start_date": date?,
	"exp_end_date": date?}, ...]"""
	assert_project_permission(project, ptype="read", user=user)

	overrides = {edit["task"]: {k: v for k, v in edit.items() if k != "task"} for edit in task_edits}
	return compute_cpm(project, task_overrides=overrides)
PYEOF

cat > scheduling/services/lookahead_service.py <<'PYEOF'
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
PYEOF

cat > scheduling/services/schedule_validation.py <<'PYEOF'
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
PYEOF

cat > scheduling/api.py <<'PYEOF'
"""Scheduling - HTTP adapters only (NFR-MAINT.1)."""
import frappe

from buildpolaris_bff.shared.api_envelope import success
from buildpolaris_bff.scheduling.services import (
	baseline_service,
	lookahead_service,
	schedule_service,
	schedule_task_service,
	schedule_validation,
	task_dependency_service,
	what_if_service,
)


@frappe.whitelist()
def create_task(project, subject, exp_start_date=None, exp_end_date=None, duration=None,
                 is_group=0, parent_task=None):
	return success(schedule_task_service.create_task(
		project, subject, exp_start_date, exp_end_date, duration, is_group, parent_task
	))


@frappe.whitelist()
def update_task(task, updates):
	if isinstance(updates, str):
		updates = frappe.parse_json(updates)
	return success(schedule_task_service.update_task(task, updates))


@frappe.whitelist()
def list_tasks(project):
	return success(schedule_task_service.list_tasks(project))


@frappe.whitelist()
def create_dependency(project, predecessor, successor, type="FS", lag_days=0):
	return success(task_dependency_service.create_dependency(project, predecessor, successor, type, int(lag_days)))


@frappe.whitelist()
def delete_dependency(dependency):
	return success(task_dependency_service.delete_dependency(dependency))


@frappe.whitelist()
def recompute_schedule(project):
	return success(schedule_service.recompute_schedule(project))


@frappe.whitelist()
def preview_schedule_change(project, task_edits):
	if isinstance(task_edits, str):
		task_edits = frappe.parse_json(task_edits)
	return success(what_if_service.preview_schedule_change(project, task_edits))


@frappe.whitelist()
def run_health_check(project):
	return success(schedule_validation.run_health_check(project))


@frappe.whitelist()
def create_baseline(project, label):
	return success(baseline_service.create_baseline(project, label))


@frappe.whitelist()
def list_baselines(project):
	return success(baseline_service.list_baselines(project))


@frappe.whitelist()
def get_baseline_variance(baseline):
	return success(baseline_service.get_baseline_variance(baseline))


@frappe.whitelist()
def get_lookahead(project, weeks=3, as_of_date=None):
	return success(lookahead_service.get_lookahead(project, int(weeks), as_of_date))
PYEOF

echo "=== [4/6] financials/ DocType JSONs ==="

cat > financials/doctype/cost_code/cost_code.json <<'JSONEOF'
{
 "actions": [],
 "autoname": "naming_series:",
 "creation": "2026-08-13 00:00:00",
 "doctype": "DocType",
 "engine": "InnoDB",
 "field_order": ["naming_series", "project", "code", "cost_center", "column_break_1", "description", "budget_amount"],
 "fields": [
  {"fieldname": "naming_series", "fieldtype": "Select", "label": "Series", "options": "CC-.YYYY.-.#####", "hidden": 1},
  {"fieldname": "project", "fieldtype": "Link", "label": "Project", "options": "Project", "reqd": 1, "in_list_view": 1},
  {"fieldname": "code", "fieldtype": "Data", "label": "Code", "reqd": 1, "in_list_view": 1},
  {"fieldname": "cost_center", "fieldtype": "Link", "label": "Cost Center", "options": "Cost Center"},
  {"fieldname": "column_break_1", "fieldtype": "Column Break"},
  {"fieldname": "description", "fieldtype": "Small Text", "label": "Description"},
  {"fieldname": "budget_amount", "fieldtype": "Currency", "label": "Budget Amount", "reqd": 1, "permlevel": 1, "in_list_view": 1}
 ],
 "index_web_pages_for_search": 0,
 "links": [],
 "modified": "2026-08-13 00:00:00",
 "modified_by": "Administrator",
 "module": "Financials",
 "name": "Cost Code",
 "owner": "Administrator",
 "permissions": [
  {"role": "System Manager", "permlevel": 0, "read": 1, "write": 1, "create": 1, "delete": 1},
  {"role": "System Manager", "permlevel": 1, "read": 1, "write": 1},
  {"role": "BuildPolaris Admin", "permlevel": 0, "read": 1, "write": 1, "create": 1, "delete": 1},
  {"role": "BuildPolaris Admin", "permlevel": 1, "read": 1, "write": 1},
  {"role": "BuildPolaris Project Manager", "permlevel": 0, "read": 1, "write": 1, "create": 1},
  {"role": "BuildPolaris Project Manager", "permlevel": 1, "read": 1, "write": 1},
  {"role": "BuildPolaris Owner", "permlevel": 0, "read": 1},
  {"role": "BuildPolaris Owner", "permlevel": 1, "read": 1},
  {"role": "BuildPolaris Accounting", "permlevel": 0, "read": 1},
  {"role": "BuildPolaris Accounting", "permlevel": 1, "read": 1},
  {"role": "BuildPolaris Subcontractor", "permlevel": 0, "read": 1}
 ],
 "sort_field": "modified",
 "sort_order": "DESC",
 "states": [],
 "track_changes": 1
}
JSONEOF

cat > financials/doctype/commitment/commitment.json <<'JSONEOF'
{
 "actions": [],
 "autoname": "naming_series:",
 "creation": "2026-08-13 00:00:00",
 "doctype": "DocType",
 "engine": "InnoDB",
 "field_order": [
  "naming_series", "project", "cost_code", "supplier", "type", "status",
  "column_break_1", "original_amount", "revised_amount", "purchase_order",
  "section_break_approval", "approved_by", "approved_at", "is_immutable"
 ],
 "fields": [
  {"fieldname": "naming_series", "fieldtype": "Select", "label": "Series", "options": "COMM-.YYYY.-.#####", "hidden": 1},
  {"fieldname": "project", "fieldtype": "Link", "label": "Project", "options": "Project", "reqd": 1, "in_list_view": 1},
  {"fieldname": "cost_code", "fieldtype": "Link", "label": "Cost Code", "options": "Cost Code", "reqd": 1, "in_list_view": 1},
  {"fieldname": "supplier", "fieldtype": "Link", "label": "Supplier", "options": "Supplier", "reqd": 1, "in_list_view": 1},
  {"fieldname": "type", "fieldtype": "Select", "label": "Type", "options": "Subcontract\nPurchaseOrder", "reqd": 1},
  {"fieldname": "status", "fieldtype": "Select", "label": "Status", "options": "Draft\nPendingApproval\nApproved\nRejected", "default": "Draft", "in_list_view": 1},
  {"fieldname": "column_break_1", "fieldtype": "Column Break"},
  {"fieldname": "original_amount", "fieldtype": "Currency", "label": "Original Amount", "reqd": 1, "permlevel": 1},
  {"fieldname": "revised_amount", "fieldtype": "Currency", "label": "Revised Amount", "read_only": 1, "permlevel": 1},
  {"fieldname": "purchase_order", "fieldtype": "Link", "label": "Purchase Order", "options": "Purchase Order", "read_only": 1},
  {"fieldname": "section_break_approval", "fieldtype": "Section Break", "label": "Approval"},
  {"fieldname": "approved_by", "fieldtype": "Link", "label": "Approved By", "options": "User", "read_only": 1},
  {"fieldname": "approved_at", "fieldtype": "Datetime", "label": "Approved At", "read_only": 1},
  {"fieldname": "is_immutable", "fieldtype": "Check", "label": "Is Immutable", "read_only": 1, "default": "0"}
 ],
 "index_web_pages_for_search": 0,
 "links": [],
 "modified": "2026-08-13 00:00:00",
 "modified_by": "Administrator",
 "module": "Financials",
 "name": "Commitment",
 "owner": "Administrator",
 "permissions": [
  {"role": "System Manager", "permlevel": 0, "read": 1, "write": 1, "create": 1, "delete": 1},
  {"role": "System Manager", "permlevel": 1, "read": 1, "write": 1},
  {"role": "BuildPolaris Admin", "permlevel": 0, "read": 1, "write": 1, "create": 1, "delete": 1},
  {"role": "BuildPolaris Admin", "permlevel": 1, "read": 1, "write": 1},
  {"role": "BuildPolaris Project Manager", "permlevel": 0, "read": 1, "write": 1, "create": 1},
  {"role": "BuildPolaris Project Manager", "permlevel": 1, "read": 1, "write": 1},
  {"role": "BuildPolaris Owner", "permlevel": 0, "read": 1},
  {"role": "BuildPolaris Owner", "permlevel": 1, "read": 1},
  {"role": "BuildPolaris Accounting", "permlevel": 0, "read": 1, "write": 1},
  {"role": "BuildPolaris Accounting", "permlevel": 1, "read": 1, "write": 1},
  {"role": "BuildPolaris Subcontractor", "permlevel": 0, "read": 1}
 ],
 "sort_field": "modified",
 "sort_order": "DESC",
 "states": [],
 "track_changes": 1
}
JSONEOF

cat > financials/doctype/change_event/change_event.json <<'JSONEOF'
{
 "actions": [],
 "autoname": "naming_series:",
 "creation": "2026-08-13 00:00:00",
 "doctype": "DocType",
 "engine": "InnoDB",
 "field_order": [
  "naming_series", "project", "commitment", "originating_rfi", "category",
  "column_break_1", "amount_delta", "status", "approved_by", "is_immutable",
  "section_break_reason", "outcome_reason"
 ],
 "fields": [
  {"fieldname": "naming_series", "fieldtype": "Select", "label": "Series", "options": "CE-.YYYY.-.#####", "hidden": 1},
  {"fieldname": "project", "fieldtype": "Link", "label": "Project", "options": "Project", "reqd": 1, "in_list_view": 1},
  {"fieldname": "commitment", "fieldtype": "Link", "label": "Commitment", "options": "Commitment", "reqd": 1, "in_list_view": 1},
  {"fieldname": "originating_rfi", "fieldtype": "Link", "label": "Originating RFI", "options": "RFI"},
  {"fieldname": "category", "fieldtype": "Select", "label": "Category", "options": "ScopeGap\nDesignError\nFieldCondition\nOwnerRequest\nOther", "reqd": 1, "in_list_view": 1},
  {"fieldname": "column_break_1", "fieldtype": "Column Break"},
  {"fieldname": "amount_delta", "fieldtype": "Currency", "label": "Amount Delta", "reqd": 1, "in_list_view": 1},
  {"fieldname": "status", "fieldtype": "Select", "label": "Status", "options": "Open\nApproved\nRejected", "default": "Open", "in_list_view": 1},
  {"fieldname": "approved_by", "fieldtype": "Link", "label": "Approved By", "options": "User", "read_only": 1},
  {"fieldname": "is_immutable", "fieldtype": "Check", "label": "Is Immutable", "read_only": 1, "default": "0"},
  {"fieldname": "section_break_reason", "fieldtype": "Section Break", "label": "Outcome"},
  {"fieldname": "outcome_reason", "fieldtype": "Text", "label": "Outcome Reason"}
 ],
 "index_web_pages_for_search": 0,
 "links": [],
 "modified": "2026-08-13 00:00:00",
 "modified_by": "Administrator",
 "module": "Financials",
 "name": "Change Event",
 "owner": "Administrator",
 "permissions": [
  {"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1},
  {"role": "BuildPolaris Admin", "read": 1, "write": 1, "create": 1, "delete": 1},
  {"role": "BuildPolaris Project Manager", "read": 1, "write": 1, "create": 1},
  {"role": "BuildPolaris Owner", "read": 1, "write": 1},
  {"role": "BuildPolaris Accounting", "read": 1},
  {"role": "BuildPolaris Subcontractor", "read": 1}
 ],
 "sort_field": "modified",
 "sort_order": "DESC",
 "states": [],
 "track_changes": 1
}
JSONEOF

cat > financials/doctype/pay_application_line/pay_application_line.json <<'JSONEOF'
{
 "actions": [],
 "autoname": "hash",
 "creation": "2026-08-13 00:00:00",
 "doctype": "DocType",
 "engine": "InnoDB",
 "istable": 1,
 "field_order": ["cost_code", "scheduled_value", "work_completed_this_period", "materials_stored", "pct_complete"],
 "fields": [
  {"fieldname": "cost_code", "fieldtype": "Link", "label": "Cost Code", "options": "Cost Code", "reqd": 1, "in_list_view": 1},
  {"fieldname": "scheduled_value", "fieldtype": "Currency", "label": "Scheduled Value", "reqd": 1, "in_list_view": 1},
  {"fieldname": "work_completed_this_period", "fieldtype": "Currency", "label": "Work Completed This Period", "in_list_view": 1},
  {"fieldname": "materials_stored", "fieldtype": "Currency", "label": "Materials Stored", "in_list_view": 1},
  {"fieldname": "pct_complete", "fieldtype": "Percent", "label": "% Complete", "read_only": 1, "in_list_view": 1}
 ],
 "index_web_pages_for_search": 0,
 "links": [],
 "modified": "2026-08-13 00:00:00",
 "modified_by": "Administrator",
 "module": "Financials",
 "name": "Pay Application Line",
 "owner": "Administrator",
 "permissions": [
  {"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1}
 ],
 "sort_field": "modified",
 "sort_order": "DESC",
 "states": [],
 "track_changes": 0
}
JSONEOF

cat > financials/doctype/pay_application/pay_application.json <<'JSONEOF'
{
 "actions": [],
 "autoname": "naming_series:",
 "creation": "2026-08-13 00:00:00",
 "doctype": "DocType",
 "engine": "InnoDB",
 "field_order": [
  "naming_series", "commitment", "project", "period_end", "retainage_pct",
  "column_break_1", "status", "purchase_invoice", "payment_entry",
  "section_break_lines", "lines"
 ],
 "fields": [
  {"fieldname": "naming_series", "fieldtype": "Select", "label": "Series", "options": "PA-.YYYY.-.#####", "hidden": 1},
  {"fieldname": "commitment", "fieldtype": "Link", "label": "Commitment", "options": "Commitment", "reqd": 1, "in_list_view": 1},
  {"fieldname": "project", "fieldtype": "Link", "label": "Project", "options": "Project", "read_only": 1, "fetch_from": "commitment.project", "in_list_view": 1},
  {"fieldname": "period_end", "fieldtype": "Date", "label": "Period End", "reqd": 1, "in_list_view": 1},
  {"fieldname": "retainage_pct", "fieldtype": "Percent", "label": "Retainage %", "default": "10"},
  {"fieldname": "column_break_1", "fieldtype": "Column Break"},
  {"fieldname": "status", "fieldtype": "Select", "label": "Status", "options": "Draft\nPendingApproval\nApproved\nRejected\nPaid", "default": "Draft", "in_list_view": 1},
  {"fieldname": "purchase_invoice", "fieldtype": "Link", "label": "Purchase Invoice", "options": "Purchase Invoice", "read_only": 1},
  {"fieldname": "payment_entry", "fieldtype": "Link", "label": "Payment Entry", "options": "Payment Entry", "read_only": 1},
  {"fieldname": "section_break_lines", "fieldtype": "Section Break", "label": "Schedule of Values"},
  {"fieldname": "lines", "fieldtype": "Table", "label": "Lines", "options": "Pay Application Line"}
 ],
 "index_web_pages_for_search": 0,
 "links": [],
 "modified": "2026-08-13 00:00:00",
 "modified_by": "Administrator",
 "module": "Financials",
 "name": "Pay Application",
 "owner": "Administrator",
 "permissions": [
  {"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1},
  {"role": "BuildPolaris Admin", "read": 1, "write": 1, "create": 1, "delete": 1},
  {"role": "BuildPolaris Project Manager", "read": 1, "write": 1, "create": 1},
  {"role": "BuildPolaris Owner", "read": 1},
  {"role": "BuildPolaris Accounting", "read": 1, "write": 1},
  {"role": "BuildPolaris Subcontractor", "read": 1, "write": 1, "create": 1, "if_owner": 1}
 ],
 "sort_field": "modified",
 "sort_order": "DESC",
 "states": [],
 "track_changes": 1
}
JSONEOF

cat > financials/doctype/evm_snapshot/evm_snapshot.json <<'JSONEOF'
{
 "actions": [],
 "autoname": "hash",
 "creation": "2026-08-13 00:00:00",
 "doctype": "DocType",
 "engine": "InnoDB",
 "field_order": [
  "project", "snapshot_date", "column_break_1", "planned_value", "earned_value",
  "actual_cost", "section_break_indices", "cpi", "spi"
 ],
 "fields": [
  {"fieldname": "project", "fieldtype": "Link", "label": "Project", "options": "Project", "reqd": 1, "in_list_view": 1},
  {"fieldname": "snapshot_date", "fieldtype": "Date", "label": "Snapshot Date", "reqd": 1, "in_list_view": 1},
  {"fieldname": "column_break_1", "fieldtype": "Column Break"},
  {"fieldname": "planned_value", "fieldtype": "Currency", "label": "Planned Value"},
  {"fieldname": "earned_value", "fieldtype": "Currency", "label": "Earned Value"},
  {"fieldname": "actual_cost", "fieldtype": "Currency", "label": "Actual Cost"},
  {"fieldname": "section_break_indices", "fieldtype": "Section Break", "label": "Indices"},
  {"fieldname": "cpi", "fieldtype": "Float", "label": "CPI", "precision": "4"},
  {"fieldname": "spi", "fieldtype": "Float", "label": "SPI", "precision": "4"}
 ],
 "index_web_pages_for_search": 0,
 "links": [],
 "modified": "2026-08-13 00:00:00",
 "modified_by": "Administrator",
 "module": "Financials",
 "name": "EVM Snapshot",
 "owner": "Administrator",
 "permissions": [
  {"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1},
  {"role": "BuildPolaris Admin", "read": 1, "write": 1, "create": 1, "delete": 1},
  {"role": "BuildPolaris Project Manager", "read": 1},
  {"role": "BuildPolaris Owner", "read": 1}
 ],
 "sort_field": "modified",
 "sort_order": "DESC",
 "states": [],
 "track_changes": 0
}
JSONEOF

echo "=== [5/6] financials/ DocType controllers + services ==="

cat > financials/doctype/cost_code/cost_code.py <<'PYEOF'
import frappe
from frappe.model.document import Document


class CostCode(Document):
	def validate(self):
		if self.budget_amount is not None and self.budget_amount < 0:
			frappe.throw("Budget amount cannot be negative.")
PYEOF

cat > financials/doctype/commitment/commitment.py <<'PYEOF'
import frappe
from frappe.model.document import Document

PROTECTED_FIELDS = ["cost_code", "supplier", "type", "original_amount", "revised_amount"]


class Commitment(Document):
	def validate(self):
		if not self.revised_amount:
			self.revised_amount = self.original_amount
		self._enforce_immutability()

	def _enforce_immutability(self):
		"""FR-3.8: once Approved, immutable except through the defined
		amendment flow (financials/services/change_event_service.py sets
		flags.via_amendment before touching revised_amount)."""
		if self.is_new() or not self.is_immutable:
			return
		if self.flags.get("via_amendment"):
			return
		doc_before = self.get_doc_before_save()
		if not doc_before:
			return
		for f in PROTECTED_FIELDS:
			if self.get(f) != doc_before.get(f):
				frappe.throw(
					f"Cannot modify '{f}' on an approved, immutable Commitment "
					f"outside the amendment flow (FR-3.8)."
				)
PYEOF

cat > financials/doctype/change_event/change_event.py <<'PYEOF'
import frappe
from frappe.model.document import Document

PROTECTED_FIELDS = ["commitment", "category", "amount_delta"]


class ChangeEvent(Document):
	def validate(self):
		self._enforce_immutability()

	def _enforce_immutability(self):
		if self.is_new() or not self.is_immutable:
			return
		if self.flags.get("via_amendment"):
			return
		doc_before = self.get_doc_before_save()
		if not doc_before:
			return
		for f in PROTECTED_FIELDS:
			if self.get(f) != doc_before.get(f):
				frappe.throw(
					f"Cannot modify '{f}' on an approved/rejected, immutable "
					f"Change Event outside the amendment flow (FR-3.8)."
				)
PYEOF

cat > financials/doctype/pay_application/pay_application.py <<'PYEOF'
import frappe
from frappe.model.document import Document

IMMUTABLE_STATUSES = ("Approved", "Paid")
PROTECTED_FIELDS = ["commitment", "period_end", "retainage_pct"]


class PayApplication(Document):
	def validate(self):
		self._enforce_immutability()

	def _enforce_immutability(self):
		"""FR-3.8. Pay Application has no dedicated is_immutable field
		(ERD §3.1) - immutability is governed by status: once the PRIOR
		persisted state was Approved/Paid, protected fields freeze."""
		if self.is_new() or self.flags.get("via_amendment"):
			return
		doc_before = self.get_doc_before_save()
		if not doc_before or doc_before.status not in IMMUTABLE_STATUSES:
			return

		for f in PROTECTED_FIELDS:
			if self.get(f) != doc_before.get(f):
				frappe.throw(f"Cannot modify '{f}' on an Approved/Paid Pay Application (FR-3.8).")

		before_lines = [
			(r.cost_code, r.scheduled_value, r.work_completed_this_period, r.materials_stored)
			for r in (doc_before.lines or [])
		]
		after_lines = [
			(r.cost_code, r.scheduled_value, r.work_completed_this_period, r.materials_stored)
			for r in (self.lines or [])
		]
		if before_lines != after_lines:
			frappe.throw("Cannot modify line items on an Approved/Paid Pay Application (FR-3.8).")
PYEOF

cat > financials/doctype/pay_application_line/pay_application_line.py <<'PYEOF'
from frappe.model.document import Document


class PayApplicationLine(Document):
	pass
PYEOF

cat > financials/doctype/evm_snapshot/evm_snapshot.py <<'PYEOF'
from frappe.model.document import Document


class EVMSnapshot(Document):
	pass
PYEOF

# ---------------------------------------------------------------------------
# erpnext_adapter.py: re-issued with the retainage Payment Term bootstrap
# and a generic Cost-Code billing Item (Purchase Invoice Item requires a
# real Item link - a Cost Code is not one) fixed in.
cat > shared/erpnext_adapter.py <<'PYEOF'
"""
Adapter over native ERPNext v16 doctypes - the ONLY path BuildPolaris uses
to touch financial data (REQ "Financial system of record" clause; no
parallel ledger, ever - ERD §3.1 design note).

financials/services/*.py calls these functions; it never constructs a
Purchase Order / Purchase Invoice / Payment Entry doc directly, so every
financial-doctype creation path is auditable from one file.
"""
import frappe
from frappe.utils import flt, nowdate


def get_or_create_supplier(supplier_name: str, supplier_group: str | None = None) -> str:
	"""FR-3.2: Commitments reference a native Supplier - never a free-text
	vendor name. Reuses an existing Supplier by name."""
	existing = frappe.db.exists("Supplier", supplier_name)
	if existing:
		return existing

	doc = frappe.new_doc("Supplier")
	doc.supplier_name = supplier_name
	doc.supplier_group = supplier_group or _default_supplier_group()
	doc.supplier_type = "Company"
	doc.insert(ignore_permissions=True)
	return doc.name


def _default_supplier_group() -> str:
	group = frappe.db.get_single_value("Buying Settings", "supplier_group")
	return group or "All Supplier Groups"


def get_or_create_cost_center(company: str, cost_center_name: str | None = None) -> str:
	"""FR-3.1: optional Cost Code -> Cost Center cross-check link."""
	if not cost_center_name:
		return frappe.db.get_value("Company", company, "cost_center")

	existing = frappe.db.exists("Cost Center", {"cost_center_name": cost_center_name, "company": company})
	if existing:
		return existing

	doc = frappe.new_doc("Cost Center")
	doc.cost_center_name = cost_center_name
	doc.company = company
	doc.parent_cost_center = frappe.db.get_value("Company", company, "cost_center")
	doc.insert(ignore_permissions=True)
	return doc.name


def get_or_create_billing_item(cost_code: str) -> str:
	"""Non-stock service Item representing billing against a Cost Code, so
	Pay Application lines can post through ERPNext's standard Purchase
	Invoice Item table (which requires a real Item link) without pretending
	a Cost Code is physical inventory. One Item per Cost Code, reused."""
	item_code = f"BP-COSTCODE-{cost_code}"
	if frappe.db.exists("Item", item_code):
		return item_code

	cost_code_doc = frappe.db.get_value("Cost Code", cost_code, ["code", "description"], as_dict=True)
	doc = frappe.new_doc("Item")
	doc.item_code = item_code
	doc.item_name = f"Cost Code {cost_code_doc.code if cost_code_doc else cost_code} Billing"
	doc.item_group = _default_service_item_group()
	doc.is_stock_item = 0
	doc.include_item_in_manufacturing = 0
	doc.insert(ignore_permissions=True)
	return item_code


def _default_service_item_group() -> str:
	if frappe.db.exists("Item Group", "Services"):
		return "Services"
	return frappe.db.get_single_value("Selling Settings", "item_group") or "All Item Groups"


def create_purchase_order(company: str, supplier: str, project: str, items: list, cost_center: str | None = None) -> str:
	"""FR-3.3: Commitment approval (PO-type only) creates and links a native
	Purchase Order. `items` is [{item_code|description, qty, rate}, ...]."""
	doc = frappe.new_doc("Purchase Order")
	doc.company = company
	doc.supplier = supplier
	doc.project = project
	doc.transaction_date = nowdate()
	for item in items:
		row = doc.append("items", {})
		row.item_code = item.get("item_code")
		row.item_name = item.get("description") or item.get("item_code")
		row.description = item.get("description")
		row.qty = flt(item.get("qty", 1))
		row.rate = flt(item.get("rate", 0))
		if cost_center:
			row.cost_center = cost_center
	doc.insert(ignore_permissions=True)
	doc.submit()
	return doc.name


def create_purchase_invoice_with_retainage(company: str, supplier: str, project: str,
                                            items: list, retainage_pct: float,
                                            purchase_order: str | None = None) -> str:
	"""FR-3.5: Pay Application approval generates a native Purchase Invoice
	with retainage modeled as a held-back Payment Term - so it appears in
	ERPNext's own AP aging, never a side field the platform tracks alone."""
	_ensure_payment_term("Immediate", "Immediate")
	_ensure_payment_term("Retainage Held", "Retainage withheld until closeout release (FR-3.5).")

	doc = frappe.new_doc("Purchase Invoice")
	doc.company = company
	doc.supplier = supplier
	doc.project = project
	for item in items:
		row = doc.append("items", {})
		row.item_code = item.get("item_code")
		row.item_name = item.get("description") or item.get("item_code")
		row.description = item.get("description")
		row.qty = flt(item.get("qty", 1))
		row.rate = flt(item.get("rate", 0))
		if purchase_order:
			row.purchase_order = purchase_order

	if retainage_pct:
		_apply_retainage_payment_terms(doc, retainage_pct)

	doc.insert(ignore_permissions=True)
	doc.submit()
	return doc.name


def _ensure_payment_term(name: str, description: str) -> str:
	if not frappe.db.exists("Payment Term", name):
		frappe.get_doc({
			"doctype": "Payment Term",
			"payment_term_name": name,
			"description": description,
			"invoice_portion": 100,
		}).insert(ignore_permissions=True)
	return name


def _apply_retainage_payment_terms(purchase_invoice_doc, retainage_pct: float):
	"""Splits payment into an immediate-due portion and a retainage-held
	portion using ERPNext's native Payment Terms."""
	release_pct = 100 - flt(retainage_pct)
	purchase_invoice_doc.payment_terms_template = None
	purchase_invoice_doc.set("payment_schedule", [])
	purchase_invoice_doc.append("payment_schedule", {
		"payment_term": "Immediate",
		"invoice_portion": release_pct,
		"due_date": nowdate(),
	})
	purchase_invoice_doc.append("payment_schedule", {
		"payment_term": "Retainage Held",
		"invoice_portion": flt(retainage_pct),
		"due_date": nowdate(),
	})


def create_payment_entry(purchase_invoice: str, paid_amount: float | None = None) -> str:
	"""FR-3.5: payment against a Pay Application's Purchase Invoice creates
	a native Payment Entry linked back to it."""
	from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

	pe = get_payment_entry("Purchase Invoice", purchase_invoice)
	if paid_amount is not None:
		pe.paid_amount = flt(paid_amount)
		pe.received_amount = flt(paid_amount)
	pe.insert(ignore_permissions=True)
	pe.submit()
	return pe.name


def get_ap_aging_for_supplier(supplier: str, company: str) -> dict:
	"""Read AP figures live from ERPNext - never a duplicated total_paid /
	amount_outstanding field anywhere in BuildPolaris (ERD §3.1)."""
	rows = frappe.get_all(
		"Purchase Invoice",
		filters={"supplier": supplier, "company": company, "docstatus": 1},
		fields=["name", "grand_total", "outstanding_amount", "status"],
	)
	total_billed = sum(flt(r.grand_total) for r in rows)
	total_outstanding = sum(flt(r.outstanding_amount) for r in rows)
	return {
		"total_billed": total_billed,
		"total_outstanding": total_outstanding,
		"total_paid": total_billed - total_outstanding,
		"invoices": rows,
	}
PYEOF

cat > financials/services/cost_code_service.py <<'PYEOF'
"""FR-3.1: Cost Code structure per Project. FR-3.6: budget/committed/actual
rollup (field-level masking for Subcontractor is enforced natively via the
DocType JSON's permlevel, not computed here)."""
import frappe

from buildpolaris_bff.shared.exceptions import ValidationError
from buildpolaris_bff.shared.permissions import assert_project_permission, assert_role


def create_cost_code(project, code, description, budget_amount, cost_center=None, created_by=None):
	created_by = created_by or frappe.session.user
	assert_project_permission(project, ptype="write", user=created_by)
	assert_role("BuildPolaris Project Manager", "BuildPolaris Admin", user=created_by)

	if frappe.db.exists("Cost Code", {"project": project, "code": code}):
		raise ValidationError(f"Cost Code '{code}' already exists on this Project.")

	doc = frappe.get_doc({
		"doctype": "Cost Code",
		"naming_series": "CC-.YYYY.-.#####",
		"project": project,
		"code": code,
		"description": description,
		"budget_amount": budget_amount,
		"cost_center": cost_center,
	})
	doc.insert()
	return doc.as_dict()


def list_cost_codes(project, user=None):
	assert_project_permission(project, ptype="read", user=user)
	return frappe.get_all(
		"Cost Code", filters={"project": project},
		fields=["name", "code", "description", "budget_amount", "cost_center"],
	)


def get_budget_rollup(project, user=None):
	"""FR-3.6: budget vs committed vs actual per Cost Code, read live -
	never a cached rollup field."""
	assert_project_permission(project, ptype="read", user=user)

	cost_codes = list_cost_codes(project, user=user)
	rollup = []
	for cc in cost_codes:
		committed = frappe.db.sql(
			"select coalesce(sum(revised_amount), 0) from `tabCommitment` "
			"where cost_code = %s and status = 'Approved'",
			cc.name,
		)[0][0]
		actual = frappe.db.sql(
			"""select coalesce(sum(pal.work_completed_this_period + pal.materials_stored), 0)
			   from `tabPay Application Line` pal
			   inner join `tabPay Application` pa on pa.name = pal.parent
			   where pal.cost_code = %s and pa.status in ('Approved', 'Paid')""",
			cc.name,
		)[0][0]
		rollup.append({
			"cost_code": cc.name,
			"code": cc.code,
			"budget_amount": cc.budget_amount,
			"committed": committed,
			"actual": actual,
			"variance": (cc.budget_amount or 0) - (committed or 0),
		})
	return rollup
PYEOF

cat > financials/services/commitment_service.py <<'PYEOF'
"""FR-3.2/FR-3.3: Commitments against a Cost Code + native Supplier,
approved by Accounting."""
import frappe
from frappe.utils import now_datetime

from buildpolaris_bff.shared.erpnext_adapter import create_purchase_order, get_or_create_cost_center
from buildpolaris_bff.shared.exceptions import ValidationError
from buildpolaris_bff.shared.permissions import assert_project_permission, assert_role
from buildpolaris_bff.shared.security_log import log_security_event


def create_commitment(project, cost_code, supplier, type, original_amount, created_by=None):
	created_by = created_by or frappe.session.user
	assert_project_permission(project, ptype="write", user=created_by)
	assert_role("BuildPolaris Project Manager", "BuildPolaris Admin", user=created_by)

	if type not in ("Subcontract", "PurchaseOrder"):
		raise ValidationError("type must be 'Subcontract' or 'PurchaseOrder'.")

	cc_project = frappe.db.get_value("Cost Code", cost_code, "project")
	if cc_project != project:
		raise ValidationError("Cost Code does not belong to this Project.")

	doc = frappe.get_doc({
		"doctype": "Commitment",
		"naming_series": "COMM-.YYYY.-.#####",
		"project": project,
		"cost_code": cost_code,
		"supplier": supplier,
		"type": type,
		"status": "Draft",
		"original_amount": original_amount,
		"revised_amount": original_amount,
	})
	doc.insert()
	return doc.as_dict()


def submit_for_approval(commitment: str, submitted_by: str | None = None):
	submitted_by = submitted_by or frappe.session.user
	doc = frappe.get_doc("Commitment", commitment)
	assert_project_permission(doc.project, ptype="write", user=submitted_by)
	if doc.status != "Draft":
		raise ValidationError(f"Commitment must be Draft to submit for approval (current: {doc.status}).")
	doc.status = "PendingApproval"
	doc.save()
	return doc.as_dict()


def approve_commitment(commitment: str, items: list | None = None, approved_by: str | None = None):
	"""FR-3.3: approval rolls the amount into the Cost Code's committed
	total (read live via get_committed_total below - no duplicated rollup
	field) and, for PO-type Commitments, creates and links a native
	Purchase Order."""
	approved_by = approved_by or frappe.session.user
	assert_role("BuildPolaris Accounting", "BuildPolaris Admin", user=approved_by)

	doc = frappe.get_doc("Commitment", commitment)
	assert_project_permission(doc.project, ptype="write", user=approved_by)

	if doc.status != "PendingApproval":
		raise ValidationError(f"Commitment must be PendingApproval to approve (current: {doc.status}).")

	if doc.type == "PurchaseOrder":
		if not items:
			raise ValidationError("PO-type Commitments require line items to create the Purchase Order.")
		company = frappe.db.get_value("Project", doc.project, "company")
		cost_center = get_or_create_cost_center(company)
		po_name = create_purchase_order(company, doc.supplier, doc.project, items, cost_center=cost_center)
		doc.purchase_order = po_name

	doc.status = "Approved"
	doc.approved_by = approved_by
	doc.approved_at = now_datetime()
	doc.is_immutable = 1
	doc.save()

	log_security_event("COMMITMENT_APPROVED", {"commitment": commitment, "approved_by": approved_by})
	frappe.db.commit()
	return doc.as_dict()


def get_committed_total(cost_code: str) -> float:
	"""Read live - never a cached rollup field (ERD §3.1 design note)."""
	result = frappe.db.sql(
		"select coalesce(sum(revised_amount), 0) from `tabCommitment` "
		"where cost_code = %s and status = 'Approved'",
		cost_code,
	)
	return float(result[0][0]) if result else 0.0
PYEOF

cat > financials/services/change_event_service.py <<'PYEOF'
"""FR-3.4: Change Events, optionally linked to an originating RFI. Approval
updates the linked Commitment's revised amount - the defined amendment
path for Commitment (FR-3.8)."""
import frappe

from buildpolaris_bff.shared.exceptions import ValidationError
from buildpolaris_bff.shared.permissions import assert_project_permission, assert_role
from buildpolaris_bff.shared.security_log import log_security_event

VALID_CATEGORIES = {"ScopeGap", "DesignError", "FieldCondition", "OwnerRequest", "Other"}


def create_change_event(project, commitment, category, outcome_reason, amount_delta,
                         originating_rfi=None, created_by=None):
	created_by = created_by or frappe.session.user
	assert_project_permission(project, ptype="write", user=created_by)
	assert_role("BuildPolaris Project Manager", "BuildPolaris Admin", user=created_by)

	if category not in VALID_CATEGORIES:
		raise ValidationError(f"category must be one of {VALID_CATEGORIES}.")

	commit_project = frappe.db.get_value("Commitment", commitment, "project")
	if commit_project != project:
		raise ValidationError("Commitment does not belong to this Project.")

	doc = frappe.get_doc({
		"doctype": "Change Event",
		"naming_series": "CE-.YYYY.-.#####",
		"project": project,
		"commitment": commitment,
		"originating_rfi": originating_rfi,
		"category": category,
		"outcome_reason": outcome_reason,
		"amount_delta": amount_delta,
		"status": "Open",
	})
	doc.insert()
	return doc.as_dict()


def approve_change_event(change_event: str, approved_by: str | None = None):
	"""FR-3.4: Role: Owner or PM (unlike Commitment approval, which is
	Accounting-only - this is a scope decision, not a payment decision)."""
	approved_by = approved_by or frappe.session.user
	assert_role("BuildPolaris Owner", "BuildPolaris Project Manager", "BuildPolaris Admin", user=approved_by)

	doc = frappe.get_doc("Change Event", change_event)
	assert_project_permission(doc.project, ptype="write", user=approved_by)

	if doc.status != "Open":
		raise ValidationError(f"Change Event must be Open to approve (current: {doc.status}).")

	commitment_doc = frappe.get_doc("Commitment", doc.commitment)
	commitment_doc.flags.via_amendment = True  # a Change Event IS the defined amendment path (FR-3.8)
	commitment_doc.revised_amount = (commitment_doc.revised_amount or 0) + doc.amount_delta
	commitment_doc.save()

	doc.status = "Approved"
	doc.approved_by = approved_by
	doc.is_immutable = 1
	doc.save()

	log_security_event("CHANGE_EVENT_APPROVED", {
		"change_event": change_event, "commitment": doc.commitment, "amount_delta": doc.amount_delta,
	})
	frappe.db.commit()
	return doc.as_dict()


def reject_change_event(change_event: str, rejected_by: str | None = None):
	rejected_by = rejected_by or frappe.session.user
	assert_role("BuildPolaris Owner", "BuildPolaris Project Manager", "BuildPolaris Admin", user=rejected_by)

	doc = frappe.get_doc("Change Event", change_event)
	assert_project_permission(doc.project, ptype="write", user=rejected_by)
	if doc.status != "Open":
		raise ValidationError(f"Change Event must be Open to reject (current: {doc.status}).")
	doc.status = "Rejected"
	doc.is_immutable = 1
	doc.save()
	return doc.as_dict()
PYEOF

cat > financials/services/pay_application_service.py <<'PYEOF'
"""FR-3.5: AIA G702/G703-style Pay Applications billed against a
Commitment. Approval generates a native Purchase Invoice with retainage as
a held-back Payment Term; payment generates a Payment Entry."""
import frappe
from frappe.utils import flt

from buildpolaris_bff.shared.erpnext_adapter import (
	create_payment_entry,
	create_purchase_invoice_with_retainage,
	get_or_create_billing_item,
)
from buildpolaris_bff.shared.exceptions import ValidationError
from buildpolaris_bff.shared.permissions import assert_project_permission, assert_role
from buildpolaris_bff.shared.security_log import log_security_event


def create_pay_application(commitment, period_end, lines, retainage_pct=10, created_by=None):
	"""lines: [{cost_code, scheduled_value, work_completed_this_period, materials_stored}]"""
	created_by = created_by or frappe.session.user
	commitment_doc = frappe.get_doc("Commitment", commitment)
	assert_project_permission(commitment_doc.project, ptype="write", user=created_by)
	assert_role("BuildPolaris Subcontractor", "BuildPolaris Project Manager", "BuildPolaris Admin", user=created_by)

	if commitment_doc.status != "Approved":
		raise ValidationError("Pay Applications can only be billed against an Approved Commitment.")

	doc = frappe.get_doc({
		"doctype": "Pay Application",
		"naming_series": "PA-.YYYY.-.#####",
		"commitment": commitment,
		"project": commitment_doc.project,
		"period_end": period_end,
		"retainage_pct": retainage_pct,
		"status": "Draft",
	})
	for line in lines:
		scheduled = flt(line.get("scheduled_value"))
		completed = flt(line.get("work_completed_this_period"))
		stored = flt(line.get("materials_stored"))
		pct = round(((completed + stored) / scheduled) * 100, 2) if scheduled else 0
		doc.append("lines", {
			"cost_code": line.get("cost_code"),
			"scheduled_value": scheduled,
			"work_completed_this_period": completed,
			"materials_stored": stored,
			"pct_complete": pct,
		})
	doc.insert()
	return doc.as_dict()


def submit_for_approval(pay_application: str, submitted_by: str | None = None):
	submitted_by = submitted_by or frappe.session.user
	doc = frappe.get_doc("Pay Application", pay_application)
	assert_project_permission(doc.project, ptype="write", user=submitted_by)
	if doc.status != "Draft":
		raise ValidationError(f"Pay Application must be Draft to submit (current: {doc.status}).")
	doc.status = "PendingApproval"
	doc.save()
	return doc.as_dict()


def approve_pay_application(pay_application: str, approved_by: str | None = None):
	"""FR-3.5: approval generates a native Purchase Invoice with retainage
	as a held-back Payment Term."""
	approved_by = approved_by or frappe.session.user
	assert_role("BuildPolaris Accounting", "BuildPolaris Admin", user=approved_by)

	doc = frappe.get_doc("Pay Application", pay_application)
	assert_project_permission(doc.project, ptype="write", user=approved_by)

	if doc.status != "PendingApproval":
		raise ValidationError(f"Pay Application must be PendingApproval to approve (current: {doc.status}).")

	commitment_doc = frappe.get_doc("Commitment", doc.commitment)
	company = frappe.db.get_value("Project", doc.project, "company")

	items = []
	for line in doc.lines:
		item_code = get_or_create_billing_item(line.cost_code)
		items.append({
			"item_code": item_code,
			"description": f"Pay App {doc.name} - {line.cost_code}",
			"qty": 1,
			"rate": flt(line.work_completed_this_period) + flt(line.materials_stored),
		})

	pi_name = create_purchase_invoice_with_retainage(
		company=company, supplier=commitment_doc.supplier, project=doc.project,
		items=items, retainage_pct=doc.retainage_pct,
		purchase_order=commitment_doc.purchase_order,
	)

	doc.purchase_invoice = pi_name
	doc.status = "Approved"
	doc.save()

	log_security_event("PAY_APPLICATION_APPROVED", {"pay_application": pay_application, "purchase_invoice": pi_name})
	frappe.db.commit()
	return doc.as_dict()


def record_payment(pay_application: str, paid_amount: float | None = None, recorded_by: str | None = None):
	recorded_by = recorded_by or frappe.session.user
	assert_role("BuildPolaris Accounting", "BuildPolaris Admin", user=recorded_by)

	doc = frappe.get_doc("Pay Application", pay_application)
	assert_project_permission(doc.project, ptype="write", user=recorded_by)

	if doc.status != "Approved":
		raise ValidationError(f"Pay Application must be Approved before recording payment (current: {doc.status}).")
	if not doc.purchase_invoice:
		raise ValidationError("Pay Application has no linked Purchase Invoice.")

	pe_name = create_payment_entry(doc.purchase_invoice, paid_amount=paid_amount)
	doc.payment_entry = pe_name
	doc.status = "Paid"
	doc.save()

	log_security_event("PAY_APPLICATION_PAID", {"pay_application": pay_application, "payment_entry": pe_name})
	frappe.db.commit()
	return doc.as_dict()
PYEOF

cat > financials/services/amendment_service.py <<'PYEOF'
"""
FR-3.8: the defined amendment flow for approved, immutable financial
records. There is no generic "unlock and edit" path - each doctype's
correction flow is intentionally narrow and fully audited:

  - Commitment  -> corrected via an approved Change Event (amount only).
    Any other correction (wrong Supplier, wrong Cost Code) requires
    Accounting to reject the approval upstream before it becomes
    immutable; once immutable, no field but revised_amount ever changes,
    and only through change_event_service.approve_change_event.

  - Change Event -> once Approved/Rejected, itself immutable; a mistaken
    approval is corrected by logging an offsetting Change Event (negative
    amount_delta) rather than editing history - this preserves the full,
    truthful chain (NFR-AUD.1) instead of rewriting what happened.

  - Pay Application -> once Approved/Paid, corrected by creating a new
    Pay Application against the same Commitment for a later period that
    nets out the error, never by re-opening the original.
"""
import frappe

from buildpolaris_bff.shared.exceptions import ValidationError
from buildpolaris_bff.shared.permissions import assert_project_permission, assert_role
from buildpolaris_bff.identity.services import change_history_service


def create_offsetting_change_event(original_change_event: str, reason: str, created_by: str | None = None):
	"""The concrete corrective action for an erroneously approved Change
	Event: an equal-and-opposite Change Event, fully traceable via
	get_amendment_history()."""
	created_by = created_by or frappe.session.user
	original = frappe.get_doc("Change Event", original_change_event)
	assert_project_permission(original.project, ptype="write", user=created_by)
	assert_role("BuildPolaris Owner", "BuildPolaris Project Manager", "BuildPolaris Admin", user=created_by)

	if original.status != "Approved":
		raise ValidationError("Only an Approved Change Event can be offset.")

	from buildpolaris_bff.financials.services.change_event_service import create_change_event

	return create_change_event(
		project=original.project,
		commitment=original.commitment,
		category=original.category,
		outcome_reason=f"Amendment of {original.name}: {reason}",
		amount_delta=-original.amount_delta,
		created_by=created_by,
	)


def get_amendment_history(doctype: str, name: str):
	"""Every amendment is itself a fully versioned write (FR-1.6/NFR-AUD.1) -
	surface it through the same native Version history, not a parallel log."""
	return change_history_service.get_change_history(doctype, name)
PYEOF

cat > financials/services/evm_service.py <<'PYEOF'
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
PYEOF

cat > financials/services/financial_close_service.py <<'PYEOF'
"""
FR-3.6: budget vs committed vs actual, rolled up to the Project level
(Cost-Code-level detail lives in cost_code_service.get_budget_rollup).
Also the read used by the Closeout module's 'final payment gate' check
(FR-7.5) to confirm no financial item is left in an unresolved state.
"""
import frappe

from buildpolaris_bff.shared.permissions import assert_project_permission
from buildpolaris_bff.financials.services.cost_code_service import get_budget_rollup


def get_project_financial_summary(project: str, user: str | None = None) -> dict:
	assert_project_permission(project, ptype="read", user=user)
	rollup = get_budget_rollup(project, user=user)
	return {
		"project": project,
		"total_budget": sum(r["budget_amount"] or 0 for r in rollup),
		"total_committed": sum(r["committed"] or 0 for r in rollup),
		"total_actual": sum(r["actual"] or 0 for r in rollup),
		"cost_codes": rollup,
	}


def has_unresolved_financial_items(project: str) -> bool:
	"""Used by closeout/services/closeout_gate_service.py (FR-7.5) - the
	final payment gate is blocked while anything is still Draft/Pending."""
	pending_commitments = frappe.db.count("Commitment", {
		"project": project, "status": ["in", ["Draft", "PendingApproval"]],
	})
	pending_pay_apps = frappe.db.count("Pay Application", {
		"project": project, "status": ["in", ["Draft", "PendingApproval"]],
	})
	pending_changes = frappe.db.count("Change Event", {
		"project": project, "status": "Open",
	})
	return bool(pending_commitments or pending_pay_apps or pending_changes)
PYEOF

cat > financials/api.py <<'PYEOF'
"""Financials - HTTP adapters only (NFR-MAINT.1)."""
import frappe

from buildpolaris_bff.shared.api_envelope import success
from buildpolaris_bff.financials.services import (
	amendment_service,
	change_event_service,
	commitment_service,
	cost_code_service,
	evm_service,
	financial_close_service,
	pay_application_service,
)


@frappe.whitelist()
def create_cost_code(project, code, description, budget_amount, cost_center=None):
	return success(cost_code_service.create_cost_code(project, code, description, float(budget_amount), cost_center))


@frappe.whitelist()
def list_cost_codes(project):
	return success(cost_code_service.list_cost_codes(project))


@frappe.whitelist()
def get_budget_rollup(project):
	return success(cost_code_service.get_budget_rollup(project))


@frappe.whitelist()
def create_commitment(project, cost_code, supplier, type, original_amount):
	return success(commitment_service.create_commitment(project, cost_code, supplier, type, float(original_amount)))


@frappe.whitelist()
def submit_commitment_for_approval(commitment):
	return success(commitment_service.submit_for_approval(commitment))


@frappe.whitelist()
def approve_commitment(commitment, items=None):
	if isinstance(items, str):
		items = frappe.parse_json(items)
	return success(commitment_service.approve_commitment(commitment, items))


@frappe.whitelist()
def create_change_event(project, commitment, category, outcome_reason, amount_delta, originating_rfi=None):
	return success(change_event_service.create_change_event(
		project, commitment, category, outcome_reason, float(amount_delta), originating_rfi
	))


@frappe.whitelist()
def approve_change_event(change_event):
	return success(change_event_service.approve_change_event(change_event))


@frappe.whitelist()
def reject_change_event(change_event):
	return success(change_event_service.reject_change_event(change_event))


@frappe.whitelist()
def create_pay_application(commitment, period_end, lines, retainage_pct=10):
	if isinstance(lines, str):
		lines = frappe.parse_json(lines)
	return success(pay_application_service.create_pay_application(commitment, period_end, lines, float(retainage_pct)))


@frappe.whitelist()
def submit_pay_application_for_approval(pay_application):
	return success(pay_application_service.submit_for_approval(pay_application))


@frappe.whitelist()
def approve_pay_application(pay_application):
	return success(pay_application_service.approve_pay_application(pay_application))


@frappe.whitelist()
def record_payment(pay_application, paid_amount=None):
	paid_amount = float(paid_amount) if paid_amount is not None else None
	return success(pay_application_service.record_payment(pay_application, paid_amount))


@frappe.whitelist()
def get_evm(project, as_of_date=None):
	return success(evm_service.compute_evm(project, as_of_date))


@frappe.whitelist()
def get_project_financial_summary(project):
	return success(financial_close_service.get_project_financial_summary(project))


@frappe.whitelist()
def create_offsetting_change_event(original_change_event, reason):
	return success(amendment_service.create_offsetting_change_event(original_change_event, reason))


@frappe.whitelist()
def get_amendment_history(doctype, name):
	return success(amendment_service.get_amendment_history(doctype, name))
PYEOF

echo "=== [6/6] config/jobs.py: implement schedule_health_check; hooks.py: wire EVM nightly snapshot ==="

cat > config/jobs.py <<'PYEOF'
"""
BuildPolaris scheduled jobs (wired in hooks.scheduler_events).
Job failures MUST surface to an operator-visible channel (NFR-OBS.2).
"""
import frappe
from frappe.utils import today


def escalate_overdue_communications():
	"""
	UC-4.5 / FR-4.5: escalate overdue RFIs and Action Items via the existing
	notification engine. Runs daily.

	NOTE: pending the Communications phase - 'Escalation Log' as referenced
	in the pre-refactor draft was removed in the ARCH v2.1 refactor (FR-4.5
	uses native ToDo/notification engine, not a bespoke doctype). This
	function body is replaced when communications/services/escalation_service.py
	lands.
	"""
	pass


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
PYEOF

cat > hooks.py <<'PYEOF'
from frappe import _

app_name = "buildpolaris_bff"
app_title = "BuildPolaris BFF"
app_publisher = "BuildPolaris"
app_description = "Backend-for-Frontend for BuildPolaris Construction Project Management"
app_email = "dev@buildpolaris.com"
app_license = "MIT"

# ------------------------------------------------------------------
# Request lifecycle - attach a trace id to every request (NFR-OBS.1).
# ------------------------------------------------------------------
before_request = [
	"buildpolaris_bff.shared.security_log.attach_trace_id",
]

# ------------------------------------------------------------------
# Scheduler Events (ARCH §1.1: no message broker anywhere - every
# propagation is either synchronous REST or a frappe.enqueue background
# job, and every recurring job is registered here, never a cron outside
# Frappe's own scheduler).
#
# Phased delivery note: a string reference to a not-yet-implemented
# function is safe at import time (Frappe resolves it lazily when the job
# actually fires); this file is re-issued complete at the end of each
# phase. Do not let a scheduler tick fire against a job whose module
# hasn't landed yet.
# ------------------------------------------------------------------
scheduler_events = {
	"daily": [
		"buildpolaris_bff.config.jobs.escalate_overdue_communications",   # FR-4.5 (Communications phase - body pending)
		"buildpolaris_bff.config.jobs.closeout_lookahead_digest",          # M7 (Closeout phase - body pending)
		"buildpolaris_bff.financials.services.evm_service.capture_nightly_snapshot",  # FR-3.7 (implemented)
	],
	"hourly": [
		"buildpolaris_bff.config.jobs.schedule_health_check",                           # FR-2.3 (implemented)
		"buildpolaris_bff.ai_copilot.services.retry_failed_ingestion.run",              # NFR-AIGOV.3 (AI Copilot phase - pending)
	],
}

# ------------------------------------------------------------------
# Document Events
#   No wildcard "*" hook here (ARCH §2.4/§4.3 correction: no CDC/event-bus
#   layer exists in this design). Each module wires ONLY the specific
#   DocType hooks its own FRs require (e.g. File.after_insert for FR-8.10
#   ingestion, entity-mirror hooks for FR-8.2) directly - added in the
#   AI Copilot phase, not here as a platform-wide catch-all.
# ------------------------------------------------------------------
doc_events = {}

# ------------------------------------------------------------------
# Fixtures / Permissions / Website
# ------------------------------------------------------------------
fixtures = []
has_permission = {}
website_route_rules = []
PYEOF

echo ""
echo "=== PHASE 2b COMPLETE: scheduling/ + financials/ ==="
echo "Files written:"
find scheduling financials -name "*.py" -o -name "*.json" | sort
echo ""
echo "config/jobs.py, hooks.py updated (schedule_health_check implemented,"
echo "EVM nightly snapshot wired). shared/erpnext_adapter.py re-issued with"
echo "the retainage Payment Term bootstrap + Cost-Code billing Item fix."
echo ""
echo "Do NOT run 'bench migrate' yet - Communications/Document Control/Field/"
echo "Closeout/AI Copilot DocType JSONs still need their Phase 2 pass."
echo "Next: say 'go' for Communications + Document Control."