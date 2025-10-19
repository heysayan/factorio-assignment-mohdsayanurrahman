#!/usr/bin/env python
# part2_assignment/factory/main.py
import sys
import json
import pulp
from collections import defaultdict

def solve_factory(data):

    machines = data.get("machines", {})
    recipes = data.get("recipes", {})
    modules = data.get("modules", {})
    limits = data.get("limits", {})
    target_item = data["target"]["item"]
    requested_target_rate = data["target"]["rate_per_min"]

    raw_items = set(limits.get("raw_supply_per_min", {}).keys())
    max_machines = limits.get("max_machines", {})
    raw_supply_caps = limits.get("raw_supply_per_min", {})

    eff_crafts = {}
    prod_multipliers = {}
    recipe_machine = {}
    all_items = set()
    intermediate_items = set()

    for r_name, recipe in recipes.items():
        m_name = recipe["machine"]
        recipe_machine[r_name] = m_name
        
        machine_info = machines.get(m_name, {})
        module_info = modules.get(m_name, {})

        base_speed = machine_info.get("crafts_per_min", 1) 
        speed_mod = module_info.get("speed", 0.0)
        prod_mod = module_info.get("prod", 0.0)
        time_s = recipe["time_s"]
        
        prod_multipliers[r_name] = 1.0 + prod_mod

        eff_crafts[r_name] = (base_speed * (1.0 + speed_mod) * 60.0) / time_s

        for item in recipe.get("in", {}):
            all_items.add(item)
        for item in recipe.get("out", {}):
            all_items.add(item)
            if item not in raw_items and item != target_item:
                intermediate_items.add(item)

    prob = pulp.LpProblem("Factory_Optimize", pulp.LpMinimize)

    xr_vars = {r_name: pulp.LpVariable(f"xr_{r_name}", lowBound=0) for r_name in recipes}

    inv_eff_crafts = {}
    for r_name, eff in eff_crafts.items():
        if eff > 1e-9: 
            inv_eff_crafts[r_name] = 1.0 / eff
        else:
            inv_eff_crafts[r_name] = 0.0 

    machine_usage_per_recipe = {}
    for r_name in recipes:
        if inv_eff_crafts[r_name] > 0:
            machine_usage_per_recipe[r_name] = xr_vars[r_name] * inv_eff_crafts[r_name]
        else:
            prob += xr_vars[r_name] == 0, f"Zero_Eff_Craft_{r_name}"
            machine_usage_per_recipe[r_name] = 0.0 

    total_machine_usage = pulp.lpSum(machine_usage_per_recipe.values())
    prob += total_machine_usage, "Minimize_Total_Machines"

    sorted_recipe_names = sorted(recipes.keys())
    
    EPSILON = 1e-7 
    
    tie_breaker = pulp.lpSum([
        (EPSILON**(i + 1)) * xr_vars[r_name] 
        for i, r_name in enumerate(sorted_recipe_names)
    ])

    prob += total_machine_usage + tie_breaker, "Minimize_Machines_Lexicographically"

    item_balance = defaultdict(pulp.LpAffineExpression)

    for r_name, recipe in recipes.items():
        xr = xr_vars[r_name]
        prod_mult = prod_multipliers[r_name]

        for item, amount in recipe.get("in", {}).items():
            item_balance[item] -= xr * amount

        for item, amount in recipe.get("out", {}).items():
            item_balance[item] += xr * amount * prod_mult 

    for item in all_items:
        balance_expr = item_balance[item]
        
        if item == target_item:
            prob += balance_expr == float(requested_target_rate), f"Target_Rate_{item}"
        
        elif item in intermediate_items:
            prob += balance_expr >= -1e-9, f"Intermediate_Balance_low_{item}"
            prob += balance_expr <= 1e-9, f"Intermediate_Balance_high_{item}"

        elif item in raw_items:
            prob += balance_expr <= 1e-9, f"Raw_Net_Consume_{item}"
            
            consumption = -balance_expr
            cap = raw_supply_caps.get(item, 0)
            prob += consumption <= cap + 1e-9, f"Raw_Supply_Cap_{item}" 

    machine_usage_per_type = defaultdict(pulp.LpAffineExpression)
    for r_name in recipes:
        m_name = recipe_machine[r_name]
        machine_usage_per_type[m_name] += machine_usage_per_recipe[r_name]

    for m_name, cap in max_machines.items():
        usage = machine_usage_per_type.get(m_name)
        if usage is not None:
            prob += usage <= cap + 1e-9, f"Machine_Cap_{m_name}" 

    prob.solve(pulp.PULP_CBC_CMD(msg=False))

    if prob.status == pulp.LpStatusOptimal:
        per_recipe_crafts = {
            r_name: var.varValue for r_name, var in xr_vars.items()
        }
        
        per_machine_counts = {
            m_name: usage.value() 
            for m_name, usage in machine_usage_per_type.items() 
            if usage.value() > 1e-9 
        }
        
        raw_consumption = {
            item: (-item_balance[item].value())
            for item in raw_items
            if (-item_balance[item].value()) > 1e-9 
        }
        
        return {
            "status": "ok",
            "per_recipe_crafts_per_min": per_recipe_crafts,
            "per_machine_counts": per_machine_counts,
            "raw_consumption_per_min": raw_consumption
        }

    prob_max = pulp.LpProblem("Factory_MaxRate", pulp.LpMaximize)

    T_var = pulp.LpVariable("Max_Target_Rate", lowBound=0)
    
    xr_vars_max = {r_name: pulp.LpVariable(f"xr_{r_name}", lowBound=0) for r_name in recipes}

    prob_max += T_var, "Maximize_Target_Rate"

    item_balance_max = defaultdict(pulp.LpAffineExpression)
    for r_name, recipe in recipes.items():
        xr = xr_vars_max[r_name]
        prod_mult = prod_multipliers[r_name]
        for item, amount in recipe.get("in", {}).items():
            item_balance_max[item] -= xr * amount
        for item, amount in recipe.get("out", {}).items():
            item_balance_max[item] += xr * amount * prod_mult

    constraint_map = {} 
    for item in all_items:
        balance_expr = item_balance_max[item]
        
        if item == target_item:
            c = (balance_expr == T_var)
            prob_max += c, f"Target_Rate_{item}"
        
        elif item in intermediate_items:
            prob_max += balance_expr >= -1e-9, f"Intermediate_Balance_low_{item}"
            prob_max += balance_expr <= 1e-9, f"Intermediate_Balance_high_{item}"

        elif item in raw_items:
            prob_max += balance_expr <= 1e-9, f"Raw_Net_Consume_{item}"
            
            consumption = -balance_expr
            cap = raw_supply_caps.get(item, 0)
            c = (consumption <= cap + 1e-9)
            prob_max += c, f"Raw_Supply_Cap_{item}"
            constraint_map[f"raw:{item}"] = c 

    machine_usage_per_type_max = defaultdict(pulp.LpAffineExpression)
    for r_name in recipes:
        m_name = recipe_machine[r_name]
        inv_eff_craft = inv_eff_crafts[r_name]
        machine_usage_per_type_max[m_name] += xr_vars_max[r_name] * inv_eff_craft if inv_eff_craft > 0 else 0.0


    for m_name, cap in max_machines.items():
        usage = machine_usage_per_type_max.get(m_name)
        if usage is not None:
            c = (usage <= cap + 1e-9)
            prob_max += c, f"Machine_Cap_{m_name}"
            constraint_map[f"machine:{m_name}"] = c 

    prob_max.solve(pulp.PULP_CBC_CMD(msg=False))

    if prob_max.status != pulp.LpStatusOptimal:
        return {
            "status": "infeasible",
            "max_feasible_target_per_min": 0.0,
            "bottleneck_hint": ["Fundamental infeasibility"]
        }

    max_rate = T_var.varValue
    bottleneck_hints = []

    tolerance = 1e-6
    for name, constraint in constraint_map.items():
        if constraint.slack is not None and abs(constraint.slack) < tolerance:
            ctype, cname = name.split(":", 1)
            if ctype == "raw":
                bottleneck_hints.append(f"{cname} supply") 
            elif ctype == "machine":
                bottleneck_hints.append(f"{cname} cap") 

    return {
        "status": "infeasible",
        "max_feasible_target_per_min": max_rate,
        "bottleneck_hint": sorted(list(set(bottleneck_hints))) 
    }


def main():
    try:
        try:
            indata = json.load(sys.stdin)
        except json.JSONDecodeError as e:
            sys.stderr.write(f"Error: Invalid JSON input. {e}\n")
            return

        result = solve_factory(indata)

        try:
            json.dump(result, sys.stdout, indent=None) 
        except (IOError, TypeError) as e:
            sys.stderr.write(f"Error: Could not write JSON output. {e}\n")

    except Exception as e:
        sys.stderr.write(f"An unexpected error occurred: {e}\n")
        json.dump({
            "status": "infeasible",
            "max_feasible_target_per_min": 0.0,
            "bottleneck_hint": [f"Error: {e}"]
        }, sys.stdout)

if __name__ == "__main__":
    main()