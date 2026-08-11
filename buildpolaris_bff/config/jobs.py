"""
BuildPolaris scheduled job placeholders.

Phase 0 wires these into Frappe's scheduler via hooks.py.
Phase 3 (Communications) adds the escalation job body.
Phase 6 (Closeout) adds the closeout digest job body.
"""

import frappe


def escalate_overdue_communications():
    """
    Phase 3: Escalate overdue RFIs, Submittals, Action Items.
    Creates Escalation Log entries and Frappe Notifications.
    """
    pass


def closeout_lookahead_digest():
    """
    Phase 6: Send closeout look-ahead digests to PM/Owner personas.
    """
    pass


def schedule_health_check():
    """
    Phase 1: Recompute schedule health for active projects.
    """
    pass
