# part2_assignment/tests/test_belts.py

import json
import subprocess
import pytest

# Helper function to run the main script
def run_belts(input_data):
    process = subprocess.Popen(
        ["python3", "belts/main.py"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    stdout, stderr = process.communicate(json.dumps(input_data))
    assert process.returncode == 0, f"Process failed with stderr: {stderr}"
    return json.loads(stdout)

def test_simple_feasible_flow():
    """A simple graph that should be feasible."""
    input_data = {
        "sources": {"s1": 100},
        "sink": "t1",
        "edges": [
            {"from": "s1", "to": "a", "upper_bound": 100},
            {"from": "a", "to": "t1", "upper_bound": 100}
        ]
    }
    output = run_belts(input_data)
    assert output["status"] == "ok"
    assert abs(output["max_flow_per_min"] - 100) < 1e-6
    assert len(output["flows"]) == 2

def test_infeasible_capacity_cut():
    """A graph that is infeasible due to a simple capacity bottleneck."""
    input_data = {
        "sources": {"s1": 100},
        "sink": "t1",
        "edges": [
            {"from": "s1", "to": "a", "upper_bound": 100},
            {"from": "a", "to": "t1", "upper_bound": 50} # Bottleneck
        ]
    }
    output = run_belts(input_data)
    assert output["status"] == "infeasible"
    # The min-cut separates {s1, a} from {t1}
    assert set(output["cut_reachable"]) == {"s1", "a"}
    assert abs(output["deficit"]["demand_balance"] - 50) < 1e-6

def test_infeasible_lower_bound():
    """A graph that is infeasible because a lower bound cannot be satisfied."""
    input_data = {
        "sources": {"s1": 100},
        "sink": "t1",
        "edges": [
            {"from": "s1", "to": "a", "upper_bound": 100},
            {"from": "a", "to": "b", "lower_bound": 80, "upper_bound": 100},
            {"from": "b", "to": "t1", "upper_bound": 50} # Cannot handle the lower bound of 80
        ]
    }
    output = run_belts(input_data)
    assert output["status"] == "infeasible"

def test_node_capacity():
    """A feasible flow that is limited by a node's capacity."""
    input_data = {
        "sources": {"s1": 50, "s2": 50},
        "sink": "t1",
        "node_caps": {"a": 80}, # Node 'a' is a bottleneck
        "edges": [
            {"from": "s1", "to": "a", "upper_bound": 50},
            {"from": "s2", "to": "a", "upper_bound": 50},
            {"from": "a", "to": "t1", "upper_bound": 100}
        ]
    }
    # Total supply is 100, but node 'a' can only handle 80.
    # This should be infeasible.
    output = run_belts(input_data)
    assert output["status"] == "infeasible"
    # The cut should identify that the node 'a' is the problem.
    # The split node a_IN -> a_OUT is the tight edge.
    assert set(output["cut_reachable"]) == {"s1", "s2", "a"}
    assert abs(output["deficit"]["demand_balance"] - 20) < 1e-6