from frappe import _

app_name = "buildpolaris_bff"
app_title = "BuildPolaris BFF"
app_publisher = "BuildPolaris"
app_description = "Backend-for-Frontend for BuildPolaris Construction Project Management"
app_email = "dev@buildpolaris.com"
app_license = "MIT"

# ------------------------------------------------------------------
# Scheduler Events — Phase 0 wires the infrastructure;
# Phases 3/6 fill in the job bodies.
# ------------------------------------------------------------------
scheduler_events = {
    "daily": [
        "buildpolaris_bff.config.jobs.escalate_overdue_communications",
        "buildpolaris_bff.config.jobs.closeout_lookahead_digest",
    ],
    "hourly": [
        "buildpolaris_bff.config.jobs.schedule_health_check",
    ],
}

# ------------------------------------------------------------------
# Document Events
# ------------------------------------------------------------------
doc_events = {}

# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------
fixtures = []

# ------------------------------------------------------------------
# Permissions
# ------------------------------------------------------------------
has_permission = {}

# ------------------------------------------------------------------
# Website
# ------------------------------------------------------------------
website_route_rules = []
