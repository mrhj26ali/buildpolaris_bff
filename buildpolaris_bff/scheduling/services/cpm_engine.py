import frappe
from frappe.utils import getdate, add_days

def calculate_cpm(tasks: list[dict], project_start_date: str) -> dict:
    """
    Calculates the Critical Path Method (CPM) schedule.
    
    Input tasks format:
    [
        { "id": "task-1", "duration": 5, "predecessors": [] },
        { "id": "task-2", "duration": 3, "predecessors": ["task-1"] }
    ]
    
    Returns tasks with start_date, finish_date, total_float, and is_critical.
    """
    if not tasks:
        return {"tasks": [], "critical_path": [], "project_duration": 0}
        
    task_map = {t["id"]: t for t in tasks}
    
    # Initialize schedule fields
    for t in tasks:
        t["es"] = 0  # Early Start
        t["ef"] = 0  # Early Finish
        t["ls"] = 0  # Late Start
        t["lf"] = 0  # Late Finish
        t["total_float"] = 0
        t["is_critical"] = False
        
    # Forward Pass: Calculate Early Start (ES) and Early Finish (EF)
    changed = True
    max_iterations = len(tasks) + 1
    iteration = 0
    
    while changed and iteration < max_iterations:
        changed = False
        iteration += 1
        
        for t in tasks:
            max_pred_ef = 0
            for pred_id in t.get("predecessors", []):
                if pred_id in task_map:
                    pred_ef = task_map[pred_id]["ef"]
                    if pred_ef > max_pred_ef:
                        max_pred_ef = pred_ef
            
            new_es = max_pred_ef
            new_ef = new_es + t.get("duration", 0)
            
            if new_es != t["es"] or new_ef != t["ef"]:
                t["es"] = new_es
                t["ef"] = new_ef
                changed = True
                
    # Project Finish Date
    project_finish = max(t["ef"] for t in tasks) if tasks else 0
    
    # Backward Pass: Calculate Late Start (LS) and Late Finish (LF)
    changed = True
    iteration = 0
    
    while changed and iteration < max_iterations:
        changed = False
        iteration += 1
        
        for t in tasks:
            min_succ_ls = project_finish
            
            # Find successors (tasks that depend on current task)
            for other_t in tasks:
                if t["id"] in other_t.get("predecessors", []):
                    if other_t["ls"] < min_succ_ls:
                        min_succ_ls = other_t["ls"]
            
            new_lf = min_succ_ls
            new_ls = new_lf - t.get("duration", 0)
            
            if new_ls != t["ls"] or new_lf != t["lf"]:
                t["ls"] = new_ls
                t["lf"] = new_lf
                changed = True
                
    # Calculate Total Float and identify Critical Path
    critical_path = []
    
    for t in tasks:
        t["total_float"] = t["ls"] - t["es"]
        
        if t["total_float"] == 0:
            t["is_critical"] = True
            critical_path.append(t["id"])
            
    # Convert relative days to actual calendar dates
    start_dt = getdate(project_start_date)
    
    for t in tasks:
        t["start_date"] = str(add_days(start_dt, t["es"]))
        t["finish_date"] = str(add_days(start_dt, t["ef"]))
        
        # Clean up relative fields for the client response
        t.pop("es", None)
        t.pop("ef", None)
        t.pop("ls", None)
        t.pop("lf", None)
        
    return {
        "tasks": tasks,
        "critical_path": critical_path,
        "project_duration": project_finish,
        "project_finish_date": str(add_days(start_dt, project_finish))
    }
