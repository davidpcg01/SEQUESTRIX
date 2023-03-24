import os
import pulp as pl
from pulp import *
from typing import Dict, List, Set
import pandas as pd
import numpy as np
import gurobipy as gp
import logging
import os
from gurobipy import GRB
from alternateNetworkGeo import alternateNetworkGeo
import time
import datetime


MPS_FILE_PATH = os.path.join("Sequestrix/app/solver_files/CO2_network_optimization.mps")
LP_FILE_PATH = os.path.join("Sequestrix/app/solver_files/CO2_network_optimization.lp")
SOL_FILE_PATH = os.path.join("Sequestrix/app/solver_files/CO2_network_optimization.sol")
ILP_FILE_PATH = os.path.join("Sequestrix/app/solver_files/CO2_network_optimization.ilp")

LOGGER = logging.getLogger(__name__)
FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
logging.basicConfig(filename='model_solve.log', filemode='w', level=logging.DEBUG, format=FORMAT)
START_TIME = time.time()

class Math_model:
    def __init__(self, nodes, nodesValue, arcs, arcsInfo, paths, nodesCost, duration, target_cap, crf=0.1) -> None:
        self.nodes = nodes #contains nodenames in format [node1, node2]
        self.arcs = arcs #contains arcs in the format [(node1, node2)]
        self.nodesValue = nodesValue #contains node capacity values in format {node:cap}
        self.arcsInfo = arcsInfo #contains info about arcs in format {(node1, node2): [length, weight, weighted_cost, lowerbound, upperbound]}
        self.paths = paths #contains the list of nodes connected in path for reconstruction
        self.nodesCost = nodesCost #contains capture and storage cost for sources and sinks in data in format {source:cap_cost, sink:storage_cost}
        self.duration = duration #duration of project
        self.target_cap = target_cap  #amount of C02 you want to be stored in tCO2/yr. note input will be given as MTCO2/yr
        self.crf = crf


        self._initialize_sets()
        self._initialize_source_parameters()
        self._initialize_sink_parameters()
        self._initialize_arcs_parameters()
        self._initialize_pipeline_parameters()

        self.vars: Dict[str, gp.tupledict] = {}
        self.cons: Dict[str, gp.tupledict] = {}

        self.Big_M = 56.46 #max flow allowed in a pipeline tCO2/yr
        self.LTrend = 6.86 #upperbound flow for lower pipeline trend tCO2/yr

        self.costTrend = {"Slope": [0.1157192, 0.0783067],
                          "Intercept": [0.4316551, 0.770037]} #trends of pipeline cost relating MTCO2/ to $M/yr
        
        self.c = len(self.costTrend["Slope"])
    

    
    
    def _initialize_sets(self) -> None:
        self.asset: Set = set() #all assets
        self.src: Set = set() #all source nodes
        self.sink: Set = set() #all storage nodes
        self.node: Set = set() #all transhipment nodes
        self.epipe: Set = set() #all existing pipelines
        self.a_a: Set = set() #all node to node connections
        self.two_way_arcs: Dict = set() #two way arcs, for (a, a') and (a', a) in self.a_a, only take (a, a')


    def _initialize_source_parameters(self) -> None:
        self.source_annual_cap: Dict = {} #amount of CO2 that can be captured at source annually (MtCO2/yr)
        self.capture_cost: Dict = {} #capture cost of CO2 at source in $/tCO2
        self.capture_fixed_cost: Dict = {} #fixed capture cost of CO2 at source in $M
        self.capture_var_cost: Dict = {} #variable capture cost of CO2 at source in $/tCO2

    def _initialize_sink_parameters(self) -> None:
        self.sink_cap: Dict = {} #total amount of CO2 that can be stored at a sink in MTCO2
        self.storage_cost: Dict = {} #storage cost of CO2 at source in $/tCO2
        self.storage_fixed_cost: Dict = {} #fixed capture cost of CO2 at source in $M
        self.storage_var_cost: Dict = {} #variable capture cost of CO2 at source in $/tCO2

    def _initialize_arcs_parameters(self) -> None:
        self.max_arc_cap: Dict = {} #maximum amout of CO2 an arc/or pipeline can transport annually (MtCO2/yr)
        self.min_arc_cap: Dict = {} #minimum amout of CO2 an arc/or pipeline can transport annually (MtCO2/yr)
        self.arc_length: Dict = {} #length of arc/or pipeline in KM
        self.arc_weight: Dict = {} #weight of constructing arc. This corresponds to the terrain
        self.arc_cost: Dict = {} #weighted cost of constructing arc (this is the build cost)
        

    def _initialize_pipeline_parameters(self) -> None:
        self.pipe_nodes: Dict = {}
    
    def _generate_sets(self) -> None:
        self.asset = set(self.nodes)
        self.src = set([node for node in self.nodes if 'source' in node])
        self.sink = set([node for node in self.nodes if 'sink' in node])
        self.node = set([node for node in self.nodes if ((node not in self.src) and (node not in self.sink))])
        self.epipe = set([node.split("_")[0] for node in self.nodes if ("_" in node) and ('source' not in node) and ('sink' not in node)])
        self.a_a = set(self.arcs)
        
        #extract 2 way arcs
        seen = {}
        result = []

        for (a, b) in self.a_a:
            if (a, b) not in seen:
                seen[(a,b)] = True
                if (b, a) in seen:
                    result.append((b,a))

        self.two_way_arcs = set(result)

    def _generate_parameters(self) -> None:
        #source parameters
        self.source_annual_cap = {key:self.nodesValue[key] for key in self.src}
        self.capture_cost = {key:self.nodesCost[key][0] for key in self.src}
        self.capture_fixed_cost = {key:self.nodesCost[key][1] for key in self.src}
        self.capture_var_cost = {key:self.nodesCost[key][2] for key in self.src}

        self.capture_v_cost = {key:self.capture_cost[key] if (self.capture_var_cost[key] == 0)
                                and (self.capture_fixed_cost[key] == 0)
                                else self.capture_var_cost[key] for key in self.src}

        #sink parameters
        self.sink_cap = {key:self.nodesValue[key] for key in self.sink}
        self.storage_cost = {key:self.nodesCost[key][0] for key in self.sink}
        self.storage_fixed_cost = {key:self.nodesCost[key][1] for key in self.sink}
        self.storage_var_cost = {key:self.nodesCost[key][2] for key in self.sink}

        self.storage_v_cost = {key:self.storage_cost[key] if (self.storage_var_cost[key] == 0) 
                                and (self.storage_fixed_cost[key] == 0)
                                else self.storage_var_cost[key] for key in self.sink}

        #arc parameters
        self.MaxCap = sum(self.source_annual_cap.values()) #maximum possible flow
        self.MidCap = ((self.costTrend["Intercept"][1] - self.costTrend["Intercept"][0]) / (self.costTrend["Slope"][0] - self.costTrend["Slope"][1]))


        # self.max_arc_cap = {key:self.arcsInfo[key][4] for key in self.a_a}
        self.max_arc_cap = {(akey[0], akey[1], ckey):self.arcsInfo[akey][4] if self.arcsInfo[akey][4] < self.MidCap else self.MidCap if ckey == 0 else self.MaxCap 
                            for akey in self.a_a for ckey in range(self.c)}

        # self.min_arc_cap = {key:self.arcsInfo[key][3] for key in self.a_a}
        self.min_arc_cap = {(akey[0], akey[1], ckey):self.arcsInfo[akey][3] if self.arcsInfo[akey][3] > 0 else 0
                            for akey in self.a_a for ckey in range(self.c)}
        self.arc_length = {key:self.arcsInfo[key][0] for key in self.a_a} 
        self.arc_weight = {key:self.arcsInfo[key][1] for key in self.a_a} 
        self.arc_cost = {key:self.arcsInfo[key][2] for key in self.a_a}
        

        #pipeline parameters
        self.pipe_nodes = {key:[pipenode for pipenode in self.node if key in pipenode] for key in self.epipe}

    def _validation_checks(self) -> None:
        #if target cap greater than total source cap, then set target cap to source cap
        total_source_cap = sum(self.source_annual_cap.values()) #MTCO2/yr
        total_sink_cap = -sum(self.sink_cap.values()) / self.duration #MTCO2/yr
        total_max_arc_flow = sum(self.max_arc_cap.values()) #MTCO2/yr
        
        # print(total_source_cap, total_sink_cap, total_max_arc_flow)
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
    
    
    def create_variables(self) -> None:
        #flow from node 1 to node 2 in network (tCO2/yr)
        index = ((node1, node2, c) for (node1, node2) in self.a_a for c in range(self.c))
        self.vars['arc_flow'] = self.model.addVars(index, name='arc_flow', lb=0, vtype=GRB.CONTINUOUS)

        #amount of CO2 captured at source (tCO2/yr)
        index = (src for src in self.src)
        self.vars['CO2_captured'] = self.model.addVars(index, name='CO2_captured', lb=0, vtype=GRB.CONTINUOUS)

        #amount of CO2 stored at sink (tCO2/yr)
        index = (sink for sink in self.sink)
        self.vars['CO2_injected'] = self.model.addVars(index, name='CO2_injected', lb=0, vtype=GRB.CONTINUOUS)

        #indicator for if pipeline arc connecting node 1 to 2 is built
        index = ((node1, node2, c) for (node1, node2) in self.a_a for c in range(self.c))
        self.vars['arc_built'] = self.model.addVars(index, name='arc_built', vtype=GRB.BINARY)

        #indicator is source is opened
        index = (src for src in self.src)
        self.vars['src_opened'] = self.model.addVars(index, name='src_opened', vtype=GRB.BINARY)

        #indicator is sink is opened
        index = (sink for sink in self.sink)
        self.vars['sink_opened'] = self.model.addVars(index, name='sink_opened', vtype=GRB.BINARY)



    def _initialize_gurobi(self) -> None:
        self.env = gp.Env(empty=True)
        self.env.start()
        self.model = gp.Model("CO2_network_optimization", env=self.env)


    def _arc_upper_lower_bound_cons(self) -> None:
        cons_name = 'arc_lower_bound'
        constr = ((self.min_arc_cap[node1, node2, c]) * self.vars['arc_built'][node1, node2, c] #conversion min cap from MTCO2/yr to tCO2/yr 
                    <= self.vars['arc_flow'][node1, node2, c] 
                    for (node1, node2) in self.a_a
                    for c in range(self.c))
        self.cons[cons_name] = self.model.addConstrs(constr, name=cons_name)

        cons_name = 'arc_upper_bound'
        constr = ((self.max_arc_cap[node1, node2, c]) * self.vars['arc_built'][node1, node2, c] #conversion max cap from MTCO2/yr to tCO2/yr 
                    >= self.vars['arc_flow'][node1, node2, c]  
                    for (node1, node2) in self.a_a
                    for c in range(self.c))
        self.cons[cons_name] = self.model.addConstrs(constr, name=cons_name)


    def _single_direction_arc_flow_cons(self) -> None:
        cons_name = 'arc_single_dir_flow'
        constr = (sum(self.vars['arc_built'][node1, node2, c] for c in range(self.c)) <= 1
                  for (node1, node2) in self.a_a)
        self.cons[cons_name] =  self.model.addConstrs(constr, name=cons_name)


    def _node_balance_cons(self) -> None:
        asset_to_node = {n:[a for a in self.asset
                            if (a,n) in self.a_a]
                        for n in self.node}
        node_to_asset = {n:[a for a in self.asset
                            if (n,a) in self.a_a]
                        for n in self.node}

        cons_name = 'node_balance'
        constr = (sum(self.vars['arc_flow'][a,n,c1] for a in asset_to_node[n] for c1 in range(self.c))
                    == sum(self.vars['arc_flow'][n,a,c2] for a in node_to_asset[n] for c2 in range(self.c))
                    for n in self.node)
        self.cons[cons_name] = self.model.addConstrs(constr, name=cons_name)
        
    
    def _demand_balance_cons(self) -> None:
        asset_to_demand = {d:[a for a in self.asset
                            if (a,d) in self.a_a]
                        for d in self.sink}
        demand_to_asset = {d:[a for a in self.asset
                            if (d,a) in self.a_a]
                        for d in self.sink}

        cons_name = 'demand_balance'
        constr = (sum(self.vars['arc_flow'][a,d,c1] for a in asset_to_demand[d] for c1 in range(self.c))*self.duration  #convert tCO2/yr to MTCO2
                    - sum(self.vars['arc_flow'][d,a,c2] for a in demand_to_asset[d] for c2 in range(self.c))*self.duration 
                    == self.vars['CO2_injected'][d] #MTCO2
                    for d in self.sink)
        self.cons[cons_name] = self.model.addConstrs(constr, name=cons_name)
    

    def _supply_balance_cons(self) -> None:
        asset_to_supply = {s:[a for a in self.asset
                            if (a,s) in self.a_a]
                        for s in self.src}
        supply_to_asset = {s:[a for a in self.asset
                            if (s,a) in self.a_a]
                        for s in self.src}

        cons_name = 'supply_balance'
        constr = (sum(self.vars['arc_flow'][a,s,c1] for a in asset_to_supply[s] for c1 in range(self.c))  #convert tCO2/yr to MTCO2/yr
                    - sum(self.vars['arc_flow'][s,a,c2] for a in supply_to_asset[s] for c2 in range(self.c)) 
                    == -self.vars['CO2_captured'][s] #MTCO2/yr
                    for s in self.src)
        self.cons[cons_name] = self.model.addConstrs(constr, name=cons_name)


    def _capture_limit_cons(self) -> None:
        cons_name = 'capture_limit'
        constr = (self.vars['CO2_captured'][s] #MTCO2/yr
                    <= self.source_annual_cap[s] * self.vars['src_opened'][s] 
                    for s in self.src)
        self.cons[cons_name] = self.model.addConstrs(constr, name=cons_name)

    
    def _storage_limit_cons(self) -> None:
        cons_name = 'storage_limit'
        constr = (self.vars['CO2_injected'][d] 
                    <= -self.sink_cap[d] * self.vars['sink_opened'][d] #1e6 converts MTCO2 to tCO2
                    for d in self.sink)
        self.cons[cons_name] = self.model.addConstrs(constr, name=cons_name)


    def _capture_target_cons(self) -> None:
        cons_name = 'CO2_capture_target'
        constr = (sum(self.vars['CO2_captured'][s] for s in self.src)
                    >= self.target_cap)
        self.cons[cons_name] = self.model.addConstr(constr, name=cons_name)






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
        msg = ("'Supply Balance' constraint: Time elapsed: %.2f seconds"
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


    def create_objective(self) -> None:
        #capture cost + transport flow cost + arc build cost + storage cost
        capture_cost = sum((self.capture_fixed_cost[s] * self.vars['src_opened'][s]) + # $M * {0,1} = $M
                            (self.capture_v_cost[s] * self.vars['CO2_captured'][s] * self.duration) for s in self.src) # $/tCO2 * MTCO2/yr * yr = $M
        
        storage_cost = sum((self.storage_fixed_cost[d] * self.vars['sink_opened'][d]) + # $M * {0,1} = $M
                            (self.storage_v_cost[d] * self.vars['CO2_injected'][d]) for d in self.sink) # $/tCO2 * MTCO2 = $M
        

        transport_flow_cost = sum((self.costTrend["Slope"][c] * self.vars['arc_flow'][node1, node2, c]) 
                                  *  self.arc_cost[node1, node2] * self.crf * self.duration
                                        for (node1, node2) in self.a_a
                                        for c in range(self.c)) # $M * {0, 1} = $M



        pipeline_build_cost = sum((self.costTrend["Intercept"][c] * self.vars['arc_built'][node1, node2, c]) 
                                  *  self.arc_cost[node1, node2] * self.crf * self.duration
                                        for (node1, node2) in self.a_a
                                        for c in range(self.c)) # $M * {0, 1} = $M

        obj =  capture_cost + storage_cost + transport_flow_cost + pipeline_build_cost
  


        self.model.setObjective(obj, GRB.MINIMIZE)
        self.model.update()

    def solve_model(self) -> None:
        LOGGER.info('Evauating "minimum cost" objective function')
        self.create_objective()
        LOGGER.info('Objective function "mimumum cost" evaluated')
        self.use_pulp = False
        
        #set numrerical focus to 2
        # self.model.setParam('NumericFocus', 2)
        #output lp and mps files
        self.model.write(LP_FILE_PATH)
        self.model.write(MPS_FILE_PATH)
        
        if (self.model.NumVars <= 2000) and (self.model.NumConstrs <= 2000):
            #solve model
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

                #write solution
                self.model.write(SOL_FILE_PATH)
                self.extract_results()
            LOGGER.info("Time elapsed: %.2f seconds" % (time.time() - START_TIME))
        else:
            LOGGER.info("Model is too large for Gurobipy free licence, switching to CPLEX")
            self.use_pulp=True
            self.pulp_var, self.pulp_model = LpProblem.fromMPS(MPS_FILE_PATH)
            self.pulp_solver = pl.CPLEX_CMD(options=['mipdisplay=0'])
            self.pulp_model.solve(self.pulp_solver)
            if self.pulp_model.status == 1:
                #write soln
                self.extract_pulp_variables()
                self.extract_results()
            LOGGER.info("Time elapsed: %.2f seconds" % (time.time() - START_TIME))
                

    def extract_pulp_variables(self) -> None:
        prob1 = self.pulp_model
        arc_flow_keys = {}
        co2_captured_keys = {}
        co2_injected_keys = {}
        arc_built_keys = {}
        src_opened_keys = {}
        sink_opened_keys = {}

        for v in prob1.variables():
            if "arc_flow" in v.name:
                key1 = v.name.split(",")[0][9:]
                key2 = v.name.split(",")[1]
                key3 = int(v.name.split(",")[2].split("_")[0])
                arc_flow_keys[(key1, key2, key3)] = v.varValue
            if "CO2_captured" in v.name:
                key = v.name.split("_")[2] + "_" + v.name.split("_")[3]
                co2_captured_keys[key] = v.varValue
            if "CO2_injected" in v.name:
                key = v.name.split("_")[2] + "_" + v.name.split("_")[3]
                co2_injected_keys[key] = v.varValue
            if "arc_built" in v.name:
                key1 = v.name.split(",")[0][10:]
                key2 = v.name.split(",")[1]
                key3 = int(v.name.split(",")[2].split("_")[0])
                arc_built_keys[(key1, key2, key3)] = v.varValue
            if "src_opened" in v.name:
                key = v.name.split("_")[2] + "_" + v.name.split("_")[3]
                src_opened_keys[key] = v.varValue
            if "sink_opened" in v.name:
                key = v.name.split("_")[2] + "_" + v.name.split("_")[3]
                sink_opened_keys[key] = v.varValue

        # Write the solution to a .sol file
        with open(SOL_FILE_PATH, "w") as f:
            f.write("# Solution for model CO2_network_optimization \n")
            f.write(f"# Objective value = {value(prob1.objective)} \n")
            for key in arc_flow_keys.keys():
                f.write(f"arc_flow[{key[0]},{key[1]},{key[2]}] {arc_flow_keys[key]} \n")
            for key in co2_captured_keys.keys():
                f.write(f"CO2_captured[{key}] {co2_captured_keys[key]} \n")
            for key in co2_injected_keys.keys():
                f.write(f"CO2_injected[{key}] {co2_injected_keys[key]} \n")
            for key in arc_built_keys.keys():
                f.write(f"arc_built[{key[0]},{key[1]},{key[2]}] {int(arc_built_keys[key])} \n")
            for key in src_opened_keys.keys():
                f.write(f"src_opened[{key}] {int(src_opened_keys[key])} \n")
            for key in sink_opened_keys.keys():
                f.write(f"sink_opened[{key}] {int(sink_opened_keys[key])} \n")

        self.arc_flow_keys = arc_flow_keys
        self.co2_captured_keys = co2_captured_keys
        self.co2_injected_keys = co2_injected_keys
        self.arc_built_keys = arc_built_keys
        self.src_opened_keys = src_opened_keys
        self.sink_opened_keys = sink_opened_keys

        

    
    def extract_soln_arcs(self) -> None:
        self.soln_arcs = {}
        for arc in self.vars['arc_flow']:
            if self.vars['arc_flow'][arc].X > 0:
                self.soln_arcs[arc] = self.vars['arc_flow'][arc].X
        
        self.soln_arcs_a = {(arc[0], arc[1]):self.soln_arcs[arc] for arc in self.soln_arcs.keys()}

    def extract_activated_source(self) -> None:
        self.soln_sources = {}
        for src in self.vars['CO2_captured']:
            if self.vars['CO2_captured'][src].X > 0:
                self.soln_sources[src] = self.vars['CO2_captured'][src].X

    def extract_activated_sinks(self) -> None:
        self.soln_sinks = {}
        for sink in self.vars['CO2_injected']:
            if self.vars['CO2_injected'][sink].X > 0:
                self.soln_sinks[sink] = self.vars['CO2_injected'][sink].X

    def extract_costs(self) -> None:
        self.soln_cap_costs = {} #$M
        self.soln_storage_costs = {} #$M
        self.soln_transport_costs = {}
        
        for src in self.soln_sources.keys():
            c_cost = (self.capture_fixed_cost[src] + (self.capture_v_cost[src] * self.soln_sources[src] * self.duration)) 
            self.soln_cap_costs[src] = c_cost
        
        for sink in self.soln_sinks.keys():
            s_cost = self.storage_fixed_cost[sink] + (self.storage_v_cost[sink] * self.soln_sinks[sink])
            self.soln_storage_costs[sink] = s_cost
        
        for arc in self.soln_arcs.keys():
            print("arc: ", arc)
            print("slope: ", self.costTrend["Slope"][arc[2]])
            print("intercept: ", self.costTrend["Intercept"][arc[2]])
            print("flow: ", self.vars['arc_flow'][arc].x)
            print("built: ", self.vars['arc_built'][arc].x)
            print("weight: ", self.arc_cost[(arc[0], arc[1])])
            print("crf: ", self.crf)
            print("duration: ", self.duration)
            

            tf_cost = (self.costTrend["Slope"][arc[2]] * self.vars['arc_flow'][arc].x) *  self.arc_cost[(arc[0], arc[1])] * self.crf * self.duration
            tb_cost = (self.costTrend["Intercept"][arc[2]] * self.vars['arc_built'][arc].x) *  self.arc_cost[(arc[0], arc[1])] * self.crf * self.duration

            t_cost = tf_cost + tb_cost

            print("transfer: ", tf_cost)
            print("build: ", tb_cost)
            print("total: ", t_cost)
            print("")

            self.soln_transport_costs[arc] = t_cost

            self.soln_transport_costs_a = {(arc[0], arc[1]):self.soln_transport_costs[arc] for arc in self.soln_transport_costs.keys()}


    def extract_soln_arcs_p(self) -> None:
        self.soln_arcs = {}
        for arc in self.arc_flow_keys.keys():
            if self.arc_flow_keys[arc] > 0:
                self.soln_arcs[arc] = self.arc_flow_keys[arc]
        
        self.soln_arcs_a = {(arc[0], arc[1]):self.soln_arcs[arc] for arc in self.soln_arcs.keys()}
    
    def extract_activated_source_p(self) -> None:
        self.soln_sources = {}
        for src in self.co2_captured_keys.keys():
            if self.co2_captured_keys[src] > 0:
                self.soln_sources[src] = self.co2_captured_keys[src]

    def extract_activated_sinks_p(self) -> None:
        self.soln_sinks = {}
        for sink in self.co2_injected_keys.keys():
            if self.co2_injected_keys[sink] > 0:
                self.soln_sinks[sink] = self.co2_injected_keys[sink]
    

    def extract_costs_p(self) -> None:
        self.soln_cap_costs = {} #$M
        self.soln_storage_costs = {} #$M
        self.soln_transport_costs = {}
        
        for src in self.soln_sources.keys():
            c_cost = (self.capture_fixed_cost[src] + (self.capture_v_cost[src] * self.soln_sources[src] * self.duration)) 
            self.soln_cap_costs[src] = c_cost
        
        for sink in self.soln_sinks.keys():
            s_cost = self.storage_fixed_cost[sink] + (self.storage_v_cost[sink] * self.soln_sinks[sink])
            self.soln_storage_costs[sink] = s_cost
        
        for arc in self.soln_arcs.keys():
            print("arc: ", arc)
            print("slope: ", self.costTrend["Slope"][arc[2]])
            print("intercept: ", self.costTrend["Intercept"][arc[2]])
            print("flow: ", self.arc_flow_keys[arc])
            print("built: ", self.arc_built_keys[arc])
            print("weight: ", self.arc_cost[(arc[0], arc[1])])
            print("crf: ", self.crf)
            print("duration: ", self.duration)
            tf_cost = (self.costTrend["Slope"][arc[2]] * self.arc_flow_keys[arc]) *  self.arc_cost[(arc[0], arc[1])] * self.crf * self.duration
            tb_cost = (self.costTrend["Intercept"][arc[2]] * self.arc_built_keys[arc]) *  self.arc_cost[(arc[0], arc[1])] * self.crf * self.duration

            t_cost = tf_cost + tb_cost
            
            print("transfer: ", tf_cost)
            print("build: ", tb_cost)
            print("total: ", t_cost)
            print("")

            self.soln_transport_costs[arc] = t_cost

            self.soln_transport_costs_a = {(arc[0], arc[1]):self.soln_transport_costs[arc] for arc in self.soln_transport_costs.keys()}

    

     
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

    def get_soln_arcs(self):
        return self.soln_arcs_a
    
    def get_soln_sources(self):
        return self.soln_sources
    
    def get_soln_sinks(self):
        return self.soln_sinks
    
    def get_soln_cap_costs(self):
        return self.soln_cap_costs
    
    def get_soln_storage_costs(self):
        return self.soln_storage_costs
    
    def get_soln_transport_costs(self):
        return self.soln_transport_costs_a
    
    def get_all_soln_results(self):
        return self.soln_arcs_a, self.soln_sources, self.soln_sinks, self.soln_cap_costs, self.soln_storage_costs, self.soln_transport_costs_a
    


    def _print_sets(self) -> None:
        print("Printing Sets...".upper())
        print(self.asset)
        print(" ")
        print(self.src)
        print(" ")
        print(self.sink)
        print(" ")
        print(self.node)
        print(" ")
        print(self.epipe)
        print(" ")
        print(self.a_a)
        print(" ")

    def _print_parameters(self) -> None:
        print("Printing parameters".upper())
        print(self.source_annual_cap)
        print(" ")
        print(self.capture_cost)
        print(" ")
        print(self.sink_cap)
        print(" ")
        print(self.storage_cost)
        print(" ")
        print(self.max_arc_cap)
        print(" ")
        print(self.min_arc_cap)
        print(" ")
        print(self.arc_length)
        print(" ")
        print(self.arc_weight)
        print(" ")
        print(self.arc_cost)
        print(" ")
        print(self.pipe_nodes)
        print(" ")

    
    def _print_init(self) -> None:
        print(self.nodes)
        print(" ")
        print(self.arcs)
        print(" ")
        print(self.b)
        print(" ")
        print(self.cost)
        print(" ")
        print(self.lower)
        print(" ")
        print(self.upper)


if __name__ == '__main__':

        pass
