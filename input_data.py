import numpy as np
import pandas as pd


class InputData:
    def __init__(self, filename) -> None:
        self.filename = filename

    
    def _read_data(self) -> None:
        self.source_df = pd.read_excel(self.filename, sheet_name='sources')
        self.sink_df = pd.read_excel(self.filename, sheet_name='sinks')

        #make missing values zero
        self.source_df.fillna(0, inplace=True)
        self.sink_df.fillna(0, inplace=True)


    def _preprocess_sources(self) -> None:
        #extract elements
        self.sourceID = list([f'source_{id}' for id in self.source_df['ID']])
        self.sourceName = list(self.source_df['UNIQUE NAME'].values)
        
        self.source_cap = list(self.source_df['Capture Capacity (MTCO2/yr)'].values)
        self.source_total_cost = list(self.source_df['Total Unit Cost ($/tCO2)'].values)
        self.source_fixed_cost = list(self.source_df['Fixed Cost ($M)'].values)
        self.source_var_cost = list(self.source_df['Operating Cost ($/tCO2)'].values)
        self.sourceX = list(self.source_df['X loc'].values)
        self.sourceY = list(self.source_df['Y loc'].values)
        self.sourceLat = list(self.source_df['Lat'].values)
        self.sourceLon = list(self.source_df['Lon'].values)

        #dictionaries
        self.sourceID_Name = dict(zip(self.sourceID, self.sourceName))
        self.sourceID_cap = dict(zip(self.sourceID, self.source_cap))
        self.sourceID_TC = dict(zip(self.sourceID, self.source_total_cost))
        self.sourceID_FC = dict(zip(self.sourceID, self.source_fixed_cost))
        self.sourceID_VC = dict(zip(self.sourceID, self.source_var_cost))
        self.sourceID_X = dict(zip(self.sourceID, self.sourceX))
        self.sourceID_Y = dict(zip(self.sourceID, self.sourceY))
        self.sourceID_Lat = dict(zip(self.sourceID, self.sourceLat))
        self.sourceID_Lon = dict(zip(self.sourceID, self.sourceLon))

        #get input for candidateNetwork Model
        self.sourceCandidate = [(id, self.sourceID_Lat[id], self.sourceID_Lon[id], self.sourceID_cap[id])
                                    for id in self.sourceID]
        
        #get input costs for Math_model
        self.sourceCosts = {id:[self.sourceID_TC[id],
                                self.sourceID_FC[id],
                                self.sourceID_VC[id]]
                            for id in self.sourceID}

    
    def _preprocess_sinks(self) -> None:
        #extract elemets
        self.sinkID = list([f'sink_{id}' for id in self.sink_df['ID']])
        self.sinkName = list(self.sink_df['UNIQUE NAME'].values)
        
        self.sink_cap = list(self.sink_df['Storage Capacity (MTCO2)'].values)
        self.sink_total_cost = list(self.sink_df['Total Unit Cost ($/tCO2)'].values)
        self.sink_fixed_cost = list(self.sink_df['Fixed Cost ($M)'].values)
        self.sink_var_cost = list(self.sink_df['Operating Cost ($/tCO2)'].values)
        self.sinkX = list(self.sink_df['X loc'].values)
        self.sinkY = list(self.sink_df['Y loc'].values)
        self.sinkLat = list(self.sink_df['Lat'].values)
        self.sinkLon = list(self.sink_df['Lon'].values)

        #dictionaries
        self.sinkID_Name = dict(zip(self.sinkID, self.sinkName))
        self.sinkID_cap = dict(zip(self.sinkID, self.sink_cap))
        self.sinkID_TC = dict(zip(self.sinkID, self.sink_total_cost))
        self.sinkID_FC = dict(zip(self.sinkID, self.sink_fixed_cost))
        self.sinkID_VC = dict(zip(self.sinkID, self.sink_var_cost))
        self.sinkID_X = dict(zip(self.sinkID, self.sinkX))
        self.sinkID_Y = dict(zip(self.sinkID, self.sinkY))
        self.sinkID_Lat = dict(zip(self.sinkID, self.sinkLat))
        self.sinkID_Lon = dict(zip(self.sinkID, self.sinkLon))

        #get input for candidateNetwork Model
        self.sinkCandidate = [(id, self.sinkID_Lat[id], self.sinkID_Lon[id], self.sinkID_cap[id])
                                    for id in self.sinkID]
        
        #get input costs for Math_model
        self.sinkCosts = {id:[self.sinkID_TC[id],
                                self.sinkID_FC[id],
                                self.sinkID_VC[id]]
                            for id in self.sinkID}

    
    def process_data(self):
        self._preprocess_sources()
        self._preprocess_sinks()

        self.nodeCosts = {**self.sourceCosts, **self.sinkCosts}

        return self.sourceCandidate, self.sinkCandidate, self.nodeCosts

    
    def get_ID_Names(self):
        return self.sourceID_Name, self.sinkID_Name




if __name__ == '__main__':
    data = InputData('TestInput2.xlsx')
    data._read_data()
    source, sink, costs = data.process_data()

    print(source)
    print(sink)
    print(costs)    

    