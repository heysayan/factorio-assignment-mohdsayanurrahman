#!/usr/bin/env python
# part2_assignment/belts/main.py
import sys
import json
import networkx as nx
from collections import defaultdict

SUPER_SOURCE = "_SUPER_SOURCE"
SUPER_SINK = "_SUPER_SINK"
TOLERANCE = 1e-9

def get_node_names(v, split_nodes):
    if v in split_nodes:
        return f"{v}_IN", f"{v}_OUT"
    else:
        return v, v
        
def map_in(v, split_nodes):
    return f"{v}_IN" if v in split_nodes else v

def map_out(v, split_nodes):
    return f"{v}_OUT" if v in split_nodes else v

def get_original_name(v):
    if v.endswith("_IN"):
        return v[:-3]
    if v.endswith("_OUT"):
        return v[:-4]
    return v

def solve_belts(data):
    
    G = nx.DiGraph()
    
    sources = data.get("sources", {})
    sink_node = data["sink"]
    node_caps = data.get("node_caps", {})
    edges = data.get("edges", [])
    
    total_supply = sum(sources.values())
    total_demand = total_supply 

    all_nodes = set(sources.keys()) | {sink_node}
    for edge in edges:
        all_nodes.add(edge["from"])
        all_nodes.add(edge["to"])

    split_nodes = {
        v for v in all_nodes 
        if v in node_caps and v not in sources and v != sink_node
    }

    for v in split_nodes:
        v_in, v_out = get_node_names(v, split_nodes)
        G.add_edge(v_in, v_out, capacity=node_caps[v])

    imbalance = defaultdict(float)
    lower_bounds = {}

    for edge in edges:
        u_orig, v_orig = edge["from"], edge["to"]
        lo = edge.get("lower_bound", 0.0)
        hi = edge.get("upper_bound", float('inf'))

        u_mapped_out = map_out(u_orig, split_nodes)
        v_mapped_in = map_in(v_orig, split_nodes)
        
        cap_prime = hi - lo
        if cap_prime < -TOLERANCE:
            return {
                "status": "infeasible",
                "cut_reachable": [],
                "deficit": {"demand_balance": lo - hi, "tight_edges": [{"from": u_orig, "to": v_orig, "flow_needed": lo}]}
            }
        
        G.add_edge(u_mapped_out, v_mapped_in, capacity=max(0, cap_prime))
        
        imbalance[v_orig] += lo
        imbalance[u_orig] -= lo
        
        lower_bounds[(u_orig, v_orig)] = lo

    total_demand_to_meet = 0.0
    
    for v_orig, imb in imbalance.items():
        if imb > TOLERANCE:
            v_mapped_in = map_in(v_orig, split_nodes)
            G.add_edge(SUPER_SOURCE, v_mapped_in, capacity=imb)
            total_demand_to_meet += imb
        elif imb < -TOLERANCE:
            v_mapped_out = map_out(v_orig, split_nodes)
            G.add_edge(v_mapped_out, SUPER_SINK, capacity=-imb)
            
    for s_orig, supply in sources.items():
        s_mapped_out = map_out(s_orig, split_nodes)
        G.add_edge(SUPER_SOURCE, s_mapped_out, capacity=supply)
        total_demand_to_meet += supply
        
    t_mapped_in = map_in(sink_node, split_nodes)
    G.add_edge(t_mapped_in, SUPER_SINK, capacity=total_demand)

    if total_demand_to_meet < TOLERANCE:
        flow_value = 0.0
        flow_dict = {}
    else:
        try:
            flow_value, flow_dict = nx.maximum_flow(G, SUPER_SOURCE, SUPER_SINK)
        except nx.NetworkXUnbounded:
            return { "status": "infeasible", "cut_reachable": [], "deficit": {"demand_balance": float('inf'), "tight_nodes": ["Unbounded flow"]}}
        except nx.NetworkXError:
             return { "status": "infeasible", "cut_reachable": [], "deficit": {"demand_balance": total_demand_to_meet, "tight_nodes": ["Disconnected graph"]}}

    if abs(flow_value - total_demand_to_meet) > TOLERANCE:
        deficit = total_demand_to_meet - flow_value
        
        try:
            cut_value, partition = nx.minimum_cut(G, SUPER_SOURCE, SUPER_SINK)
            reachable, non_reachable = partition
        except nx.NetworkXError:
            try:
                reachable = nx.descendants(G, SUPER_SOURCE) | {SUPER_SOURCE}
            except nx.NetworkXError:
                reachable = set()

        cut_nodes = set()
        for v in reachable:
            if v != SUPER_SOURCE:
                cut_nodes.add(get_original_name(v))
        
        return {
            "status": "infeasible",
            "cut_reachable": sorted(list(cut_nodes)),
            "deficit": {
                "demand_balance": deficit,
                "tight_nodes": [], 
                "tight_edges": []
            }
        }

    final_flows = []
    
    for (u_orig, v_orig), lo in lower_bounds.items():
        u_mapped = map_out(u_orig, split_nodes)
        v_mapped = map_in(v_orig, split_nodes)
        
        flow_prime = 0.0
        if u_mapped in flow_dict and v_mapped in flow_dict[u_mapped]:
            flow_prime = flow_dict[u_mapped][v_mapped]
            
        final_flow = flow_prime + lo
        
        if final_flow > TOLERANCE:
            final_flows.append({
                "from": u_orig,
                "to": v_orig,
                "flow": final_flow
            })

    return {
        "status": "ok",
        "max_flow_per_min": total_supply,
        "flows": final_flows
    }


def main():
    try:
        try:
            indata = json.load(sys.stdin)
        except json.JSONDecodeError as e:
            sys.stderr.write(f"Error: Invalid JSON input. {e}\n")
            return

        result = solve_belts(indata)

        try:
            json.dump(result, sys.stdout, indent=None)
        except (IOError, TypeError) as e:
            sys.stderr.write(f"Error: Could not write JSON output. {e}\n")
            
    except Exception as e:
        sys.stderr.write(f"An unexpected error occurred: {e}\n")
        json.dump({
            "status": "infeasible",
            "cut_reachable": [],
            "deficit": {"demand_balance": 0.0, "tight_nodes": [f"Error: {e}"]}
        }, sys.stdout)

if __name__ == "__main__":
    main()