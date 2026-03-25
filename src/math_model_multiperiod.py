import os
import re
import pulp as pl
from pulp import *
from typing import Dict, List, Set
import pandas as pd
import numpy as np
import gurobipy as gp
import logging
from gurobipy import GRB
import time

MPS_FILE_PATH = os.path.join("Sequestrix/app/solver_files/CO2_network_optimization.mps")
LP_FILE_PATH = os.path.join("Sequestrix/app/solver_files/CO2_network_optimization.lp")
SOL_FILE_PATH = os.path.join("Sequestrix/app/solver_files/CO2_network_optimization.sol")
ILP_FILE_PATH = os.path.join("Sequestrix/app/solver_files/CO2_network_optimization.ilp")

LOGGER = logging.getLogger(__name__)
FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
logging.basicConfig(filename='model_solve.log', filemode='w', level=logging.DEBUG, format=FORMAT)
START_TIME = time.time()


class Math_model_multiperiod:
    def __init__(self, nodes, nodesValue, arcs, arcsInfo, paths, nodesCost,
                 num_periods, target_cap, source_cap_t=None, sink_inject_t=None,
                 target_cap_t=None, crf=0.1):
        self.nodes = nodes
        self.arcs = arcs
        self.nodesValue = nodesValue
        self.arcsInfo = arcsInfo
        self.paths = paths
        self.nodesCost = nodesCost
        self.T = num_periods
        self.duration = num_periods
        self.target_cap = target_cap
        self.crf = crf
        self.periods = list(range(1, self.T + 1))
        self.source_cap_t = source_cap_t or {}
        self.sink_inject_t = sink_inject_t or {}
        self.target_cap_t = target_cap_t or {}

        self.costTrend = {"Slope": [0.1157192, 0.0783067],
                          "Intercept": [0.4316551, 0.770037]}
        self.c = len(self.costTrend["Slope"])

        self._initialize_sets()
        self._initialize_source_parameters()
        self._initialize_sink_parameters()
        self._initialize_arcs_parameters()
        self._initialize_pipeline_parameters()

        self.vars: Dict[str, gp.tupledict] = {}
        self.cons: Dict[str, gp.tupledict] = {}

        self.Big_M = 56.46
        self.LTrend = 6.86

    # ------------------------------------------------------------------ sets
    def _initialize_sets(self) -> None:
        self.asset: Set = set()
        self.src: Set = set()
        self.sink: Set = set()
        self.node: Set = set()
        self.epipe: Set = set()
        self.a_a: Set = set()
        self.two_way_arcs: Dict = set()

    def _initialize_source_parameters(self) -> None:
        self.source_annual_cap: Dict = {}
        self.capture_cost: Dict = {}
        self.capture_fixed_cost: Dict = {}
        self.capture_var_cost: Dict = {}

    def _initialize_sink_parameters(self) -> None:
        self.sink_cap: Dict = {}
        self.storage_cost: Dict = {}
        self.storage_fixed_cost: Dict = {}
        self.storage_var_cost: Dict = {}

    def _initialize_arcs_parameters(self) -> None:
        self.max_arc_cap: Dict = {}
        self.min_arc_cap: Dict = {}
        self.arc_length: Dict = {}
        self.arc_weight: Dict = {}
        self.arc_cost: Dict = {}

    def _initialize_pipeline_parameters(self) -> None:
        self.pipe_nodes: Dict = {}

    def _generate_sets(self) -> None:
        self.asset = set(self.nodes)
        self.src = set([node for node in self.nodes if 'source' in node])
        self.sink = set([node for node in self.nodes if 'sink' in node])
        self.node = set([node for node in self.nodes
                         if ((node not in self.src) and (node not in self.sink))])
        self.epipe = set([node.split("_")[0] for node in self.nodes
                          if ("_" in node) and ('source' not in node) and ('sink' not in node)])
        self.a_a = set(self.arcs)

        seen = {}
        result = []
        for (a, b) in self.a_a:
            if (a, b) not in seen:
                seen[(a, b)] = True
                if (b, a) in seen:
                    result.append((b, a))
        self.two_way_arcs = set(result)

    def _generate_parameters(self) -> None:
        self.source_annual_cap = {key: self.nodesValue[key] for key in self.src}
        self.capture_cost = {key: self.nodesCost[key][0] for key in self.src}
        self.capture_fixed_cost = {key: self.nodesCost[key][1] for key in self.src}
        self.capture_var_cost = {key: self.nodesCost[key][2] for key in self.src}
        self.capture_v_cost = {
            key: self.capture_cost[key]
            if (self.capture_var_cost[key] == 0) and (self.capture_fixed_cost[key] == 0)
            else self.capture_var_cost[key]
            for key in self.src
        }

        self.sink_cap = {key: self.nodesValue[key] for key in self.sink}
        self.storage_cost = {key: self.nodesCost[key][0] for key in self.sink}
        self.storage_fixed_cost = {key: self.nodesCost[key][1] for key in self.sink}
        self.storage_var_cost = {key: self.nodesCost[key][2] for key in self.sink}
        self.storage_v_cost = {
            key: self.storage_cost[key]
            if (self.storage_var_cost[key] == 0) and (self.storage_fixed_cost[key] == 0)
            else self.storage_var_cost[key]
            for key in self.sink
        }

        self.MaxCap = sum(self.source_annual_cap.values())
        self.MidCap = ((self.costTrend["Intercept"][1] - self.costTrend["Intercept"][0])
                       / (self.costTrend["Slope"][0] - self.costTrend["Slope"][1]))

        self.max_arc_cap = {
            (akey[0], akey[1], ckey):
                self.arcsInfo[akey][4] if self.arcsInfo[akey][4] < self.MidCap
                else self.MidCap if ckey == 0 else self.MaxCap
            for akey in self.a_a for ckey in range(self.c)
        }
        self.min_arc_cap = {
            (akey[0], akey[1], ckey):
                self.arcsInfo[akey][3] if self.arcsInfo[akey][3] > 0 else 0
            for akey in self.a_a for ckey in range(self.c)
        }
        self.arc_length = {key: self.arcsInfo[key][0] for key in self.a_a}
        self.arc_weight = {key: self.arcsInfo[key][1] for key in self.a_a}
        self.arc_cost = {key: self.arcsInfo[key][2] for key in self.a_a}
        self.pipe_nodes = {key: [pipenode for pipenode in self.node if key in pipenode]
                           for key in self.epipe}

        # --- multiperiod-specific: time-indexed source capacities ---
        self.source_annual_cap_t = {}
        for s in self.src:
            self.source_annual_cap_t[s] = {}
            for t in self.periods:
                if s in self.source_cap_t and t in self.source_cap_t[s]:
                    self.source_annual_cap_t[s][t] = self.source_cap_t[s][t]
                else:
                    self.source_annual_cap_t[s][t] = self.source_annual_cap[s]

        # --- multiperiod-specific: time-indexed sink injectivity ---
        self.sink_inject_t_param = {}
        for d in self.sink:
            self.sink_inject_t_param[d] = {}
            for t in self.periods:
                if d in self.sink_inject_t and t in self.sink_inject_t[d]:
                    self.sink_inject_t_param[d][t] = self.sink_inject_t[d][t]
                else:
                    self.sink_inject_t_param[d][t] = abs(self.sink_cap[d])

    def _validation_checks(self) -> None:
        total_source_cap = sum(self.source_annual_cap.values())
        total_sink_cap = -sum(self.sink_cap.values()) / self.duration
        total_max_arc_flow = sum(self.max_arc_cap.values())

        LOGGER.info(f'Target capacity (MTCO2/yr): {self.target_cap}')
        LOGGER.info(f'Total source capacity (MTCO2/yr): {total_source_cap}')
        LOGGER.info(f'Total sink capacity (MTCO2/yr): {total_sink_cap}')
        LOGGER.info(f'Total pipe capacity (MTCO2/yr): {total_max_arc_flow}')

        limiting_flow = min(total_source_cap, total_sink_cap, total_max_arc_flow)
        LOGGER.info(f'Limiting Flow (MTCO2/yr): {limiting_flow}')

        if self.target_cap > limiting_flow:
            LOGGER.warning('Target cap greater than limiting flow, resetting target to limiting flow')
            self.target_cap = limiting_flow

    def create_sets_and_parameters(self):
        self._generate_sets()
        self._generate_parameters()
        self._validation_checks()

    # --------------------------------------------------------------- gurobi
    def _initialize_gurobi(self) -> None:
        self.env = gp.Env(empty=True)
        self.env.start()
        self.model = gp.Model("CO2_network_optimization", env=self.env)

    # ------------------------------------------------------------ variables
    def create_variables(self) -> None:
        # 4-tuple: time-indexed flow
        index = [(n1, n2, c, t) for (n1, n2) in self.a_a
                 for c in range(self.c) for t in self.periods]
        self.vars['arc_flow'] = self.model.addVars(
            index, name='arc_flow', lb=0, vtype=GRB.CONTINUOUS)

        # 2-tuple: time-indexed capture
        index = [(s, t) for s in self.src for t in self.periods]
        self.vars['CO2_captured'] = self.model.addVars(
            index, name='CO2_captured', lb=0, vtype=GRB.CONTINUOUS)

        # 2-tuple: time-indexed injection
        index = [(d, t) for d in self.sink for t in self.periods]
        self.vars['CO2_injected'] = self.model.addVars(
            index, name='CO2_injected', lb=0, vtype=GRB.CONTINUOUS)

        # 3-tuple: time-invariant arc built
        index = [(n1, n2, c) for (n1, n2) in self.a_a for c in range(self.c)]
        self.vars['arc_built'] = self.model.addVars(
            index, name='arc_built', vtype=GRB.BINARY)

        # 1-key: time-invariant source/sink activation
        self.vars['src_opened'] = self.model.addVars(
            self.src, name='src_opened', vtype=GRB.BINARY)
        self.vars['sink_opened'] = self.model.addVars(
            self.sink, name='sink_opened', vtype=GRB.BINARY)

    # --------------------------------------------------------- constraints
    def _arc_upper_lower_bound_cons(self) -> None:
        for (n1, n2) in self.a_a:
            for c in range(self.c):
                for t in self.periods:
                    self.model.addConstr(
                        self.vars['arc_flow'][n1, n2, c, t]
                        >= self.min_arc_cap[n1, n2, c] * self.vars['arc_built'][n1, n2, c],
                        name=f'arc_lb_{n1}_{n2}_{c}_{t}')
                    self.model.addConstr(
                        self.vars['arc_flow'][n1, n2, c, t]
                        <= self.max_arc_cap[n1, n2, c] * self.vars['arc_built'][n1, n2, c],
                        name=f'arc_ub_{n1}_{n2}_{c}_{t}')

    def _single_direction_arc_flow_cons(self) -> None:
        cons_name = 'arc_single_dir_flow'
        constr = (sum(self.vars['arc_built'][node1, node2, c] for c in range(self.c)) <= 1
                  for (node1, node2) in self.a_a)
        self.cons[cons_name] = self.model.addConstrs(constr, name=cons_name)

    def _node_balance_cons(self) -> None:
        asset_to_node = {n: [a for a in self.asset if (a, n) in self.a_a]
                         for n in self.node}
        node_to_asset = {n: [a for a in self.asset if (n, a) in self.a_a]
                         for n in self.node}
        for t in self.periods:
            for n in self.node:
                self.model.addConstr(
                    sum(self.vars['arc_flow'][a, n, c, t]
                        for a in asset_to_node[n] for c in range(self.c))
                    == sum(self.vars['arc_flow'][n, a, c, t]
                           for a in node_to_asset[n] for c in range(self.c)),
                    name=f'node_balance_{n}_{t}')

    def _demand_balance_cons(self) -> None:
        asset_to_demand = {d: [a for a in self.asset if (a, d) in self.a_a]
                           for d in self.sink}
        demand_to_asset = {d: [a for a in self.asset if (d, a) in self.a_a]
                           for d in self.sink}
        for t in self.periods:
            for d in self.sink:
                self.model.addConstr(
                    sum(self.vars['arc_flow'][a, d, c, t]
                        for a in asset_to_demand[d] for c in range(self.c))
                    - sum(self.vars['arc_flow'][d, a, c, t]
                          for a in demand_to_asset[d] for c in range(self.c))
                    == self.vars['CO2_injected'][d, t],
                    name=f'demand_balance_{d}_{t}')

    def _supply_balance_cons(self) -> None:
        asset_to_supply = {s: [a for a in self.asset if (a, s) in self.a_a]
                           for s in self.src}
        supply_to_asset = {s: [a for a in self.asset if (s, a) in self.a_a]
                           for s in self.src}
        for t in self.periods:
            for s in self.src:
                self.model.addConstr(
                    sum(self.vars['arc_flow'][a, s, c, t]
                        for a in asset_to_supply[s] for c in range(self.c))
                    - sum(self.vars['arc_flow'][s, a, c, t]
                          for a in supply_to_asset[s] for c in range(self.c))
                    == -self.vars['CO2_captured'][s, t],
                    name=f'supply_balance_{s}_{t}')

    def _capture_limit_cons(self) -> None:
        for s in self.src:
            for t in self.periods:
                self.model.addConstr(
                    self.vars['CO2_captured'][s, t]
                    <= self.source_annual_cap_t[s][t] * self.vars['src_opened'][s],
                    name=f'capture_limit_{s}_{t}')

    def _storage_limit_cons(self) -> None:
        # Per-period injectivity bound
        for d in self.sink:
            for t in self.periods:
                self.model.addConstr(
                    self.vars['CO2_injected'][d, t]
                    <= self.sink_inject_t_param[d][t] * self.vars['sink_opened'][d],
                    name=f'inject_limit_{d}_{t}')

        # Cumulative storage bound
        for d in self.sink:
            self.model.addConstr(
                sum(self.vars['CO2_injected'][d, t] for t in self.periods)
                <= -self.sink_cap[d] * self.vars['sink_opened'][d],
                name=f'cumulative_storage_{d}')

    def _capture_target_cons(self) -> None:
        if self.target_cap_t:
            for t in self.periods:
                if t in self.target_cap_t:
                    self.model.addConstr(
                        sum(self.vars['CO2_captured'][s, t] for s in self.src)
                        >= self.target_cap_t[t],
                        name=f'capture_target_{t}')
        else:
            self.model.addConstr(
                sum(self.vars['CO2_captured'][s, t]
                    for s in self.src for t in self.periods)
                >= self.target_cap * self.T,
                name='capture_target_cumulative')

    def create_constraints(self) -> None:
        self._arc_upper_lower_bound_cons()
        msg = ("'Arc Bounds' constraint: Time elapsed: %.2f seconds"
               % (time.time() - START_TIME))
        print(msg)
        LOGGER.info(msg)
        self._single_direction_arc_flow_cons()
        msg = ("'Single Direction' constraint: Time elapsed: %.2f seconds"
               % (time.time() - START_TIME))
        print(msg)
        LOGGER.info(msg)
        self._node_balance_cons()
        msg = ("'Node Balance' constraint: Time elapsed: %.2f seconds"
               % (time.time() - START_TIME))
        print(msg)
        LOGGER.info(msg)
        self._demand_balance_cons()
        msg = ("'Demand Balance' constraint: Time elapsed: %.2f seconds"
               % (time.time() - START_TIME))
        print(msg)
        LOGGER.info(msg)
        self._supply_balance_cons()
        msg = ("'Supply Balance' constraint: Time elapsed: %.2f seconds"
               % (time.time() - START_TIME))
        print(msg)
        LOGGER.info(msg)
        self._capture_limit_cons()
        msg = ("'Capture Limit' constraint: Time elapsed: %.2f seconds"
               % (time.time() - START_TIME))
        print(msg)
        LOGGER.info(msg)
        self._storage_limit_cons()
        msg = ("'Storage Limit' constraint: Time elapsed: %.2f seconds"
               % (time.time() - START_TIME))
        print(msg)
        LOGGER.info(msg)
        self._capture_target_cons()
        msg = ("'Capture Target' constraint: Time elapsed: %.2f seconds"
               % (time.time() - START_TIME))
        print(msg)
        LOGGER.info(msg)

    # ----------------------------------------------------------- objective
    def create_objective(self) -> None:
        fixed_cap = sum(self.capture_fixed_cost[s] * self.vars['src_opened'][s]
                        for s in self.src)
        fixed_sto = sum(self.storage_fixed_cost[d] * self.vars['sink_opened'][d]
                        for d in self.sink)

        var_cap = sum(self.capture_v_cost[s] * self.vars['CO2_captured'][s, t]
                      for s in self.src for t in self.periods)
        var_sto = sum(self.storage_v_cost[d] * self.vars['CO2_injected'][d, t]
                      for d in self.sink for t in self.periods)

        transport_flow = sum(
            (self.costTrend["Slope"][c] * self.vars['arc_flow'][n1, n2, c, t])
            * self.arc_cost[n1, n2] * self.crf
            for (n1, n2) in self.a_a for c in range(self.c) for t in self.periods)

        pipeline_build = sum(
            (self.costTrend["Intercept"][c] * self.vars['arc_built'][n1, n2, c])
            * self.arc_cost[n1, n2] * self.crf
            for (n1, n2) in self.a_a for c in range(self.c)) * self.T

        obj = fixed_cap + fixed_sto + var_cap + var_sto + transport_flow + pipeline_build
        self.model.setObjective(obj, GRB.MINIMIZE)
        self.model.update()

    # ---------------------------------------------------------- build/solve
    def build_model(self) -> None:
        self._initialize_gurobi()
        print('\nInitialized Gurobi model instance\n')
        LOGGER.info('\nInitialized Gurobi model instance')
        LOGGER.info('Creating sets and parameters...')
        print('Creating sets and parameters...')
        self.create_sets_and_parameters()
        print('Sets and parameters are generated')
        print("Time elapsed: %.2f seconds" % (time.time() - START_TIME))
        LOGGER.info('Sets and parameters are generated')
        LOGGER.info("Time elapsed: %.2f seconds" % (time.time() - START_TIME))
        LOGGER.info('Setting variables...')
        print('\nSetting variables...')
        self.create_variables()
        print('Variables are defined')
        print("Time elapsed: %.2f seconds" % (time.time() - START_TIME))
        LOGGER.info('Variables are defined')
        LOGGER.info("Time elapsed: %.2f seconds" % (time.time() - START_TIME))
        LOGGER.info('Imposing constraints...')
        print('\nImposing constraints...')
        self.create_constraints()
        print('Constraints are enforced\n')
        LOGGER.info('Constraints are enforced')
        print('Solving model...\n')

    def solve_model(self) -> None:
        LOGGER.info('Evaluating "minimum cost" objective function')
        self.create_objective()
        LOGGER.info('Objective function "minimum cost" evaluated')
        self.use_pulp = False

        self.model.write(LP_FILE_PATH)
        self.model.write(MPS_FILE_PATH)

        if (self.model.NumVars <= 2000) and (self.model.NumConstrs <= 2000):
            self.model.optimize()
            LOGGER.info(f'Model Status: {self.model.status}')
            if self.model.status == GRB.INFEASIBLE:
                self.model.computeIIS()
                self.model.write(ILP_FILE_PATH)
            elif self.model.status == GRB.INF_OR_UNBD:
                self.model.setParam('DualReductions', 0)
                self.model.optimize()
                if self.model.status == GRB.INFEASIBLE:
                    self.model.computeIIS()
                    self.model.write(ILP_FILE_PATH)
            else:
                self.objective = self.model.ObjVal
                self.model.write(SOL_FILE_PATH)
                self.extract_results()
            LOGGER.info("Time elapsed: %.2f seconds" % (time.time() - START_TIME))
        else:
            LOGGER.info("Model is too large for Gurobipy free licence, switching to CPLEX")
            self.use_pulp = True
            self.pulp_var, self.pulp_model = LpProblem.fromMPS(MPS_FILE_PATH)
            self.pulp_solver = pl.CPLEX_CMD(options=['mipdisplay=0'])
            self.pulp_model.solve(self.pulp_solver)
            if self.pulp_model.status == 1:
                self.extract_pulp_variables()
                self.extract_results()
            LOGGER.info("Time elapsed: %.2f seconds" % (time.time() - START_TIME))

    # --------------------------------------------------- PuLP variable extraction
    def extract_pulp_variables(self) -> None:
        prob = self.pulp_model
        self.arc_flow_keys = {}
        self.co2_captured_keys = {}
        self.co2_injected_keys = {}
        self.arc_built_keys = {}
        self.src_opened_keys = {}
        self.sink_opened_keys = {}

        for v in prob.variables():
            m = re.match(r'^(\w+)\[(.+)\]', v.name)
            if not m:
                continue
            vtype = m.group(1)
            parts = m.group(2).split(',')

            if vtype == 'arc_flow' and len(parts) == 4:
                key = (parts[0], parts[1], int(parts[2]), int(parts[3]))
                self.arc_flow_keys[key] = v.varValue
            elif vtype == 'CO2_captured' and len(parts) == 2:
                key = (parts[0], int(parts[1]))
                self.co2_captured_keys[key] = v.varValue
            elif vtype == 'CO2_injected' and len(parts) == 2:
                key = (parts[0], int(parts[1]))
                self.co2_injected_keys[key] = v.varValue
            elif vtype == 'arc_built' and len(parts) == 3:
                key = (parts[0], parts[1], int(parts[2]))
                self.arc_built_keys[key] = v.varValue
            elif vtype == 'src_opened':
                self.src_opened_keys[parts[0]] = v.varValue
            elif vtype == 'sink_opened':
                self.sink_opened_keys[parts[0]] = v.varValue

        with open(SOL_FILE_PATH, "w") as f:
            f.write("# Solution for model CO2_network_optimization \n")
            f.write(f"# Objective value = {value(prob.objective)} \n")
            for key in self.arc_flow_keys.keys():
                f.write(f"arc_flow[{key[0]},{key[1]},{key[2]},{key[3]}] {self.arc_flow_keys[key]} \n")
            for key in self.co2_captured_keys.keys():
                f.write(f"CO2_captured[{key[0]},{key[1]}] {self.co2_captured_keys[key]} \n")
            for key in self.co2_injected_keys.keys():
                f.write(f"CO2_injected[{key[0]},{key[1]}] {self.co2_injected_keys[key]} \n")
            for key in self.arc_built_keys.keys():
                f.write(f"arc_built[{key[0]},{key[1]},{key[2]}] {int(self.arc_built_keys[key])} \n")
            for key in self.src_opened_keys.keys():
                f.write(f"src_opened[{key}] {int(self.src_opened_keys[key])} \n")
            for key in self.sink_opened_keys.keys():
                f.write(f"sink_opened[{key}] {int(self.sink_opened_keys[key])} \n")

    # ------------------------------------------------ Gurobi result extraction
    def extract_soln_arcs(self) -> None:
        self.soln_arcs_t = {}
        agg = {}
        for key in self.vars['arc_flow']:
            val = self.vars['arc_flow'][key].X
            if val > 1e-6:
                self.soln_arcs_t[key] = val
                arc_key = (key[0], key[1])
                agg[arc_key] = agg.get(arc_key, 0.0) + val
        self.soln_arcs_a = {k: v / self.T for k, v in agg.items()}
        assert len(self.soln_arcs_a) > 0, "No solution arcs found -- model may be infeasible"

    def extract_activated_source(self) -> None:
        self.soln_sources_t = {}
        agg = {}
        for key in self.vars['CO2_captured']:
            val = self.vars['CO2_captured'][key].X
            if val > 1e-6:
                self.soln_sources_t[key] = val
                agg[key[0]] = agg.get(key[0], 0.0) + val
        self.soln_sources = {k: v / self.T for k, v in agg.items()}

    def extract_activated_sinks(self) -> None:
        self.soln_sinks_t = {}
        agg = {}
        for key in self.vars['CO2_injected']:
            val = self.vars['CO2_injected'][key].X
            if val > 1e-6:
                self.soln_sinks_t[key] = val
                agg[key[0]] = agg.get(key[0], 0.0) + val
        self.soln_sinks = agg

    def extract_costs(self) -> None:
        self.soln_cap_costs = {}
        for src in self.soln_sources.keys():
            total_captured = sum(self.soln_sources_t.get((src, t), 0)
                                 for t in self.periods)
            self.soln_cap_costs[src] = (self.capture_fixed_cost[src]
                                        + self.capture_v_cost[src] * total_captured)

        self.soln_storage_costs = {}
        for sink in self.soln_sinks.keys():
            total_injected = self.soln_sinks[sink]
            self.soln_storage_costs[sink] = (self.storage_fixed_cost[sink]
                                             + self.storage_v_cost[sink] * total_injected)

        self.soln_transport_costs = {}
        for arc_key, flow in self.soln_arcs_t.items():
            n1, n2, c, t = arc_key
            tf = (self.costTrend["Slope"][c] * flow) * self.arc_cost[(n1, n2)] * self.crf
            agg_key = (n1, n2)
            self.soln_transport_costs[agg_key] = self.soln_transport_costs.get(agg_key, 0.0) + tf

        for key in self.vars['arc_built']:
            if self.vars['arc_built'][key].X > 0.5:
                n1, n2, c = key
                tb = ((self.costTrend["Intercept"][c] * 1.0)
                      * self.arc_cost[(n1, n2)] * self.crf * self.T)
                agg_key = (n1, n2)
                self.soln_transport_costs[agg_key] = self.soln_transport_costs.get(agg_key, 0.0) + tb

        self.soln_transport_costs_a = self.soln_transport_costs

    # ------------------------------------------------ PuLP result extraction
    def extract_soln_arcs_p(self) -> None:
        self.soln_arcs_t = {}
        agg = {}
        for arc, val in self.arc_flow_keys.items():
            if val > 1e-6:
                self.soln_arcs_t[arc] = val
                arc_key = (arc[0], arc[1])
                agg[arc_key] = agg.get(arc_key, 0.0) + val
        self.soln_arcs_a = {k: v / self.T for k, v in agg.items()}
        assert len(self.soln_arcs_a) > 0, "No solution arcs found -- model may be infeasible"

    def extract_activated_source_p(self) -> None:
        self.soln_sources_t = {}
        agg = {}
        for key, val in self.co2_captured_keys.items():
            if val > 1e-6:
                self.soln_sources_t[key] = val
                agg[key[0]] = agg.get(key[0], 0.0) + val
        self.soln_sources = {k: v / self.T for k, v in agg.items()}

    def extract_activated_sinks_p(self) -> None:
        self.soln_sinks_t = {}
        agg = {}
        for key, val in self.co2_injected_keys.items():
            if val > 1e-6:
                self.soln_sinks_t[key] = val
                agg[key[0]] = agg.get(key[0], 0.0) + val
        self.soln_sinks = agg

    def extract_costs_p(self) -> None:
        self.soln_cap_costs = {}
        for src in self.soln_sources.keys():
            total_captured = sum(self.soln_sources_t.get((src, t), 0)
                                 for t in self.periods)
            self.soln_cap_costs[src] = (self.capture_fixed_cost[src]
                                        + self.capture_v_cost[src] * total_captured)

        self.soln_storage_costs = {}
        for sink in self.soln_sinks.keys():
            total_injected = self.soln_sinks[sink]
            self.soln_storage_costs[sink] = (self.storage_fixed_cost[sink]
                                             + self.storage_v_cost[sink] * total_injected)

        self.soln_transport_costs = {}
        for arc_key, flow in self.soln_arcs_t.items():
            n1, n2, c, t = arc_key
            tf = (self.costTrend["Slope"][c] * flow) * self.arc_cost[(n1, n2)] * self.crf
            agg_key = (n1, n2)
            self.soln_transport_costs[agg_key] = self.soln_transport_costs.get(agg_key, 0.0) + tf

        for key, val in self.arc_built_keys.items():
            if val > 0.5:
                n1, n2, c = key
                tb = ((self.costTrend["Intercept"][c] * 1.0)
                      * self.arc_cost[(n1, n2)] * self.crf * self.T)
                agg_key = (n1, n2)
                self.soln_transport_costs[agg_key] = self.soln_transport_costs.get(agg_key, 0.0) + tb

        self.soln_transport_costs_a = self.soln_transport_costs

    # ------------------------------------------------ result routing
    def extract_results(self) -> None:
        if self.use_pulp:
            self.extract_soln_arcs_p()
            self.extract_activated_source_p()
            self.extract_activated_sinks_p()
            self.extract_costs_p()
        else:
            self.extract_soln_arcs()
            self.extract_activated_source()
            self.extract_activated_sinks()
            self.extract_costs()

    # ------------------------------------------------ public result getters
    def get_all_soln_results(self):
        return (self.soln_arcs_a, self.soln_sources, self.soln_sinks,
                self.soln_cap_costs, self.soln_storage_costs, self.soln_transport_costs_a)

    def get_all_soln_results_multiperiod(self):
        return (self.soln_arcs_a, self.soln_sources, self.soln_sinks,
                self.soln_cap_costs, self.soln_storage_costs, self.soln_transport_costs_a,
                self.soln_arcs_t, self.soln_sources_t, self.soln_sinks_t)
