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
# Install / migrate lifecycle (install.py: platform Roles, BuildPolaris
# custom fields on User, the low-privilege AI Service transport account).
# ------------------------------------------------------------------
after_install = "buildpolaris_bff.install.after_install"
after_migrate = "buildpolaris_bff.install.after_migrate"

# ------------------------------------------------------------------
# Scheduler Events (ARCH §1.1: no message broker anywhere - every
# propagation is either synchronous REST or a frappe.enqueue background
# job, and every recurring job is registered here, never a cron outside
# Frappe's own scheduler).
# ------------------------------------------------------------------
scheduler_events = {
	"daily": [
		"buildpolaris_bff.config.jobs.escalate_overdue_communications",   # FR-4.5 (implemented)
		"buildpolaris_bff.config.jobs.closeout_lookahead_digest",          # M7 (implemented)
		"buildpolaris_bff.financials.services.evm_service.capture_nightly_snapshot",  # FR-3.7 (implemented)
	],
	"hourly": [
		"buildpolaris_bff.config.jobs.schedule_health_check",                           # FR-2.3 (implemented)
		"buildpolaris_bff.ai_copilot.services.retry_failed_ingestion.run",              # NFR-AIGOV.3 (implemented)
	],
}

# ------------------------------------------------------------------
# Document Events
#   No wildcard "*" hook here (ARCH §2.4/§4.3 correction: no CDC/event-bus
#   layer exists in this design). Each module wires ONLY the specific
#   DocType hooks its own FRs require:
#     - File.after_insert: FR-8.10 ingestion trigger (allow-listed source
#       doctypes only - checked inside the handler, not here).
#     - Task/RFI/Commitment/Change Event/Punch List Item/Safety Incident:
#       FR-8.2 entity-mirror - keeps buildpolaris_ai's graph store current
#       without polling. Safety Incident mirrors metadata only
#       (NFR-PRIV.1/PRIV.2 - see entity_mirror_service.py's field map).
# ------------------------------------------------------------------
doc_events = {
	"File": {
		"after_insert": "buildpolaris_bff.ai_copilot.services.ingestion_trigger_service.on_file_after_insert",
	},
	"Task": {
		"after_insert": "buildpolaris_bff.ai_copilot.services.entity_mirror_service.mirror_hook",
		"on_update": "buildpolaris_bff.ai_copilot.services.entity_mirror_service.mirror_hook",
		"on_trash": "buildpolaris_bff.ai_copilot.services.entity_mirror_service.mirror_hook",
	},
	"RFI": {
		"after_insert": "buildpolaris_bff.ai_copilot.services.entity_mirror_service.mirror_hook",
		"on_update": "buildpolaris_bff.ai_copilot.services.entity_mirror_service.mirror_hook",
		"on_trash": "buildpolaris_bff.ai_copilot.services.entity_mirror_service.mirror_hook",
	},
	"Commitment": {
		"after_insert": "buildpolaris_bff.ai_copilot.services.entity_mirror_service.mirror_hook",
		"on_update": "buildpolaris_bff.ai_copilot.services.entity_mirror_service.mirror_hook",
		"on_trash": "buildpolaris_bff.ai_copilot.services.entity_mirror_service.mirror_hook",
	},
	"Change Event": {
		"after_insert": "buildpolaris_bff.ai_copilot.services.entity_mirror_service.mirror_hook",
		"on_update": "buildpolaris_bff.ai_copilot.services.entity_mirror_service.mirror_hook",
		"on_trash": "buildpolaris_bff.ai_copilot.services.entity_mirror_service.mirror_hook",
	},
	"Punch List Item": {
		"after_insert": "buildpolaris_bff.ai_copilot.services.entity_mirror_service.mirror_hook",
		"on_update": "buildpolaris_bff.ai_copilot.services.entity_mirror_service.mirror_hook",
		"on_trash": "buildpolaris_bff.ai_copilot.services.entity_mirror_service.mirror_hook",
	},
	"Safety Incident": {
		"after_insert": "buildpolaris_bff.ai_copilot.services.entity_mirror_service.mirror_hook",
		"on_update": "buildpolaris_bff.ai_copilot.services.entity_mirror_service.mirror_hook",
		"on_trash": "buildpolaris_bff.ai_copilot.services.entity_mirror_service.mirror_hook",
	},
}

# ------------------------------------------------------------------
# Fixtures / Permissions / Website
# ------------------------------------------------------------------
fixtures = []
has_permission = {}
website_route_rules = []
