import sys
from pathlib import Path

ROOT_PATH = Path(__file__).parent.parent.parent.resolve()
SRC_PATH = ROOT_PATH.joinpath("src")
sys.path.insert(1, str(SRC_PATH))


import streamlit as st
import plotly.express as px
import pandas as pd
import numpy as np
import time
import os
import csv
from math_model import Math_model
from math_model_multiperiod import Math_model_multiperiod
from networkDelanunay import networkDelanunay
from alternateNetworkGeo import alternateNetworkGeo
from input_data import InputData
from typing import Dict
import scenario_manager


st.set_page_config(page_title="Solve", page_icon="⚙️", layout="wide")

INPUT_FILES_PATH = os.path.join("Sequestrix/app/input_files/Input_File.xlsx")
PIPELINE_FILE_PATH = os.path.join("Sequestrix/app/pipeline_files/Pipeline_File.xlsx")
OUTPUT_FILE_PATH = os.path.join("Sequestrix/app/output_files/solution_file")


keys_to_track = ["solveButton", "p3_fig1", "p3_fig2", "p3_fig3", "dur", "target", "crf", "solved", "showAlt",
                  "multiperiod", "num_periods", "target_mode", "mp_solved", "mp_sources_t", "mp_sinks_t", "mp_arcs_t"]

for key in keys_to_track:
    if key not in st.session_state:
        st.session_state[key] = None

if st.session_state.mp_solved is None:
    st.session_state.mp_solved = False



def writeSoln(dur: int, target: float, crf: float, soln_arcs : Dict, soln_sources: Dict, soln_sinks: Dict, 
              soln_cap_costs: Dict, soln_storage_costs: Dict, soln_transport_costs: Dict, pipeResult, data, costs, filename=OUTPUT_FILE_PATH):
    total_captured = sum(soln_sources.values())
    total_stored = sum(soln_sinks.values())
    total_capture_cost = sum(soln_cap_costs.values())
    total_storage_cost = sum(soln_storage_costs.values())
    total_transport_cost = sum(soln_transport_costs.values())
    total_cost = total_capture_cost + total_storage_cost + total_transport_cost
    with open(filename+'.csv', 'w', encoding='UTF8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["SEQUESTRIX CO2 NETWORK OPTIMIZATION SOLUTION"])
        writer.writerow(["Project Duration (yrs)", dur])
        writer.writerow(["Captal Recovery Factor (%)", round(crf*100,2)])
        writer.writerow(["Annual Target Capture (MTCO2/yr)", target])
        writer.writerow(["Annual Actual Capture (MTCO2/yr)", total_captured, "If different from Target, there is a limiting constraint - see logs for details"])
        writer.writerow(["Annual Storage Amount (MTCO2/yr)", total_stored/dur])
        writer.writerow(["Total Cost ($M/yr)", total_cost/dur])
        writer.writerow(["Capture Cost ($M/yr)", total_capture_cost/dur])
        writer.writerow(["Transport Cost ($M/yr)", total_transport_cost/dur])
        writer.writerow(["Storage Cost ($M/yr)", total_storage_cost/dur])
        writer.writerow([""])
        writer.writerow(["CO2 CAPTURE SOURCES SOLUTION BREAKDOWN"])
        writer.writerow(["CO2 Source ID", "CO2 Source Name", "Capture Amount (MTCO2/yr)", "Capture Cost ($M/yr)"])
        for src in soln_sources.keys():
            writer.writerow([src, data.get_Name_From_ID(src), soln_sources[src], soln_cap_costs[src]/dur])
        writer.writerow([""])
        writer.writerow(["CO2 STORAGE SINKS SOLUTION BREAKDOWN"])
        writer.writerow(["CO2 Sink ID", "CO2 Sink Name", "Storage Amount (MTCO2/yr)", "Storage Cost ($M/yr)"])
        for sink in soln_sinks.keys():
            writer.writerow([sink, data.get_Name_From_ID(sink), soln_sinks[sink]/dur, soln_storage_costs[sink]/dur])
        writer.writerow([""])
        writer.writerow(["CO2 TRANSPORT PIPELINES SOLUTION BREAKDOWN"])
        writer.writerow(["Start Point", "End Point", "Length (km)", "Weight", "CO2 Transported (MTCO2/yr)", "Transport Cost ($M/yr)"])
        for arc in soln_arcs.keys():
            writer.writerow([arc[0], arc[1], pipeResult[arc]["length"], costs[arc][2], soln_arcs[arc], soln_transport_costs[arc]/dur])
        writer.writerow([""])

start_time = time.time()


with st.sidebar:
    if st.session_state.dur is None:
        duration_input = st.text_input('Enter Sequestration Project Duration Length (yrs)')
    else:
        duration_input = st.text_input('Enter Sequestration Project Duration Length (yrs)', value=st.session_state.dur)

    if st.session_state.target is None:
        target_Cap_input = st.number_input('Enter CO2 Sequestration Target in MTCO2/yr')
    else:
        target_Cap_input = st.number_input('Enter CO2 Sequestration Target in MTCO2/yr', value=st.session_state.target)

    if st.session_state.crf is None:
        crf_input = st.number_input('Enter Capital Recovery Factor as Fraction')
    else:
        crf_input = st.number_input('Enter Capital Recovery Factor as Fraction', value=st.session_state.crf)

    multiperiod = st.checkbox("Enable Multiperiod Planning",
                              value=st.session_state.multiperiod if st.session_state.multiperiod else False)
    if multiperiod:
        num_periods_input = st.number_input(
            "Number of Planning Periods (years)", min_value=1, value=10, step=1)
        target_mode = st.selectbox("Target Mode", ("Cumulative", "Per-Period"))
        st.info("Add 'source_periods', 'sink_periods', 'targets' sheets to input Excel for time-varying data. If absent, uniform capacities are used.")
    else:
        num_periods_input = None
        target_mode = None

    showAlt = st.checkbox("Show Alternate Network on Final Solution", value=st.session_state.showAlt)
    
    solveButton = st.button("Solve Model")


#SESSION STATE PERSISTENCE
if st.session_state.solveButton is None:
    st.session_state.solveButton = solveButton
elif (solveButton) and (solveButton != st.session_state.solveButton):
    st.session_state.solveButton = solveButton

if st.session_state.dur is None:
    st.session_state.dur = duration_input
elif duration_input == "":
    st.session_state.dur = ""
elif (duration_input) and (duration_input != st.session_state.dur):
    st.session_state.dur = duration_input

if st.session_state.target is None:
    st.session_state.target = target_Cap_input
elif (target_Cap_input) and (target_Cap_input != st.session_state.target):
    st.session_state.target = target_Cap_input

if st.session_state.crf is None:
    st.session_state.crf = crf_input
elif (crf_input) and (crf_input != st.session_state.crf):
    st.session_state.crf = crf_input

if st.session_state["showAlt"] is None:
        st.session_state["showAlt"] = showAlt
elif (showAlt is False) and (showAlt != st.session_state.showAlt):
    st.session_state["showAlt"] = showAlt
elif (showAlt is True) and (showAlt != st.session_state.showAlt):
    st.session_state["showAlt"] = showAlt

st.session_state.multiperiod = multiperiod
if multiperiod:
    st.session_state.num_periods = num_periods_input
    st.session_state.target_mode = target_mode


#DEFINE SOLVE FUNCTION WITH CACHE
@st.cache_data
def solveModel(pipe_path, input_path, dur, tar, direction, tiein, point1, point2, exclusion, etype, onlyin, onlyout, showAlt, crf=0.01):
    model_solve_start_time = time.time()
    with st.sidebar:
        if point1[0] == "":
            point1=None
        if point2[0] == "":
            point2=None
        progress_text = "CO2 Network Optimization in progress. Please wait."
        my_bar = st.progress(0, text=progress_text)


        counter = 1
        while counter < 99:
            time.sleep(3.6)
            counter += 5
            my_bar.progress(counter, text=progress_text)


            #Build graph  
            g = alternateNetworkGeo()
            g.initialize_cost_surface()
            
            #update progress bar
            time.sleep(3.6)
            counter += 30
            my_bar.progress(counter, text=progress_text)


            if pipe_path:
                g.import_pipeline_lat_long(input_dir=pipe_path, flowtype=direction)

            if input_path:
                #Import source and sink info
                data = InputData(input_path)
                data._read_data()
                sources, sinks, nodesCost = data.process_data()
                g.add_sources(sources)
                g.add_sinks(sinks)
            
            #update progress bar
            time.sleep(3.6)
            counter += 20
            my_bar.progress(counter, text=progress_text)

            g.generateDelaunayNetwork()
            if tiein:
                g.enforce_pipeline_tie_point(point1=point1, point2=point2, exclusion=exclusion, etype=etype, onlyin=onlyin, onlyout=onlyout)
            g.enforce_no_pipeline_diagonal_Xover()
            g.get_all_source_sink_shortest_paths()
            g.get_pipe_trans_nodes()
            g.get_trans_nodes()
            g.trans_node_post_process()
            g.pipe_post_process()
            g.shortest_paths_post_process()
            g._getMappingData()
            
            #update progress bar
            time.sleep(3.6)
            counter += 20
            my_bar.progress(counter, text=progress_text)

            # global fig1
            # global fig2

            fig1 = g._getDelaunayMapFig()
            fig2 = g._getAlternateNetworkMapFig()

            #Get Data for network optimization
            nodes, arcs, costs, paths, b = g.export_network()

            #set project parameters
            duration = int(dur) #yrs
            target_cap = tar #MTCO2/yr


            #initialize network model
            model = Math_model(nodes, b, arcs, costs, paths, nodesCost, duration, target_cap, crf=crf)
            model.build_model()
            model.solve_model()

            
            #EXTRACT KEY RESULTS
            soln_arcs, soln_sources, soln_sinks, soln_cap_costs, soln_storage_costs, soln_transport_costs = model.get_all_soln_results()
            pipe_result = g._getSolnResults(soln_arcs)


            writeSoln(duration, target_cap, crf_input, soln_arcs, soln_sources, soln_sinks, soln_cap_costs,
                    soln_storage_costs, soln_transport_costs, pipe_result, data=data, costs=costs)


            #extract final plot and update progress bar
            # global fig3
            fig3 = g._getSolnNetworkMapFig(soln_arcs, point1=point1, point2=point2, show_alt=showAlt)    
            time.sleep(3.6)
            counter += 24
            my_bar.progress(counter, text=progress_text)
        
        st.session_state.solved = True
        st.success('Optimization Complete!', icon="✅")
        st.write("Model Solve Time: %.2f seconds" % (time.time() - model_solve_start_time))
    
    return fig1, fig2, fig3


def writeSolnMultiperiod(dur, target, crf, soln_arcs, soln_sources, soln_sinks,
                         soln_cap_costs, soln_storage_costs, soln_transport_costs,
                         pipeResult, data, costs, soln_sources_t, soln_sinks_t,
                         soln_arcs_t, filename=OUTPUT_FILE_PATH):
    writeSoln(dur, target, crf, soln_arcs, soln_sources, soln_sinks,
              soln_cap_costs, soln_storage_costs, soln_transport_costs,
              pipeResult, data, costs, filename)
    with open(filename + '.csv', 'a', encoding='UTF8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["MULTIPERIOD PLANNING MODE"])
        writer.writerow(["Number of Planning Periods", dur])
        writer.writerow([""])
        writer.writerow(["PER-PERIOD CAPTURE BREAKDOWN"])
        writer.writerow(["Period", "CO2 Source ID", "Capture Amount (MTCO2)"])
        for (src, t), val in sorted(soln_sources_t.items(), key=lambda x: (x[0][1], x[0][0])):
            writer.writerow([t, src, val])
        writer.writerow([""])
        writer.writerow(["PER-PERIOD STORAGE BREAKDOWN"])
        writer.writerow(["Period", "CO2 Sink ID", "Storage Amount (MTCO2)"])
        for (sink, t), val in sorted(soln_sinks_t.items(), key=lambda x: (x[0][1], x[0][0])):
            writer.writerow([t, sink, val])
        writer.writerow([""])
        writer.writerow(["PER-PERIOD TRANSPORT BREAKDOWN"])
        writer.writerow(["Period", "Start Point", "End Point", "Trend", "CO2 Transported (MTCO2)"])
        for (n1, n2, c, t), val in sorted(soln_arcs_t.items(), key=lambda x: (x[0][3], x[0][0])):
            writer.writerow([t, n1, n2, c, val])
        writer.writerow([""])


def solveModelMultiperiod(pipe_path, input_path, num_periods, tar, direction,
                          tiein, point1, point2, exclusion, etype, onlyin,
                          onlyout, showAlt, target_mode, crf=0.01):
    model_solve_start_time = time.time()
    with st.sidebar:
        if point1[0] == "":
            point1 = None
        if point2[0] == "":
            point2 = None
        progress_text = "CO2 Network Optimization in progress. Please wait."
        my_bar = st.progress(0, text=progress_text)

        counter = 1
        while counter < 99:
            time.sleep(3.6)
            counter += 5
            my_bar.progress(counter, text=progress_text)

            g = alternateNetworkGeo()
            g.initialize_cost_surface()

            time.sleep(3.6)
            counter += 30
            my_bar.progress(counter, text=progress_text)

            if pipe_path:
                g.import_pipeline_lat_long(input_dir=pipe_path, flowtype=direction)

            if input_path:
                data = InputData(input_path)
                data._read_data()
                sources, sinks, nodesCost = data.process_data_multiperiod()
                source_cap_t = data.source_cap_t
                sink_inject_t = data.sink_inject_t
                target_cap_t_data = data.target_cap_t
                g.add_sources(sources)
                g.add_sinks(sinks)

            time.sleep(3.6)
            counter += 20
            my_bar.progress(counter, text=progress_text)

            g.generateDelaunayNetwork()
            if tiein:
                g.enforce_pipeline_tie_point(point1=point1, point2=point2,
                                             exclusion=exclusion, etype=etype,
                                             onlyin=onlyin, onlyout=onlyout)
            g.enforce_no_pipeline_diagonal_Xover()
            g.get_all_source_sink_shortest_paths()
            g.get_pipe_trans_nodes()
            g.get_trans_nodes()
            g.trans_node_post_process()
            g.pipe_post_process()
            g.shortest_paths_post_process()
            g._getMappingData()

            time.sleep(3.6)
            counter += 20
            my_bar.progress(counter, text=progress_text)

            fig1 = g._getDelaunayMapFig()
            fig2 = g._getAlternateNetworkMapFig()

            nodes, arcs, costs, paths, b = g.export_network()

            target_cap = tar

            # Determine target_cap_t based on target_mode
            if target_mode == "Per-Period":
                if target_cap_t_data:
                    final_target_cap_t = target_cap_t_data
                else:
                    final_target_cap_t = {t: target_cap for t in range(1, num_periods + 1)}
            else:
                final_target_cap_t = None

            model = Math_model_multiperiod(
                nodes, b, arcs, costs, paths, nodesCost,
                num_periods, target_cap,
                source_cap_t=source_cap_t if source_cap_t else None,
                sink_inject_t=sink_inject_t if sink_inject_t else None,
                target_cap_t=final_target_cap_t,
                crf=crf)
            model.build_model()
            model.solve_model()

            soln_arcs, soln_sources, soln_sinks, soln_cap_costs, soln_storage_costs, soln_transport_costs = model.get_all_soln_results()
            (_, _, _, _, _, _,
             soln_arcs_t, soln_sources_t, soln_sinks_t) = model.get_all_soln_results_multiperiod()

            pipe_result = g._getSolnResults(soln_arcs)

            writeSolnMultiperiod(num_periods, target_cap, crf_input, soln_arcs, soln_sources,
                                 soln_sinks, soln_cap_costs, soln_storage_costs,
                                 soln_transport_costs, pipe_result, data=data, costs=costs,
                                 soln_sources_t=soln_sources_t, soln_sinks_t=soln_sinks_t,
                                 soln_arcs_t=soln_arcs_t)

            st.session_state.mp_sources_t = soln_sources_t
            st.session_state.mp_sinks_t = soln_sinks_t
            st.session_state.mp_arcs_t = soln_arcs_t

            fig3 = g._getSolnNetworkMapFig(soln_arcs, point1=point1, point2=point2, show_alt=showAlt)
            time.sleep(3.6)
            counter += 24
            my_bar.progress(counter, text=progress_text)

        st.session_state.solved = True
        st.session_state.mp_solved = True
        st.success('Multiperiod Optimization Complete!', icon="✅")
        st.write("Model Solve Time: %.2f seconds" % (time.time() - model_solve_start_time))

    return fig1, fig2, fig3


# st.session_state

tab1, tab2, tab3 = st.tabs(["Delanuay Triangulation △", "Alternate Pipeline Routes ⇎", "Solution Network Map 🗾"])

if solveButton:
    st.session_state.solved = False
    if st.session_state.multiperiod:
        fig1, fig2, fig3 = solveModelMultiperiod(
            pipe_path=st.session_state.PIPELINE_FILE, input_path=st.session_state.INPUT_FILE,
            num_periods=st.session_state.num_periods, tar=st.session_state.target, crf=crf_input,
            direction=st.session_state.direction, tiein=st.session_state.tiein,
            point1=st.session_state.point1, point2=st.session_state.point2,
            exclusion=st.session_state.exclusion, etype=st.session_state.etype,
            onlyin=st.session_state.onlyin, onlyout=st.session_state.onlyout,
            showAlt=st.session_state.showAlt, target_mode=st.session_state.target_mode)
    else:
        fig1, fig2, fig3 = solveModel(
            pipe_path=st.session_state.PIPELINE_FILE, input_path=st.session_state.INPUT_FILE,
            dur=st.session_state.dur, tar=st.session_state.target, crf=crf_input,
            direction=st.session_state.direction, tiein=st.session_state.tiein,
            point1=st.session_state.point1, point2=st.session_state.point2,
            exclusion=st.session_state.exclusion, etype=st.session_state.etype,
            onlyin=st.session_state.onlyin, onlyout=st.session_state.onlyout,
            showAlt=st.session_state.showAlt)
        st.session_state.mp_solved = False

    st.session_state.p3_fig1 = fig1
    st.session_state.p3_fig2 = fig2
    st.session_state.p3_fig3 = fig3
    
if st.session_state.solveButton and st.session_state.solved:
    with tab1:
        st.plotly_chart(st.session_state.p3_fig1, use_container_width=True)

    with tab2:
        st.plotly_chart(st.session_state.p3_fig2, use_container_width=True)

    with tab3:
        st.plotly_chart(st.session_state.p3_fig3, use_container_width=True)

    st.divider()
    st.subheader("Save as Scenario")
    scenario_name = st.text_input("Scenario Name", key="save_scenario_name_solve")
    save_btn = st.button("Save Scenario", key="save_scenario_btn_solve")
    if save_btn and scenario_name:
        if scenario_manager.scenario_exists(scenario_name):
            st.warning(f"Scenario '{scenario_name.strip()}' already exists and will be overwritten.")
        metadata = {
            "dur": int(st.session_state.dur) if st.session_state.dur else 0,
            "target": st.session_state.target,
            "crf": st.session_state.crf,
            "multiperiod": bool(st.session_state.multiperiod),
            "num_periods": st.session_state.num_periods,
        }
        ok, msg = scenario_manager.save_scenario(
            scenario_name, OUTPUT_FILE_PATH + '.csv', metadata,
            network_map_fig=st.session_state.p3_fig3)
        if ok:
            st.success(msg)
        else:
            st.error(msg)
    elif save_btn and not scenario_name:
        st.warning("Please enter a scenario name.")

