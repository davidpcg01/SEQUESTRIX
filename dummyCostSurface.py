#!/usr/bin/env python
# coding: utf-8

# In[16]:


import random
import numpy as np
import csv

class dummyCostSurface:
    def __init__(self, n, lowcost=1, highcost=2, ctype='int'):
        self.n = n
        self.ctype = ctype
        self.lowcost = lowcost
        self.highcost = highcost
        self.vertices = []
        self.edges = []
        self.edgesDict = {}
        self.neighbors = {}
        self.ebunch = []
        
    
    def initialize_vertices(self):
        for i in range(1, ((self.n+1)**2)+1):
            self.vertices.append(i)
    
    def initialize_edges(self):
        n = self.n
        edges = []
        for v in self.vertices:
            if v%(n+1) == 0:
                if v/(n+1) == 1:
                    edges.append([v, v-1])
                    edges.append([v, v+n])
                    edges.append([v, v+n+1])
                elif (v/(n+1)) == (n+1):
                    edges.append([v, v-1])
                    edges.append([v, v-(n+1)])
                    edges.append([v, v-n-2])
                else:
                    edges.append([v, v-n-2])
                    edges.append([v, v-(n+1)])
                    edges.append([v, v-1])
                    edges.append([v, v+n])
                    edges.append([v, v+n+1])
            elif (v-1)%(n+1) == 0:
                if v-1 == 0:
                    edges.append([v, v+1])
                    edges.append([v, v+n+1])
                    edges.append([v, v+n+2])
                elif ((n+1)**2) - v == n:
                    edges.append([v, v-(n+1)])
                    edges.append([v, v-n])
                    edges.append([v, v+1])
                else:
                    edges.append([v, v-(n+1)])
                    edges.append([v, v-n])
                    edges.append([v, v+1])
                    edges.append([v, v+n+1])
                    edges.append([v, v+n+2])
            elif v-(n+1) < 0:
                edges.append([v, v-1])
                edges.append([v, v+1])
                edges.append([v, v+n])
                edges.append([v, v+n+1])
                edges.append([v, v+n+2])
            elif v+(n+1) > ((n+1)**2):
                edges.append([v, v-n-2])
                edges.append([v, v-(n+1)])
                edges.append([v, v-n])
                edges.append([v, v-1])
                edges.append([v, v+1])
            else:
                edges.append([v, v-n-2])
                edges.append([v, v-(n+1)])
                edges.append([v, v-n])
                edges.append([v, v-1])
                edges.append([v, v+1])
                edges.append([v, v+n+1])
                edges.append([v, v+n])
                edges.append([v, v+n+2])
        
        self.edges = edges.copy()
        
    def initialize_neighbors(self):
        for edge in self.edges:
            if edge[0] in self.neighbors:
                self.neighbors[edge[0]].append(edge[1])
            else:
                self.neighbors[edge[0]] = [edge[1]]
        
    def assign_random_cost(self):
        for edge in self.edges:
            if self.ctype == "int":
                cost = random.randint(self.lowcost, self.highcost)
            else:
                cost = round(random.uniform(self.lowcost, self.highcost),2)
            if ((edge[0], edge[1]) not in self.edgesDict) and ((edge[1], edge[0]) not in self.edgesDict):
                self.edgesDict[(edge[0], edge[1])] = cost
                self.edgesDict[(edge[1], edge[0])] = cost
    
        keys = list(self.edgesDict.keys())
        keys.sort()
        self.edgesDict = {i: self.edgesDict[i] for i in keys}
        
        
    def generate_ebunch(self):
        result = []
        for key in self.edgesDict.keys():
            result.append((key[0], key[1], {'weight': self.edgesDict[key]}))
            
        self.ebunch = result.copy()
        
    def generate_cost_surface(self):
        self.initialize_vertices()
        self.initialize_edges()
        self.initialize_neighbors()
        self.assign_random_cost()
        self.generate_ebunch()
    
    def get_edgesDict(self):
        return self.edgesDict
    
    def get_vertices(self):
        return self.vertices
    
    def get_ebunch(self):
        return self.ebunch
    
    def writeGraphToCsv(self, name):
        with open(name+'.csv', 'w', encoding='UTF8', newline='') as f:
            writer = csv.writer(f)

            for _ in self.neighbors.keys():
                writer.writerow([_] + self.neighbors[_])
                cost = [0]
                for n in self.neighbors[_]:
                    cost.append(self.edgesDict[(_,n)])
                writer.writerow(cost)
    
    
                
if __name__ == '__main__':
    C = dummyCostSurface(4, ctype="float")
    C.generate_cost_surface()
    
    print(C.get_vertices())
    print("")
    #print(C.get_edgesDict())
    print(C.get_ebunch())
    
    #C.writeGraphToCsv("newTest")

