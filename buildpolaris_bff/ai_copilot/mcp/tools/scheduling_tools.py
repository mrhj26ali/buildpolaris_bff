"""Read-only MCP tools over scheduling/ (FR-8.4). Each wraps exactly one
existing services/ function - no parallel read path is ever built for the
copilot (NFR-EXT.3)."""
from buildpolaris_bff.scheduling.services import schedule_task_service, lookahead_service


def get_schedule_state(arguments: dict, asserted_user: str, asserted_project: str | None) -> dict:
	"""List every Task on a Project with its CPM outputs (critical path,
	float). arguments: {"project": str}."""
	project = arguments.get("project") or asserted_project
	tasks = schedule_task_service.list_tasks(project, user=asserted_user)
	return {"project": project, "tasks": tasks}


def get_lookahead(arguments: dict, asserted_user: str, asserted_project: str | None) -> dict:
	"""arguments: {"project": str, "weeks": int (default 3), "as_of_date": str|None}."""
	project = arguments.get("project") or asserted_project
	weeks = int(arguments.get("weeks", 3))
	as_of_date = arguments.get("as_of_date")
	return lookahead_service.get_lookahead(project, weeks, as_of_date, user=asserted_user)
