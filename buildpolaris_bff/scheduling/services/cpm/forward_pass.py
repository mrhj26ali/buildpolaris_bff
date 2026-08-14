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
