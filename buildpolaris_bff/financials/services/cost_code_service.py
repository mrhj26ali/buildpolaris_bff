"""FR-3.1: Cost Code structure per Project. FR-3.6: budget/committed/actual
rollup (field-level masking for Subcontractor is enforced natively via the
DocType JSON's permlevel, not computed here)."""
import frappe

from buildpolaris_bff.shared.exceptions import ValidationError
from buildpolaris_bff.shared.permissions import assert_project_permission, assert_role


def create_cost_code(project, code, description, budget_amount, cost_center=None, created_by=None):
	created_by = created_by or frappe.session.user
	assert_project_permission(project, ptype="write", user=created_by)
	assert_role("BuildPolaris Project Manager", "BuildPolaris Admin", user=created_by)

	if frappe.db.exists("Cost Code", {"project": project, "code": code}):
		raise ValidationError(f"Cost Code '{code}' already exists on this Project.")

	doc = frappe.get_doc({
		"doctype": "Cost Code",
		"naming_series": "CC-.YYYY.-.#####",
		"project": project,
		"code": code,
		"description": description,
		"budget_amount": budget_amount,
		"cost_center": cost_center,
	})
	doc.insert()
	return doc.as_dict()


def list_cost_codes(project, user=None):
	assert_project_permission(project, ptype="read", user=user)
	return frappe.get_all(
		"Cost Code", filters={"project": project},
		fields=["name", "code", "description", "budget_amount", "cost_center"],
	)


def get_budget_rollup(project, user=None):
	"""FR-3.6: budget vs committed vs actual per Cost Code, read live -
	never a cached rollup field."""
	assert_project_permission(project, ptype="read", user=user)

	cost_codes = list_cost_codes(project, user=user)
	rollup = []
	for cc in cost_codes:
		committed = frappe.db.sql(
			"select coalesce(sum(revised_amount), 0) from `tabCommitment` "
			"where cost_code = %s and status = 'Approved'",
			cc.name,
		)[0][0]
		actual = frappe.db.sql(
			"""select coalesce(sum(pal.work_completed_this_period + pal.materials_stored), 0)
			   from `tabPay Application Line` pal
			   inner join `tabPay Application` pa on pa.name = pal.parent
			   where pal.cost_code = %s and pa.status in ('Approved', 'Paid')""",
			cc.name,
		)[0][0]
		rollup.append({
			"cost_code": cc.name,
			"code": cc.code,
			"budget_amount": cc.budget_amount,
			"committed": committed,
			"actual": actual,
			"variance": (cc.budget_amount or 0) - (committed or 0),
		})
	return rollup
