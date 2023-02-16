from typing import Dict, List, Set
import pandas as pd
import numpy as np
import gurobipy as gp
import logging
import os
from gurobipy import GRB
from candidateNetwork import candidateNetwork
import time
import datetime

LOGGER = logging.getLogger(__name__)
START_TIME = time.time()

class Math_model:
    def __init__(self, nodes, nodesValue, arcs, arcsInfo, nodesCost, duration) -> None:
        self.nodes = nodes #contains nodenames in format [node1, node2]
        self.arcs = arcs #contains arcs in the format [(node1, node2)]
        self.nodesValue = nodesValue #contains node capacity values in format {node:cap}
        self.arcsInfo = arcsInfo #contains info about arcs in format {(node1, node2): [length, weight, weighted_cost, lowerbound, upperbound]}
        self.nodesCost = nodesCost #contains capture and storage cost for sources and sinks in data in format {source:cap_cost, sink:storage_cost}
        self.duration = duration #duration of project
        # self.b = {key:(value*duration if value > 0 else value) for key, value in nodesValue.items()}
        # self.cost = {key:arcsInfo[key][0] for key in arcsInfo.keys()}
        # self.lower = {key:value[1]*duration for key, value in arcsInfo.items()}
        # self.upper = {key:(value[2]*duration if arcsInfo[key][2] < 1e9 else value[2]) for key,value in arcsInfo.items()}


        self._initialize_sets()
        self._initialize_source_parameters()
        self._initialize_sink_parameters()
        self._initialize_arcs_parameters()
        self._initialize_pipeline_parameters()
    

    
    
    def _initialize_sets(self) -> None:
        self.asset: Set = set() #all assets
        self.src: Set = set() #all source nodes
        self.sink: Set = set() #all storage nodes
        self.node: Set = set() #all transhipment nodes
        self.epipe: Set = set() #all existing pipelines
        self.a_a: Set = set() #all node to node connections


    def _initialize_source_parameters(self) -> None:
        self.source_annual_cap: Dict = {} #amount of CO2 that can be captured at source annually (MtCO2/yr)
        self.capture_cost: Dict = {} #capture cost of CO2 at source in $/tCO2

    def _initialize_sink_parameters(self) -> None:
        self.sink_cap: Dict = {} #total amount of CO2 that can be stored at a sink in MTCO2
        self.storage_cost: Dict = {} #storage cost of CO2 at source in $/tCO2

    def _initialize_arcs_parameters(self) -> None:
        self.max_arc_cap: Dict = {} #maximum amout of CO2 an arc/or pipeline can transport annually (MtCO2/yr)
        self.min_arc_Cap: Dict = {} #minimum amout of CO2 an arc/or pipeline can transport annually (MtCO2/yr)
        self.arc_length: Dict = {} #length of arc/or pipeline in KM
        self.arc_weight: Dict = {} #weight of constructing arc. This corresponds to the terrain
        self.arc_cost: Dict = {} #weighted cost of constructing arc

    def _initialize_pipeline_parameters(self) -> None:
        self.pipe_nodes: Dict = {}
    
    def _generate_sets(self) -> None:
        self.asset = set(self.nodes)
        self.src = set([node for node in self.nodes if 'source' in node])
        self.sink = set([node for node in self.nodes if 'sink' in node])
        self.node = set([node for node in self.nodes if ((node not in self.src) and (node not in self.sink))])
        self.epipe = set([node.split("_")[0] for node in self.nodes if "_" in node])
        self.a_a = set(self.arcs)

    def _generate_parameters(self) -> None:
        #source parameters
        self.source_annual_cap = {key:self.nodesValue[key] for key in self.src}
        self.capture_cost = {key:self.nodesCost[key] for key in self.src}

        #sink parameters
        self.sink_cap = {key:self.nodesValue[key] for key in self.sink}
        self.storage_cost = {key:self.nodesCost[key] for key in self.sink}

        #arc parameters
        self.max_arc_cap = {key:self.arcsInfo[key][4] for key in self.a_a}
        self.min_arc_Cap = {key:self.arcsInfo[key][3] for key in self.a_a}
        self.arc_length = {key:self.arcsInfo[key][0] for key in self.a_a} 
        self.arc_weight = {key:self.arcsInfo[key][1] for key in self.a_a} 
        self.arc_cost = {key:self.arcsInfo[key][2] for key in self.a_a}

        #pipeline parameters
        self.pipe_nodes = {key:[pipenode for pipenode in self.node if key in pipenode] for key in self.epipe}
    

    def create_sets_and_parameters(self):
        self._generate_sets()
        self._generate_parameters()
    
    
    def create_variables(self) -> None:
        pass


    def _initialize_gurobi(self) -> None:
        self.env = gp.Env(empty=True)
        self.env.start()
        self.model = gp.Model("co2_network_optimization", env=self.env)

    def create_constraints(self) -> None:
        pass


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
        print(self.min_arc_Cap)
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
