import frappe

PRINT_FORMAT_NAME = "BuildPolaris Closeout Package"

TEMPLATE = """
<div class="closeout-package">
  <h1>Closeout Package — {{ doc.project }}</h1>
  <p><strong>Closing Record:</strong> {{ doc.name }}<br/>
     <strong>Status:</strong> {{ doc.status }}<br/>
     <strong>Opened:</strong> {{ doc.opened_at }}</p>

  {% set scc = frappe.get_all("Substantial Completion Certificate", filters={"closing_record": doc.name}, fields=["name", "pm_signoff", "owner_signoff", "architect_signoff", "signed_at"]) %}
  <h2>Substantial Completion Certificate</h2>
  {% if scc %}
    {% for c in scc %}
      <p>PM: {{ c.pm_signoff or "—" }} | Owner: {{ c.owner_signoff or "—" }} |
         Architect: {{ c.architect_signoff or "—" }} | Signed: {{ c.signed_at or "Pending" }}</p>
    {% endfor %}
  {% else %}
    <p><em>No certificate on file.</em></p>
  {% endif %}

  {% set waivers = frappe.get_all("Lien Waiver", filters={"closing_record": doc.name}, fields=["supplier", "type"]) %}
  <h2>Lien Waivers ({{ waivers | length }})</h2>
  <table class="table table-bordered">
    <thead><tr><th>Supplier</th><th>Type</th></tr></thead>
    <tbody>
    {% for w in waivers %}
      <tr><td>{{ w.supplier }}</td><td>{{ w.type }}</td></tr>
    {% endfor %}
    </tbody>
  </table>

  {% set docs = frappe.get_all("Closeout Document", filters={"closing_record": doc.name}, fields=["category", "file"]) %}
  <h2>Closeout Documents ({{ docs | length }})</h2>
  <table class="table table-bordered">
    <thead><tr><th>Category</th><th>File</th></tr></thead>
    <tbody>
    {% for d in docs %}
      <tr><td>{{ d.category }}</td><td>{{ d.file }}</td></tr>
    {% endfor %}
    </tbody>
  </table>
</div>
"""


def execute():
    """FR-7.6: single professional PDF bundle via ERPNext v16's native
    Print Format + PDF engine. Idempotent - updates the template in place
    on re-run rather than erroring on a duplicate name."""
    if frappe.db.exists("Print Format", PRINT_FORMAT_NAME):
        pf = frappe.get_doc("Print Format", PRINT_FORMAT_NAME)
        pf.html = TEMPLATE
        pf.save(ignore_permissions=True)
        return

    frappe.get_doc({
        "doctype": "Print Format",
        "name": PRINT_FORMAT_NAME,
        "doc_type": "Closing Record",
        "print_format_type": "Jinja",
        "html": TEMPLATE,
        "standard": "No",
        "disabled": 0,
    }).insert(ignore_permissions=True)
