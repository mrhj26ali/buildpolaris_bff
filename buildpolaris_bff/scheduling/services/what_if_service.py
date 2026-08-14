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
