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
        self.edgesWDict = {}
        self.edgesLDict = {}
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
            if ((edge[0], edge[1]) not in self.edgesWDict) and ((edge[1], edge[0]) not in self.edgesWDict):
                self.edgesWDict[(edge[0], edge[1])] = cost
                self.edgesWDict[(edge[1], edge[0])] = cost
    
        keys = list(self.edgesWDict.keys())
        keys.sort()
        self.edgesWDict = {i: self.edgesWDict[i] for i in keys}
        
    def assign_length(self):
        for edge in self.edges:
            length = 1 #TODO: make the length fixed for adjacent moves and sqrt(2)*l for diagonal moves
            if ((edge[0], edge[1]) not in self.edgesLDict) and ((edge[1], edge[0]) not in self.edgesLDict):
                self.edgesLDict[(edge[0], edge[1])] = length
                self.edgesLDict[(edge[1], edge[0])] = length

        keys = list(self.edgesLDict.keys())
        keys.sort()
        self.edgesLDict = {i: self.edgesLDict[i] for i in keys}

        
    def generate_ebunch(self):
        result = []
        for key in self.edgesWDict.keys():
            result.append((key[0], key[1], {'weight': self.edgesWDict[key], 'length': self.edgesLDict[key]}))
            
        self.ebunch = result.copy()
        
    def generate_cost_surface(self):
        self.initialize_vertices()
        self.initialize_edges()
        self.initialize_neighbors()
        self.assign_random_cost()
        self.assign_length()
        self.generate_ebunch()
    
    def get_edgesWDict(self):
        return self.edgesWDict
    
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
                    cost.append(self.edgesWDict[(_,n)])
                writer.writerow(cost)
    
    
                
if __name__ == '__main__':
    C = dummyCostSurface(4, ctype="float")
    C.generate_cost_surface()
    
    print(C.get_vertices())
    print("")
    #print(C.get_edgesWDict())
    print(C.get_ebunch())
    
    #C.writeGraphToCsv("newTest")

