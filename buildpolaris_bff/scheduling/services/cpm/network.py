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
