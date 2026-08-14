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
