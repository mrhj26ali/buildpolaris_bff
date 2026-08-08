import frappe
from frappe.exceptions import ValidationError

def validate_acyclic_graph(predecessor: str, successor: str):
    """FR-4: Prevent circular dependencies via DFS cycle detection."""
    visited = set()
    
    def dfs(node):
        if node == predecessor:
            raise ValidationError(f"Circular dependency detected: {successor} eventually links back to {predecessor}")
        if node in visited:
            return
        visited.add(node)
        next_nodes = frappe.get_all("Task Dependency", filters={"predecessor_task": node}, pluck="successor_task")
        for next_node in next_nodes:
            dfs(next_node)
            
    dfs(successor)

@frappe.whitelist()
def run_dcma_health_check(project_id: str) -> dict:
    """FR-15: Schedule Quality Health Check (DCMA 14-Point Assessment)"""
    tasks = frappe.get_all("Task", filters={"project": project_id, "status": ["!=", "Cancelled"]}, 
                           fields=["name", "activity_type", "total_float", "constraint_type"])
    
    if not tasks:
        return {"error": "No activities found for this project."}

    deps = frappe.get_all("Task Dependency", filters={"project": project_id}, fields=["*"])
    total_tasks = len([t for t in tasks if t.activity_type not in ["Level of Effort", "WBS Summary"]])
    metrics = {}

    # 1. Logic (Missing Predecessor/Successor)
    tasks_with_deps = set(d.predecessor_task for d in deps) | set(d.successor_task for d in deps)
    dangling = [t.name for t in tasks if t.name not in tasks_with_deps and t.activity_type == "Task"]
    metrics["logic_missing"] = {"value": len(dangling), "threshold": "<= 5%", "status": "PASS" if len(dangling) / max(total_tasks, 1) <= 0.05 else "FAIL"}

    # 2. Leads (Negative Lag)
    leads = [d for d in deps if d.lag_days < 0]
    metrics["leads_negative_lag"] = {"value": len(leads), "threshold": "0", "status": "PASS" if len(leads) == 0 else "FAIL"}

    # 3. Hard Constraints
    hard_constraints = [t for t in tasks if t.constraint_type in ["MSO", "MFO"]]
    metrics["hard_constraints"] = {"value": len(hard_constraints), "threshold": "<= 5%", "status": "PASS" if len(hard_constraints) / max(total_tasks, 1) <= 0.05 else "FAIL"}

    # 4. Negative Float
    neg_float = [t for t in tasks if t.total_float and t.total_float < 0]
    metrics["negative_float"] = {"value": len(neg_float), "threshold": "0", "status": "PASS" if len(neg_float) == 0 else "FAIL"}

    return metrics