import pandas as pd
import numpy as np
from csv import reader
import time
from geopy.point import Point
from geopy.distance import distance
from bisect import bisect_left, bisect_right
from pathlib import Path

ROOT_PATH = Path(__file__).parent.parent.resolve()
FILE_PATH = ROOT_PATH.joinpath("Construction Costs.csv")



class geoTransformation:
    def __init__(self) -> None:
        self.costFilePath = FILE_PATH
        self.gridcost = {}
        self.gridCostList = []
        self.gridTranslated = False
        self.north = 40.422261
        self.south = 33.615165
        self.east = -92.284113
        self.west = -103.665777

    def _loadgeogrid(self) -> None:
        with open(self.costFilePath, 'r') as read_obj:
            csv_reader = reader(read_obj)
            i = 0
            while i < 2:
                next(csv_reader)
                i += 1
            self.gridWidth = int(next(csv_reader)[1])
            self.gridHeight = int(next(csv_reader)[1])
            self.lowerLeftX = float(next(csv_reader)[1])
            self.lowerLeftY = float(next(csv_reader)[1])
            self.cellSize = float(next(csv_reader)[1])
            self.noDataValue = next(csv_reader)[1]

            if round(self.cellSize, 5) == 0.00833:
                print("Transforming cellSize")
                self.cellSize = 1
                self.gridTranslated = True
                self.getGridTranslation()
                print("Transformed cellSize and generated grid translation")
            # loop throw remaining cols and add the weights as costs

        self.gridVertices = [i for i in range(1, ((self.gridWidth*self.gridHeight) + 1))]

                
    
    def _loadcost(self):
        # self._initializeCostgrid()
        with open(self.costFilePath, 'r') as read_obj:
            csv_reader = reader(read_obj)
            i = 0
            while i < 8:
                next(csv_reader)
                i += 1
            edgeConn = next(csv_reader)
            while edgeConn != ['']:
                edgeCost = next(csv_reader)
                startnode = int(edgeConn[0])
                for i in range(len(edgeCost)):
                    # if (startnode, int(edgeConn[i+1])) not in self.gridcost:
                        # print(startnode, int(edgeConn[i+1]))
                    key = (startnode, int(edgeConn[i+1]))
                    if self._checkBound(key):
                        self.gridcost[key] =  float(edgeCost[i])
                edgeConn = read_obj.readline().split(",")
                edgeConn[-1] = edgeConn[-1].split("\n")[0]

        # self._generateGridCostList()


        #create list of list to store costs
        #NOTE: each list i represents a cell
        
        # print(self.gridcost)
        # print(self.gridCostList)

    def _loadcostT(self):
        # self._initializeCostgrid()
        with open(self.costFilePath, 'r') as read_obj:
            csv_reader = reader(read_obj)
            i = 0
            while i < 8:
                next(csv_reader)
                i += 1
            edgeConn = next(csv_reader)
            while edgeConn != ['']:
                edgeCost = next(csv_reader)
                startnode = int(edgeConn[0])
                for i in range(len(edgeCost)):
                    # if (startnode, int(edgeConn[i+1])) not in self.gridcost:
                        # print(startnode, int(edgeConn[i+1]))
                    key = (self.gridtranslation[startnode], self.gridtranslation[int(edgeConn[i+1])])
                    if self._checkBound(key):
                        self.gridcost[key] =  float(edgeCost[i])
                edgeConn = read_obj.readline().split(",")
                edgeConn[-1] = edgeConn[-1].split("\n")[0]



    def create_grid(self):
        nrows = self.gridHeight
        ncols = self.gridWidth
        grid = []
        counter = 1
        for row in range(nrows):
            row_list = []
            for col in range(ncols):
                row_list.append(counter)
                counter += 1
            grid.append(row_list)
        return grid
    
    def translate_grid(self):
        nrows = self.gridHeight
        ncols = self.gridWidth
        grid = []
        for row in range(nrows):
            row_list = []
            for col in range(ncols):
                cell_number = (nrows - row) * ncols - col
                row_list.append(cell_number)
            row_list.reverse()
            grid.append(row_list)
        return grid
    
    def getGridTranslation(self):
        nrows = self.gridHeight
        ncols = self.gridWidth
        lrdu = self.create_grid()
        lrud = self.translate_grid()

        result_dict = {}
        for i in range(nrows):
            for j in range(ncols):
                result_dict[lrdu[i][j]] =  lrud[i][j]
        
        self.gridtranslation = result_dict
    

    def _generateGridCostList(self):
        for key in self.gridcost.keys():
            self.gridCostList.append([key[0], key[1], {'weight': self.gridcost[key]}])

    def _getNeighbors(self, cell):
        neighbors = [cell+1, cell-1, cell + self.gridWidth, cell - self.gridWidth, cell + self.gridWidth + 1, 
                    cell + self.gridWidth - 1, cell - self.gridWidth + 1, cell - self.gridWidth - 1]
        for i in range(len(neighbors)):
            if (neighbors[i] < 0) or (neighbors[i] > self.gridHeight * self.gridWidth):
                neighbors[i] = 0
        return neighbors
                
    def _initializeCostgrid(self):
        for i in self.gridVertices:
            neighbors = self._getNeighbors(i)
            for neighbor in neighbors:
                if neighbor != 0:
                    self.gridcost[(i, neighbor)] = 1e6


    def _vicenty(self, distance_km, point_a):
        lat_a = point_a[0]
        lon_a = point_a[1]

        # calculate the distance between two points separated by 1 degree of longitude at point_a's latitude
        lon_degrees_offset = distance(point_a, Point(lat_a, lon_a + 1)).km
        
        # calculate the distance in degrees to travel to move distance_km east
        lon_degrees_to_travel = distance_km / lon_degrees_offset
        
        # calculate the longitude of point_b
        lon_b = lon_a + lon_degrees_to_travel

        # return a Point object for point_b
        return Point(latitude=lat_a, longitude=lon_b)

    def _latlonToCell(self, lat, lon):
        # y = self.gridHeight - int((lat - self.lowerLeftY) / self.cellSize + 1) + 1
        # x = int((lon - self.lowerLeftX) / self.cellSize) + 1
        point_a = Point(self.lowerLeftY, self.lowerLeftX)
        point_b = Point(lat, self.lowerLeftX)
        point_c = Point(lat, lon)
        d1 = distance(point_a, point_b).meters
        y  = round(d1 / (self.cellSize*1000)) + 1
        d2 = distance(point_b, point_c).meters
        x = round(d2 / (self.cellSize*1000)) + 1
        return self._xyToCell(x, y)
    
    def _xyToCell(self, x, y):
        return (y -1) * self.gridWidth + x
    
    def _cellToXY(self, cell):
        y = int((cell - 1) / self.gridWidth + 1)
        x = int(cell - (y - 1) * self.gridWidth)
        return [x,y]

    def _cellToLatLon(self, cell):
        xy = self._cellToXY(cell)
        xy[0] -= 1
        xy[1] -= 1
        d1 =  (self.cellSize * 1000 * xy[1]) -.5
        d2 = (self.cellSize * 1000 * xy[0])  -.5
        point_a = Point(self.lowerLeftY, self.lowerLeftX)
        point_b = distance(kilometers=d1/1000).destination(point_a, bearing=0)
        point_c = self._vicenty(distance_km=d2/1000, point_a=point_b)
        lat = point_c[0]
        lon = point_c[1]
        return lat, lon
        
    
    def _latlonToXY(self, lat, lon):
        # y = self.gridHeight - int((lat - self.lowerLeftY) / self.cellSize + 1) + 1
        # x = int((lon - self.lowerLeftX) / self.cellSize) + 1
        point_a = Point(self.lowerLeftY, self.lowerLeftX)
        point_b = Point(lat, self.lowerLeftX)
        point_c = Point(lat, lon)
        d1 = distance(point_a, point_b).meters
        y  = round(d1 / (self.cellSize*1000)) + 1
        d2 = distance(point_b, point_c).meters
        x = round(d2 / (self.cellSize*1000)) + 1
        return [x,y]
    
    def _xyToLatLon(self, x, y):
        cell = self._xyToCell(x, y)
        return self._cellToLatLon(cell)
    
    def getVertices(self):
        return self.gridVertices
    
    def getEdgesList(self):
        return self.gridCostList
    
    def getEdegsDict(self):
        return self.gridcost
    
    def processGeoCost(self):
        start_time = time.time()
        print("Loading geo grid...")
        self._loadgeogrid()
        print("loaded geogrid. Time Elapsed: %s seconds" %(time.time() - start_time))
        print("")
        print("Subsetting Cost grid...")
        self._subsetGrid()
        print("Subsetting cost grid completed. Time Elapsed: %s seconds" %(time.time() - start_time))
        print("")
        print("Loading cost...")
        if self.gridTranslated == True:
            self._loadcostT()
        else:
            self._loadcost()
        print("loaded cost. Time Elapsed: %s seconds" %(time.time() - start_time))
        print("")
        
        
        # print("Converting cost to graph edges...")
        # self._generateGridCostList()
        # print("Conversion complete. Time Elapsed: %s seconds" %(time.time() - start_time))
        # print("")
    

    def _subsetGrid(self):
        # nrows = self.gridHeight
        ncols = self.gridWidth

        sw = self._latlonToCell(self.south, self.west)
        se = self._latlonToCell(self.south, self.east)
        nw = self._latlonToCell(self.north, self.west)
        ne = self._latlonToCell(self.north, self.east)

        inputdata = [sw, se, nw, ne]



        newWidth = max((inputdata[1] - inputdata[0]), (inputdata[3] - inputdata[2]))+1
        newHeight = max((inputdata[2] - inputdata[0]), (inputdata[3] - inputdata[1]))+ncols

        start = inputdata[0]

        n_nrows = round(newHeight/ncols)
        

        self.leftbounds = []
        self.rightbounds = []
        for i in range(n_nrows):
            start_x = start + (i*ncols)
            self.leftbounds.append(start_x)
            self.rightbounds.append(start_x + newWidth - 1)

        # self.gridsubsetcost = {}
        # for key in self.gridcost.keys():
        #     if self._checkBound(key):
        #         self.gridsubsetcost[key] = self.gridcost[key]

    
    def _checkBound(self, data):
        n = len(self.leftbounds)
        left_idx = bisect_right(self.leftbounds, data[0]) - 1
        right_idx = bisect_left(self.rightbounds, data[1])

        validLeft = (left_idx >= 0 and self.leftbounds[left_idx] <= data[0] <= self.rightbounds[left_idx])
        validRight = (right_idx < n and self.leftbounds[right_idx] <= data[1] <= self.rightbounds[right_idx])

        valid = validLeft and validRight
        return valid

    def getHeight(self):
        return self.gridHeight
    

    def getWidth(self):
        return self.gridWidth
    
    def getCellSize(self):
        return self.cellSize
    
    def getSubsetEdges(self):
        return self.gridsubsetcost
    



if __name__ == "__main__":
    gt = geoTransformation()
    gt.processGeoCost()
    # loc_list = [[10, 18], [20,75], [50,50], [80,35], [80,90]]
    # for pair in loc_list:
    #     lat, lon = gt._xyToLatLon(pair[0],pair[1])
    #     print(lat, lon)
    # cell = gt._latlonToCell(lat, lon)
    print(gt._latlonToXY(37.306068, -97.162054)) #nw
    print(gt._latlonToXY(35.805645, -97.162054)) #sw
    print(gt._latlonToXY(37.306068, -93.379661)) #ne
    print(gt._latlonToXY(35.805645, -93.379661)) #se
    print(gt._xyToLatLon(251, 263))
    # print(gt._cellToXY(205199))
    # print(gt._xyToCell(251,263))
    print(gt._xyToCell(2439,1418))
    print(gt._xyToCell(2487,1252))
    print(gt._xyToCell(2770,1418))
    print(gt._xyToCell(2825,1252))
    # print(cell)
    # print(gt._cellToLatLon(cell))
    # print(gt.getEdgesList())
    