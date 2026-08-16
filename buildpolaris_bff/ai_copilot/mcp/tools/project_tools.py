"""Read-only MCP tools over projects/ (FR-8.4)."""
from buildpolaris_bff.projects.services import project_summary_service


def get_project_summary(arguments: dict, asserted_user: str, asserted_project: str | None) -> dict:
	"""Cross-module dashboard summary for a Project. arguments: {"project": str}."""
	project = arguments.get("project") or asserted_project
	return project_summary_service.get_project_summary(project, user=asserted_user)
