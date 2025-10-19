# part2_assignment/tests/test_factory.py

import json
import subprocess
import pytest

# Helper function to run the main script
def run_factory(input_data):
    process = subprocess.Popen(
        ["python3", "factory/main.py"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    stdout, stderr = process.communicate(json.dumps(input_data))
    assert process.returncode == 0, f"Process failed with stderr: {stderr}"
    return json.loads(stdout)

def test_simple_success():
    """Tests the basic success case provided in the assignment PDF # 96-152]."""
    input_data = {
        "machines": {"assembler_1": {"crafts_per_min": 30}, "chemical": {"crafts_per_min": 60}},
        "recipes": {
            "iron_plate": {"machine": "chemical", "time_s": 3.2, "in": {"iron_ore": 1}, "out": {"iron_plate": 1}},
            "copper_plate": {"machine": "chemical", "time_s": 3.2, "in": {"copper_ore": 1}, "out": {"copper_plate": 1}},
            "green_circuit": {"machine": "assembler_1", "time_s": 0.5, "in": {"iron_plate": 1, "copper_plate": 3}, "out": {"green_circuit": 1}}
        },
        "modules": {"assembler_1": {"prod": 0.1, "speed": 0.15}, "chemical": {"prod": 0.2, "speed": 0.1}},
        "limits": {"raw_supply_per_min": {"iron_ore": 5000, "copper_ore": 5000}, "max_machines": {"assembler_1": 300, "chemical": 300}},
        "target": {"item": "green_circuit", "rate_per_min": 1800}
    }
    output = run_factory(input_data)
    
    assert output["status"] == "ok"
    assert abs(output["per_recipe_crafts_per_min"]["green_circuit"] - 1800 / 1.1) < 1e-3
    # Note: 1800 is required output. Prod is 0.1, so crafts = 1800 / (1+0.1)
    
def test_infeasible_machine_limit():
    """Tests a case that is infeasible due to a machine cap."""
    input_data = {
        "machines": {"assembler": {"crafts_per_min": 60}},
        "recipes": {"widget": {"machine": "assembler", "time_s": 1, "in": {}, "out": {"widget": 1}}},
        "limits": {"max_machines": {"assembler": 10}},
        "target": {"item": "widget", "rate_per_min": 10000}
    }
    # Effective crafts/min = 60 * 60 / 1 = 3600 per machine
    # Max production = 10 machines * 3600 crafts/min = 36000 widgets/min
    # Whoops, let's make it infeasible
    # Max production = 10 machines * 3600 = 36000. Wait, this is feasible.
    # Correct calculation: machines needed = 10000 / 3600 = 2.77. This IS feasible.
    # Let's adjust target to be infeasible.
    input_data["target"]["rate_per_min"] = 40000
    # Machines needed = 40000 / 3600 = 11.11, which is > 10.
    
    output = run_factory(input_data)
    assert output["status"] == "infeasible"
    assert "assembler cap" in output["bottleneck_hint"]
    assert abs(output["max_feasible_target_per_min"] - 36000) < 1e-6

def test_lexicographical_tie_break():
    """
    Tests the tie-breaking logic.
    Two recipes, 'alpha_rod' and 'beta_rod', can make 'rod'.
    They have identical machine costs. The solver must prefer using
    'beta_rod' over 'alpha_rod' to minimize the crafts of 'alpha_rod' to 0.
    """
    input_data = {
        "machines": {"assembler": {"crafts_per_min": 60}},
        "recipes": {
            "alpha_rod": {"machine": "assembler", "time_s": 1, "in": {}, "out": {"rod": 1}},
            "beta_rod": {"machine": "assembler", "time_s": 1, "in": {}, "out": {"rod": 1}}
        },
        "limits": {"max_machines": {"assembler": 10}},
        "target": {"item": "rod", "rate_per_min": 100}
    }
    # Both recipes cost the same number of machines.
    # A valid solution is {alpha: 100, beta: 0}.
    # Another valid solution is {alpha: 0, beta: 100}.
    # Another is {alpha: 50, beta: 50}.
    # Lexicographically, we want to minimize crafts for 'alpha_rod' first.
    # The optimal solution should be {alpha_rod: 0, beta_rod: 100}.
    
    output = run_factory(input_data)
    assert output["status"] == "ok"
    assert abs(output["per_recipe_crafts_per_min"]["alpha_rod"]) < 1e-6
    assert abs(output["per_recipe_crafts_per_min"]["beta_rod"] - 100) < 1e-6