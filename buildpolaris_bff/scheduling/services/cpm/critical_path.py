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
