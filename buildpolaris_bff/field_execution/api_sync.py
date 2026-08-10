import json
import frappe
from frappe import _
from buildpolaris_bff.shared.api_utils import standard_response, handle_api_error
from buildpolaris_bff.shared.guards import require_authenticated_user
from buildpolaris_bff.field_execution.services.sync import process_mutations

@frappe.whitelist()
@require_authenticated_user
def sync_field_mutations(mutations, last_sync_timestamp=0):
    """
    Endpoint for PWA to sync offline field mutations.
    """
    try:
        if isinstance(mutations, str):
            mutations = json.loads(mutations)
            
        result = process_mutations(mutations, float(last_sync_timestamp))
        return standard_response(True, result, _("Field data synced successfully"))
    except Exception as e:
        return handle_api_error(e)
