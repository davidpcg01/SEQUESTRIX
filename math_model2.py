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
        #TODO: calculate transport cost per tCO2 for each arc depending on size
        

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
        self.max_arc_cap = {key:self.arcsInfo[key][4] for key in self.a_a}
        self.min_arc_cap = {key:self.arcsInfo[key][3] for key in self.a_a}
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
        LOGGER.info(f'Total source capacity (MTCO2/yr): {total_max_arc_flow}')
        
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
        index = ((node1, node2) for (node1, node2) in self.a_a)
        self.vars['arc_flow'] = self.model.addVars(index, name='arc_flow', lb=0, vtype=GRB.CONTINUOUS)

        #amount of CO2 captured at source (tCO2/yr)
        index = (src for src in self.src)
        self.vars['CO2_captured'] = self.model.addVars(index, name='CO2_captured', lb=0, vtype=GRB.CONTINUOUS)

        #amount of CO2 stored at sink (tCO2/yr)
        index = (sink for sink in self.sink)
        self.vars['CO2_injected'] = self.model.addVars(index, name='CO2_injected', lb=0, vtype=GRB.CONTINUOUS)

        #indicator for if pipeline arc connecting node 1 to 2 is built
        index = ((node1, node2) for (node1, node2) in self.a_a)
        self.vars['arc_built'] = self.model.addVars(index, name='arc_built', vtype=GRB.BINARY)

        #indicator is source is opened
        index = (src for src in self.src)
        self.vars['src_opened'] = self.model.addVars(index, name='src_opened', vtype=GRB.BINARY)

        #indicator is sink is opened
        index = (sink for sink in self.sink)
        self.vars['sink_opened'] = self.model.addVars(index, name='sink_opened', vtype=GRB.BINARY)

        # #arc build cost
        # index = ((node1, node2) for (node1, node2) in self.a_a)
        # self.vars['arc_build_cost'] = self.model.addVars(index, name='arc_build_cost', lb=0, vtype=GRB.CONTINUOUS)

        # #arc use cost
        # index = ((node1, node2) for (node1, node2) in self.a_a)
        # self.vars['arc_use_cost'] = self.model.addVars(index, name='arc_use_cost', lb=0, vtype=GRB.CONTINUOUS)



    def _initialize_gurobi(self) -> None:
        self.env = gp.Env(empty=True)
        self.env.start()
        self.model = gp.Model("CO2_network_optimization", env=self.env)


    def _arc_upper_lower_bound_cons(self) -> None:
        cons_name = 'arc_lower_bound'
        constr = ((self.min_arc_cap[node1, node2] * 1e6) * self.vars['arc_built'][node1, node2] #conversion min cap from MTCO2/yr to tCO2/yr 
                    <= self.vars['arc_flow'][node1, node2] 
                    for (node1, node2) in self.a_a)
        self.cons[cons_name] = self.model.addConstrs(constr, name=cons_name)

        cons_name = 'arc_upper_bound'
        constr = ((self.max_arc_cap[node1, node2] * 1e6) * self.vars['arc_built'][node1, node2] #conversion max cap from MTCO2/yr to tCO2/yr 
                    >= self.vars['arc_flow'][node1, node2]  
                    for (node1, node2) in self.a_a)
        self.cons[cons_name] = self.model.addConstrs(constr, name=cons_name)


    def _single_direction_arc_flow_cons(self) -> None:
        cons_name = 'arc_single_dir_flow'
        constr = (self.vars['arc_built'][node1, node2] 
                    + self.vars['arc_built'][node2, node1] <= 1
                    for (node1, node2) in self.two_way_arcs)
        self.cons[cons_name] =  self.model.addConstrs(constr, name=cons_name)


    def _node_balance_cons(self) -> None:
        asset_to_node = {n:[a for a in self.asset
                            if (a,n) in self.a_a]
                        for n in self.node}
        node_to_asset = {n:[a for a in self.asset
                            if (n,a) in self.a_a]
                        for n in self.node}

        cons_name = 'node_balance'
        constr = (sum(self.vars['arc_flow'][a,n] for a in asset_to_node[n])
                    == sum(self.vars['arc_flow'][n,a] for a in node_to_asset[n])
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
        constr = (sum(self.vars['arc_flow'][a,d] for a in asset_to_demand[d])*self.duration / 1e6 #convert tCO2/yr to MTCO2
                    - sum(self.vars['arc_flow'][d,a] for a in demand_to_asset[d])*self.duration / 1e6
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
        constr = (sum(self.vars['arc_flow'][a,s] for a in asset_to_supply[s]) / 1e6 #convert tCO2/yr to MTCO2/yr
                    - sum(self.vars['arc_flow'][s,a] for a in supply_to_asset[s]) / 1e6
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



    # def _calculate_build_cost_cons(self) -> None: #in $M/km
    #     cons_name = 'calc_arc_build_cost'
    #     constr = (self.vars['arc_build_cost'][node1, node2] >= self.vars['arc_built'][node1, node2] * 0.431655132
    #                 for (node1, node2) in self.a_a)
    #     self.cons[cons_name] = self.model.addConstrs(constr, name=cons_name)

    # def _additional_build_cost(self) -> None:
    #     cons_name = 'extra_arc_build_cost'
    #     constr = (self.vars['arc_build_cost'][node1, node2] <=  0.431655132
    #                 for (node1, node2) in self.a_a)
    #     self.cons[cons_name] = self.model.addConstrs(constr, name=cons_name)

    # def _calculate_use_cost_cons(self) -> None: #in $M/km
    #     cons_name = 'calc_arc_use_cost'
    #     constr = ((0.11571952 * self.vars['arc_flow'][node1, node2] * 1e-6) == self.vars['arc_use_cost'][node1, node2]
    #                 for (node1, node2) in self.a_a)
    #     self.cons[cons_name] = self.model.addConstrs(constr, name=cons_name)



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
        # self._calculate_build_cost_cons()
        # msg = ("'Build Cost calculation' constraint: Time elapsed: %.2f seconds"
        #        % (time.time() - START_TIME))
        # print(msg)
        # LOGGER.info(msg)
        # self._additional_build_cost()
        # msg = ("'Build Cost calculation extra' constraint: Time elapsed: %.2f seconds"
        #        % (time.time() - START_TIME))
        # print(msg)
        # LOGGER.info(msg)
        # self._calculate_use_cost_cons()
        # msg = ("'Pipeline Use Cost calculation' constraint: Time elapsed: %.2f seconds"
        #        % (time.time() - START_TIME))
        # print(msg)
        # LOGGER.info(msg)



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
        
        # transport_flow_cost = sum(self.vars['arc_use_cost'][node1, node2] *  self.arc_cost[node1, node2] * self.crf 
        #                                 for (node1, node2) in self.a_a) # $M * {0, 1} = $M
        
        transport_flow_cost = sum(0.11571952 * self.vars['arc_flow'][node1, node2] * 1e-6 *  self.arc_cost[node1, node2] * self.crf 
                                        for (node1, node2) in self.a_a) # $M * {0, 1} = $M

        # pipeline_build_cost = sum(self.vars['arc_build_cost'][node1, node2] *  self.arc_cost[node1, node2] * self.crf 
        #                                 for (node1, node2) in self.a_a) # $M * {0, 1} = $M
        
        pipeline_build_cost = sum(self.vars['arc_built'][node1, node2] * 0.431655132 *  self.arc_cost[node1, node2] * self.crf 
                                        for (node1, node2) in self.a_a) # $M * {0, 1} = $M

        obj =  capture_cost + storage_cost + transport_flow_cost + pipeline_build_cost
        # obj =  capture_cost + storage_cost


        self.model.setObjective(obj, GRB.MINIMIZE)
        self.model.update()

    def solve_model(self) -> None:
        LOGGER.info('Evauating "minimum cost" objective function')
        self.create_objective()
        LOGGER.info('Objective function "mimumum cost" evaluated')
        
        #set numrerical focus to 2
        # self.model.setParam('NumericFocus', 2)
        #output lp and mps files
        self.model.write('CO2_network_optimization.lp')
        self.model.write('CO2_network_optimization.mps')
        
        #solve model
        self.model.optimize()
        LOGGER.info(f'Model Status: {self.model.status}')
        if self.model.status == GRB.INFEASIBLE:
            self.model.computeIIS()
            self.model.write('CO2_network_optimization.ilp')
        elif self.model.status == GRB.INF_OR_UNBD:
            self.model.setParam('DualReductions', 0)
            self.model.optimize()
            if self.model.status == GRB.INFEASIBLE:
                self.model.computeIIS()
                self.model.write('CO2_network_optimization.ilp')
        else:
            self.objective = self.model.ObjVal

            #write solution
            self.model.write('CO2_network_optimization.sol')
            self.extract_results()
        LOGGER.info("Time elapsed: %.2f seconds" % (time.time() - START_TIME))

    
    def extract_soln_arcs(self) -> None:
        self.soln_arcs = {}
        for arc in self.vars['arc_flow']:
            if self.vars['arc_flow'][arc].X > 0.001:
                self.soln_arcs[arc] = self.vars['arc_flow'][arc].X

    def extract_activated_source(self) -> None:
        self.soln_sources = {}
        for src in self.vars['CO2_captured']:
            if self.vars['CO2_captured'][src].X > 0.0001:
                self.soln_sources[src] = self.vars['CO2_captured'][src].X

    def extract_activated_sinks(self) -> None:
        self.soln_sinks = {}
        for sink in self.vars['CO2_injected']:
            if self.vars['CO2_injected'][sink].X > 0.0001:
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
            tf_cost = 0.11571952 * self.vars['arc_flow'][arc].X * 1e-6 *  self.arc_cost[arc] * self.crf 
            tb_cost = self.vars['arc_built'][arc].x * 0.431655132 *  self.arc_cost[arc] * self.crf 
            t_cost = tf_cost + tb_cost
            self.soln_transport_costs[arc] = t_cost
     
    def extract_results(self) -> None:
        self.extract_soln_arcs()
        self.extract_activated_source()
        self.extract_activated_sinks()
        self.extract_costs()

    def get_soln_arcs(self):
        return self.soln_arcs
    
    def get_soln_sources(self):
        return self.soln_sources
    
    def get_soln_sinks(self):
        return self.soln_sinks
    
    def get_soln_cap_costs(self):
        return self.soln_cap_costs
    
    def get_soln_storage_costs(self):
        return self.soln_storage_costs
    
    def get_soln_transport_costs(self):
        return self.soln_transport_costs
    
    def get_all_soln_results(self):
        return self.soln_arcs, self.soln_sources, self.soln_sinks, self.soln_cap_costs, self.soln_storage_costs, self.soln_transport_costs
    


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
