from math_model import Math_model
from candidateNetwork import candidateNetwork
import time

start = time.time() #start timer

#Build graph  
g = candidateNetwork(n=100)
g.initialize_dummy_cost_surface()



#Import existing pipeline
g.import_pipeline(input_dir='Existing Pipeline.xlsx', pathname='pipeline1')

#confirm pipeline has been imported
#     print(g.get_existing_zero_cost_path())
#     print(g.get_existing_zero_cost_path_vertices())


#g.print_edges()


#Enter source and sink locations:
#source: (sourceName, X, Y, AnnualCO2Cap)
#sink: (sinkName, X, Y, TotalCO2Cap)
sources = [('source 1', 10, 18, 1), ('source 2', 20, 75, 2), ('source 3', 50, 50, 1)]
sinks = [('sink 1', 80, 35, 20), ('sink 2', 80, 90, 15)]

g.add_sources(sources)
g.add_sinks(sinks)

#Generate Delaunay network
g.generateDelaunayNetwork()

#     #Modify Delaunay network if required and add tiepoints from source to xy of pipeline
#     tiepts = [['source 1', [30, 7], 'sink 1', [66,12], 'pipeline1']]
#     g.add_Delaunay_tiepoints(tiepts)

#show Delaunay network
# g.showDelaunayNetwork()

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
# g.show_candidate_network()
# g.plot_extracted_graph()
# g.print_candidate_shortest_paths()


#     g.get_pipe_trans_nodes()

# g._print_assetNameFromPT()

nodes, arcs, costs, paths, b = g.export_network()

# print(nodes)
# print(" ")
# # print(arcs)
# print(" ")
# print(costs)
# print(" ")
# # print(paths)
# print(" ")
# print(b)

nodesCost = {'source 1': 20, 'source 2': 15, 'source 3': 18, 'sink 1': -31, 'sink 2': -31}

#initialize network model
model = Math_model(nodes, b, arcs, costs, nodesCost, 10)
model.build_model()
model._print_sets()
model._print_parameters()

end = time.time() #end timer

#show time elapse
print("Total Time Elapsed: ", end - start)
print("")
