from math_model import Math_model
from candidateNetwork import candidateNetwork
from input_data import InputData
import time

start = time.time() #start timer

#Build graph  
g = candidateNetwork(width=100, height=100)
g.initialize_dummy_cost_surface()



#Import existing pipeline
g.import_pipeline(input_dir='Existing Pipeline.xlsx', pathname='pipeline1')

#Import source and sink info
data = InputData('TestInput.xlsx')
data._read_data()
sources, sinks, nodesCost = data.process_data()

# print(nodesCost)

#Note
#source: (sourceName, X, Y, AnnualCO2Cap in MTCO2/yr)
#sink: (sinkName, X, Y, TotalCO2Cap in MTCO2)
g.add_sources(sources)
g.add_sinks(sinks)

#Generate Delaunay network
g.generateDelaunayNetwork()

#     #Modify Delaunay network if required and add tiepoints from source to xy of pipeline
#     tiepts = [['source 1', [30, 7], 'sink 1', [66,12], 'pipeline1']]
#     g.add_Delaunay_tiepoints(tiepts)

#show Delaunay network
g.showDelaunayNetwork()

# #enforce pipeline tie in points
# pipetiept1 = (30, 7)
# pipetiept2 = (66, 12)
# g.enforce_pipeline_tie_point('pipeline1', pipetiept1, pipetiept2, exclusion=False, etype='before')

#enforce no diagonal crossover for existing pipelines
g.enforce_no_pipeline_diagonal_Xover()

#Genrate abd show candidate network
g.get_all_source_sink_shortest_paths()
g.get_trans_nodes()
g.trans_node_post_process()
g.get_pipe_trans_nodes()
g.pipe_post_process()
g.shortest_paths_post_process()
g.show_candidate_network()
# g.plot_extracted_graph()
# g.print_candidate_shortest_paths()

#Get Data for network optimization
nodes, arcs, costs, paths, b = g.export_network()


#set project parameters
duration = 10 #yrs
target_cap = 40 #MTCO2

print(costs)

#initialize network model
model = Math_model(nodes, b, arcs, costs, paths, nodesCost, duration, target_cap)
model.build_model()
model.solve_model()
soln_arcs = model.get_soln_arcs()

g.show_solution_network(soln_arcs)

end = time.time() #end timer

#show time elapse
print("Total Time Elapsed: ", end - start)
print("")
