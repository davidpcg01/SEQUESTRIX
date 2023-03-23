import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import csv
import pandas as pd
import numpy as np
import os
import streamlit.components.v1 as components


st.set_page_config(page_title="Results Dashboard", page_icon="📊", layout="wide")

if "solved" not in st.session_state:
        st.session_state["solved"] = False

OUTPUT_FILE_PATH = os.path.join("Sequestrix/app/output_files/solution_file.csv")

def read_result(filename=OUTPUT_FILE_PATH):
    df_capture = {"CO2 Source ID": [], "CO2 Source Name": [], "Capture Amount (MTCO2/yr)": [], "Capture Cost ($M/yr)": []}
    df_storage = {"CO2 Sink ID":[], "CO2 Sink Name":[], "Storage Amount (MTCO2/yr)":[], "Storage Cost ($M/yr)":[]}
    df_transport = {"Start Point":[], "End Point":[], "Length (km)":[], "CO2 Transported (MTCO2/yr)":[], "Transport Cost ($M/yr)":[]}
    global dur
    global target
    global total_cap 
    with open(filename, 'r') as read_obj:
        csv_reader = csv.reader(read_obj)
        next(csv_reader)
        dur = int(next(csv_reader)[1])
        next(csv_reader)
        target = float(next(csv_reader)[1])
        total_cap = float(next(csv_reader)[1])

        curr = next(csv_reader)
        while curr[0] != "CO2 Source ID":
            curr = next(csv_reader)
        
        curr = next(csv_reader)
        while curr[0] != "":
            df_capture["CO2 Source ID"].append(curr[0])
            df_capture["CO2 Source Name"].append(curr[1])
            df_capture["Capture Amount (MTCO2/yr)"].append(float(curr[2]))
            df_capture["Capture Cost ($M/yr)"].append(float(curr[3]))
            curr = next(csv_reader)
        

        while curr[0] != "CO2 Sink ID":
            curr = next(csv_reader)
        
        curr = next(csv_reader)
        while curr[0] != "":
            df_storage["CO2 Sink ID"].append(curr[0])
            df_storage["CO2 Sink Name"].append(curr[1])
            df_storage["Storage Amount (MTCO2/yr)"].append(float(curr[2]))
            df_storage["Storage Cost ($M/yr)"].append(float(curr[3]))
            curr = next(csv_reader)
        
        
        curr = next(csv_reader)
        while curr[0] != "Start Point":
            curr = next(csv_reader)
        
        
        curr = next(csv_reader)
        while curr[0] != "":
            df_transport["Start Point"].append(curr[0])
            df_transport["End Point"].append(curr[1])
            df_transport["Length (km)"].append(float(curr[2]))
            df_transport["CO2 Transported (MTCO2/yr)"].append(float(curr[3]))
            df_transport["Transport Cost ($M/yr)"].append(float(curr[4]))
            curr = next(csv_reader)
        
    
    df_capture = pd.DataFrame(df_capture)
    df_storage = pd.DataFrame(df_storage)
    df_transport = pd.DataFrame(df_transport)

    return df_capture, df_storage, df_transport, dur, target, total_cap       

def ColourWidgetText(wgt_txt, wch_colour = '#000000'):
    htmlstr = """<script>var elements = window.parent.document.querySelectorAll('*'), i;
                    for (i = 0; i < elements.length; ++i) { if (elements[i].innerText == |wgt_txt|) 
                        elements[i].style.color = ' """ + wch_colour + """ '; } </script>  """

    htmlstr = htmlstr.replace('|wgt_txt|', "'" + wgt_txt + "'")
    components.html(f"{htmlstr}", height=0, width=0)


tab1, tab2, tab3, tab4 = st.tabs(["Overview", "Capture", "Storage", "Transport"])
if st.session_state.solved:
    df_capture, df_storage, df_transport, dur, target, total_cap = read_result()
    df_capture["Total CO2 Captured (MTCO2)"] = df_capture["Capture Amount (MTCO2/yr)"] * dur
    df_storage["Total CO2 Stored (MTCO2)"] = df_storage["Storage Amount (MTCO2/yr)"] * dur
    df_transport["Pipeline Arcs"] = df_transport["Start Point"] + ' - ' + df_transport['End Point'] 

    with tab1:
        col1, col2, col3, col4 = st.columns([2,2,2,1])
        col1.metric("Project Duration (yrs)", dur)
        col2.metric("Total CO2 Sequestered (MTCO2)", round(total_cap * dur, 1))
        col3.metric("Number of Sources", f"{len(df_capture)}")
        col4.metric("Number of Sinks", f"{len(df_storage)}")

        st.markdown("#")
        st.markdown("#")

        unit_cap_cost =  sum(df_capture["Capture Cost ($M/yr)"]) / sum(df_capture["Capture Amount (MTCO2/yr)"])
        unit_sto_cost = sum(df_storage["Storage Cost ($M/yr)"]) / sum(df_storage["Storage Amount (MTCO2/yr)"])
        unit_trans_cost = sum(df_transport["Transport Cost ($M/yr)"]) / sum(df_transport["CO2 Transported (MTCO2/yr)"])
        unit_total_cost = unit_sto_cost + unit_trans_cost + unit_cap_cost
        col5, col6, col7 = st.columns([2,1.9,0.7])
        col5.metric("Unit Capture Cost ($/tCO2)", round(unit_cap_cost,2))
        col6.metric("Unit Storage Cost ($/tCO2)", round(unit_sto_cost,2))
        col7.metric("Unit Transport Cost ($/tCO2)", round(unit_trans_cost,2))

        st.markdown("#")
        st.markdown("#")

        col8, col9, col10 = st.columns([2,1.9,0.7])
        col9.metric("Total Unit Cost ($/tCO2)", round(unit_total_cost, 2))

        st.markdown("#")
        st.markdown("#")

        if unit_total_cost <= -5:
            st.markdown("<h2 style='text-align: center; color: green;'>Economic Project ✅ </h2>", unsafe_allow_html=True)
            ColourWidgetText(str(round(unit_total_cost, 2)), 'green')
        
        elif -5 < unit_total_cost < 0:
            st.markdown("<h2 style='text-align: center; color: orange;'> Marginally Economic Project ⚠ </h2>", unsafe_allow_html=True)
            ColourWidgetText(str(round(unit_total_cost, 2)), 'orange')

        else:
            st.markdown("<h2 style='text-align: center; color: red;'> Sub-Economic Project 🛑 </h2>", unsafe_allow_html=True)
            ColourWidgetText(str(round(unit_total_cost, 2)), 'red')


        ColourWidgetText(str(round(total_cap * dur, 1)), 'yellow')
        ColourWidgetText("Project Duration", 'orange')
        ColourWidgetText("Number of Sources", 'red')
        ColourWidgetText("Number of Sinks", 'green')

        

    with tab2:
        fig_col1, fig_col2 = st.columns(2)
        max_val = round(target/5)*5 + 5
        with fig_col1:
            st.markdown(f"#### CO2 Capture Target Vs Actual")
            fig = go.Figure(go.Indicator(
                domain = {'x': [0, 1], 'y': [0, 1]},
                value = total_cap,
                mode = "gauge+number+delta",
                title = {'text': "Annual CO2 Captured (MTCO2/yr)"},
                delta = {'reference': target},
                gauge = {'axis': {'range': [None, max_val]},
                        'steps' : [
                                {'range': [0, 0.3*max_val], 'color':'#FFC0CB'},
                                {'range': [0.3*max_val, 0.7*max_val], 'color':'#FFFFCC'}, 
                                {'range': [0.7*max_val, target], 'color':'#C7EA46'}],
                        'bar': {'color': '#9370DB'},
                        'threshold': {'line': {'color': "red", 'width': 10}, 'thickness': 0.75, 'value': target}}
            ))
            
            st.plotly_chart(fig, use_container_width=True)

        with fig_col2:
            st.markdown("#### Annual Capture Volume (MTCO2/yr)")
            fig2 = px.bar(df_capture.sort_values(by="Capture Amount (MTCO2/yr)", ascending=True), x="CO2 Source ID", y="Capture Amount (MTCO2/yr)", hover_name="CO2 Source Name", 
                          color_discrete_sequence=px.colors.sequential.RdBu)
            st.plotly_chart(fig2, use_container_width=True)
        
        fig_col3, fig_col4 = st.columns(2)
        with fig_col3:
            st.markdown("#### Annual Capture Cost ($M/yr)")
            fig3 = px.bar(df_capture.sort_values(by="Capture Cost ($M/yr)", ascending=True), x="Capture Cost ($M/yr)", y="CO2 Source ID", hover_name="CO2 Source Name",
                           color_discrete_sequence=px.colors.sequential.RdBu, orientation='h')
            st.plotly_chart(fig3, use_container_width=True)
            

        with fig_col4:
            st.markdown(f"#### Total Capture Volume over {dur} yrs: {total_cap} MTCO2")
            fig4 = px.pie(df_capture, values="Total CO2 Captured (MTCO2)", names="CO2 Source ID", hover_name="CO2 Source Name", color_discrete_sequence=px.colors.sequential.RdBu)
            st.plotly_chart(fig4, use_container_width=True)

        with st.expander("See CO2 Capture Results Table"):
                st.dataframe(df_capture)


    with tab3:
        fig_col5, fig_col6 = st.columns(2)
        with fig_col5:
            st.markdown(f"#### Total Storage Volume over {dur} yrs: {round(df_storage['Total CO2 Stored (MTCO2)'].sum(), 2)} MTCO2")
            fig5 = px.pie(df_storage, values="Total CO2 Stored (MTCO2)", names="CO2 Sink ID", hover_name="CO2 Sink Name", color_discrete_sequence=px.colors.sequential.Emrld)
            st.plotly_chart(fig5, use_container_width=True)
            

        with fig_col6:
            st.markdown("#### Annual Storage Volume (MTCO2/yr)")
            fig6 = px.bar(df_storage.sort_values(by="Storage Amount (MTCO2/yr)", ascending=True), x="CO2 Sink ID", y="Storage Amount (MTCO2/yr)", hover_name="CO2 Sink Name", 
                          color_discrete_sequence=px.colors.sequential.Emrld)
            st.plotly_chart(fig6, use_container_width=True)
        
        fig_col7, fig_col8 = st.columns(2)
        with fig_col7:
            st.markdown("#### Annual Storage Cost ($M/yr)")
            fig7 = px.bar(df_storage.sort_values(by="Storage Cost ($M/yr)", ascending=True), x="Storage Cost ($M/yr)", y="CO2 Sink ID", hover_name="CO2 Sink Name", 
                          color_discrete_sequence=px.colors.sequential.Emrld, orientation='h')
            st.plotly_chart(fig7, use_container_width=True)        

        with st.expander("See CO2 Storage Results Table"):
                st.dataframe(df_storage)

    with tab4:
        fig_col9, fig_col10 = st.columns(2)
        with fig_col9:
            fig8 = px.bar(df_transport.sort_values(by="Length (km)", ascending=True), x="Length (km)", y="Pipeline Arcs", color_discrete_sequence=px.colors.sequential.Oryel, orientation='h')
            st.plotly_chart(fig8, use_container_width=True) 

        with fig_col10:
            fig9 = px.bar(df_transport.sort_values(by="CO2 Transported (MTCO2/yr)", ascending=True), x="Pipeline Arcs", y="CO2 Transported (MTCO2/yr)", color="Transport Cost ($M/yr)", 
                        color_continuous_scale=px.colors.sequential.Oryel)
            st.plotly_chart(fig9, use_container_width=True)

        with st.expander("See CO2 Transport Results Table"):
                st.dataframe(df_transport)
        
        


