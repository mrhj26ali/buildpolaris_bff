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
		"buildpolaris_bff.config.jobs.escalate_overdue_communications",   # FR-4.5 (implemented)
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
