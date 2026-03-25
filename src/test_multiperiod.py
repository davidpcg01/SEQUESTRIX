"""
Deterministic equivalence test for multiperiod vs single-period MILP models.

Uses a small hardcoded network fixture so the test runs without
external assets (no construction-costs-subset.csv required).

Verifies that Math_model(duration=T) and Math_model_multiperiod(T)
with uniform capacities produce matching objective values and
identical activated source/sink sets.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from math_model import Math_model
from math_model_multiperiod import Math_model_multiperiod


def build_fixture():
    """
    Construct a minimal 4-node network:
      source_1  --  TS1  --  sink_1
      source_2  ----/

    Returns (nodes, nodesValue, arcs, arcsInfo, paths, nodesCost).
    """
    nodes = ['source_1', 'source_2', 'TS1', 'sink_1']

    nodesValue = {
        'source_1': 1.0,
        'source_2': 1.0,
        'TS1': 0,
        'sink_1': -20.0,
    }

    arcs = [
        ('source_1', 'TS1'), ('TS1', 'source_1'),
        ('source_2', 'TS1'), ('TS1', 'source_2'),
        ('TS1', 'sink_1'), ('sink_1', 'TS1'),
    ]

    # arcsInfo: {(n1,n2): [length, weight, weighted_cost, lb, ub]}
    arcsInfo = {}
    for arc in arcs:
        arcsInfo[arc] = [50.0, 1.0, 50.0, 0.0, 56.46]

    paths = {}
    for arc in arcs:
        paths[arc] = [arc[0], arc[1]]

    # nodesCost: {node: [total_unit_cost, fixed_cost, var_cost]}
    nodesCost = {
        'source_1': [10.0, 0.5, 10.0],
        'source_2': [12.0, 0.3, 12.0],
        'sink_1':   [5.0, 0.2, 5.0],
    }

    return nodes, nodesValue, arcs, arcsInfo, paths, nodesCost


def run_test():
    T = 10
    target_cap = 1.5
    crf = 0.1

    nodes, nodesValue, arcs, arcsInfo, paths, nodesCost = build_fixture()

    # --- single-period model ---
    sp = Math_model(nodes, nodesValue, arcs, arcsInfo, paths, nodesCost,
                    duration=T, target_cap=target_cap, crf=crf)
    sp.build_model()
    sp.solve_model()
    sp_obj = sp.objective
    sp_arcs, sp_sources, sp_sinks, _, _, _ = sp.get_all_soln_results()

    # --- multiperiod model (uniform capacities, cumulative target) ---
    mp = Math_model_multiperiod(nodes, nodesValue, arcs, arcsInfo, paths, nodesCost,
                                num_periods=T, target_cap=target_cap, crf=crf)
    mp.build_model()
    mp.solve_model()
    mp_obj = mp.objective
    mp_arcs, mp_sources, mp_sinks, _, _, _ = mp.get_all_soln_results()

    # --- assertions ---
    print(f"Single-period objective: {sp_obj:.6f}")
    print(f"Multiperiod   objective: {mp_obj:.6f}")

    rel_diff = abs(sp_obj - mp_obj) / max(abs(sp_obj), 1e-12)
    print(f"Relative difference:     {rel_diff:.2e}")
    assert rel_diff < 1e-4, (
        f"Objective mismatch: single={sp_obj}, multi={mp_obj}, rel_diff={rel_diff}")

    sp_src_set = set(sp_sources.keys())
    mp_src_set = set(mp_sources.keys())
    assert sp_src_set == mp_src_set, (
        f"Source sets differ: SP={sp_src_set}, MP={mp_src_set}")

    sp_sink_set = set(sp_sinks.keys())
    mp_sink_set = set(mp_sinks.keys())
    assert sp_sink_set == mp_sink_set, (
        f"Sink sets differ: SP={sp_sink_set}, MP={mp_sink_set}")

    sp_arc_set = set(sp_arcs.keys())
    mp_arc_set = set(mp_arcs.keys())
    assert sp_arc_set == mp_arc_set, (
        f"Arc sets differ: SP={sp_arc_set}, MP={mp_arc_set}")

    for src in sp_sources:
        sp_v = sp_sources[src]
        mp_v = mp_sources[src]
        src_diff = abs(sp_v - mp_v) / max(abs(sp_v), 1e-12)
        assert src_diff < 1e-4, (
            f"Source {src} flow mismatch: SP={sp_v}, MP={mp_v}")

    for arc in sp_arcs:
        sp_v = sp_arcs[arc]
        mp_v = mp_arcs[arc]
        arc_diff = abs(sp_v - mp_v) / max(abs(sp_v), 1e-12)
        assert arc_diff < 1e-4, (
            f"Arc {arc} flow mismatch: SP={sp_v}, MP={mp_v}")

    print("\nPASS -- all assertions hold")


def run_optional_spetest():
    """
    Full pipeline smoke test using SPETEST data.
    Only runs if construction-costs-subset.csv exists locally.
    """
    csv_path = os.path.join(os.path.dirname(__file__), '..', 'construction-costs-subset.csv')
    if not os.path.exists(csv_path):
        print("\nSKIP -- construction-costs-subset.csv not found; "
              "optional SPETEST smoke test not run.")
        return

    from alternateNetworkGeo import alternateNetworkGeo
    from input_data import InputData

    input_path = os.path.join(os.path.dirname(__file__),
                              '..', 'Sequestrix', 'app', 'input_files', 'Input_File.xlsx')
    if not os.path.exists(input_path):
        print("\nSKIP -- Input_File.xlsx not found; optional SPETEST smoke test not run.")
        return

    g = alternateNetworkGeo()
    g.initialize_cost_surface()

    data = InputData(input_path)
    data._read_data()
    sources, sinks, nodesCost = data.process_data()
    g.add_sources(sources)
    g.add_sinks(sinks)
    g.generateDelaunayNetwork()
    g.enforce_no_pipeline_diagonal_Xover()
    g.get_all_source_sink_shortest_paths()
    g.get_pipe_trans_nodes()
    g.get_trans_nodes()
    g.trans_node_post_process()
    g.pipe_post_process()
    g.shortest_paths_post_process()

    nodes, arcs, costs, paths, b = g.export_network()

    T = 10
    target_cap = 1.55
    crf = 0.1

    sp = Math_model(nodes, b, arcs, costs, paths, nodesCost,
                    duration=T, target_cap=target_cap, crf=crf)
    sp.build_model()
    sp.solve_model()

    mp = Math_model_multiperiod(nodes, b, arcs, costs, paths, nodesCost,
                                num_periods=T, target_cap=target_cap, crf=crf)
    mp.build_model()
    mp.solve_model()

    rel_diff = abs(sp.objective - mp.objective) / max(abs(sp.objective), 1e-12)
    print(f"\nSPETEST single-period obj: {sp.objective:.6f}")
    print(f"SPETEST multiperiod   obj: {mp.objective:.6f}")
    print(f"SPETEST relative diff:     {rel_diff:.2e}")
    assert rel_diff < 1e-4, f"SPETEST objective mismatch: rel_diff={rel_diff}"
    print("SPETEST PASS")


if __name__ == '__main__':
    run_test()
    run_optional_spetest()
