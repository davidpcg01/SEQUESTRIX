import pandas as pd
import numpy as np
import gurobipy as gp
from candidateNetwork import candidateNetwork


class Math_model:
    def __init__(self, nodes, nodesValue, arcs, arcsInfo, duration) -> None:
        self.nodes = nodes
        self.arcs = arcs
        self.b = {key:(value*duration if value > 0 else value) for key, value in nodesValue.items()}
        self.cost = {key:arcsInfo[key][0] for key in arcsInfo.keys()}
        self.lower = {key:value[1]*duration for key, value in arcsInfo.items()}
        self.upper = {key:(value[2]*duration if arcsInfo[key][2] < 1e9 else value[2]) for key,value in arcsInfo.items()}
    

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
