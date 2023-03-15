import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import csv
import pandas as pd
import numpy as np
import os
import streamlit.components.v1 as components


st.set_page_config(page_title="Results Dashboard", page_icon="📊", layout="wide")

OUTPUT_FILE_PATH = os.path.join("Sequestrix/app/output_files/solution_file.csv")





def read_result(filename=OUTPUT_FILE_PATH):
    df_capture = {"CO2 Source": [], "Capture Amount (MTCO2/yr)": [], "Capture Cost ($M/yr)": []}
    df_storage = {"CO2 Sink":[], "Storage Amount (MTCO2/yr)":[], "Storage Cost ($M/yr)":[]}
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
        while curr[0] != "CO2 Source":
            curr = next(csv_reader)
        
        curr = next(csv_reader)
        while curr[0] != "":
            df_capture["CO2 Source"].append(curr[0])
            df_capture["Capture Amount (MTCO2/yr)"].append(float(curr[1]))
            df_capture["Capture Cost ($M/yr)"].append(float(curr[2]))
            curr = next(csv_reader)
        

        while curr[0] != "CO2 Sink":
            curr = next(csv_reader)
        
        curr = next(csv_reader)
        while curr[0] != "":
            df_storage["CO2 Sink"].append(curr[0])
            df_storage["Storage Amount (MTCO2/yr)"].append(float(curr[1]))
            df_storage["Storage Cost ($M/yr)"].append(float(curr[2]))
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

df_capture, df_storage, df_transport, dur, target, total_cap = read_result()
df_capture["Total CO2 Captured (MTCO2)"] = df_capture["Capture Amount (MTCO2/yr)"] * dur
df_storage["Total CO2 Stored (MTCO2)"] = df_storage["Storage Amount (MTCO2/yr)"] * dur
df_transport["Pipeline Arcs"] = df_transport["Start Point"] + ' - ' + df_transport['End Point'] 



def ColourWidgetText(wgt_txt, wch_colour = '#000000'):
    htmlstr = """<script>var elements = window.parent.document.querySelectorAll('*'), i;
                    for (i = 0; i < elements.length; ++i) { if (elements[i].innerText == |wgt_txt|) 
                        elements[i].style.color = ' """ + wch_colour + """ '; } </script>  """

    htmlstr = htmlstr.replace('|wgt_txt|', "'" + wgt_txt + "'")
    components.html(f"{htmlstr}", height=0, width=0)


tab1, tab2, tab3, tab4 = st.tabs(["Overview", "Capture", "Storage", "Transport"])

with tab1:
     col1, col2, col3, col4 = st.columns(4)
     col1.metric("Project Duration", f"{dur} yrs")
     col2.metric("Total CO2 Sequestered", f"{round(total_cap * dur, 1)} MTCO2")
     col3.metric("Number of Sources", f"{len(df_capture)}")
     col4.metric("Number of Sinks", f"{len(df_storage)}")

     ColourWidgetText(f"{round(total_cap * dur, 1)} MTCO2", 'yellow')
     ColourWidgetText("Project Duration", 'orange')
     ColourWidgetText("Number of Sources", 'red')
     ColourWidgetText("Number of Sinks", 'green')

     pass

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
        
        st.write(fig)

    with fig_col2:
        st.markdown("#### Annual Capture Volume (MTCO2/yr)")
        fig2 = px.bar(df_capture.sort_values(by="Capture Amount (MTCO2/yr)", ascending=True), x="CO2 Source", y="Capture Amount (MTCO2/yr)", color_discrete_sequence=px.colors.sequential.RdBu)
        st.write(fig2)
    
    fig_col3, fig_col4 = st.columns(2)
    with fig_col3:
        st.markdown("#### Annual Capture Cost ($M/yr)")
        fig3 = px.bar(df_capture.sort_values(by="Capture Cost ($M/yr)", ascending=True), x="Capture Cost ($M/yr)", y="CO2 Source", color_discrete_sequence=px.colors.sequential.RdBu, orientation='h')
        st.write(fig3)
        

    with fig_col4:
        st.markdown(f"#### Total Capture Volume over {dur} yrs: {total_cap} MTCO2")
        fig4 = px.pie(df_capture, values="Total CO2 Captured (MTCO2)", names="CO2 Source", color_discrete_sequence=px.colors.sequential.RdBu)
        st.write(fig4)

    with st.expander("See CO2 Capture Results Table"):
            st.dataframe(df_capture)


with tab3:
    fig_col5, fig_col6 = st.columns(2)
    with fig_col5:
        st.markdown(f"#### Total Storage Volume over {dur} yrs: {round(df_storage['Total CO2 Stored (MTCO2)'].sum(), 2)} MTCO2")
        fig5 = px.pie(df_storage, values="Total CO2 Stored (MTCO2)", names="CO2 Sink", color_discrete_sequence=px.colors.sequential.Emrld)
        st.write(fig5)
        

    with fig_col6:
        st.markdown("#### Annual Storage Volume (MTCO2/yr)")
        fig6 = px.bar(df_storage.sort_values(by="Storage Amount (MTCO2/yr)", ascending=True), x="CO2 Sink", y="Storage Amount (MTCO2/yr)", color_discrete_sequence=px.colors.sequential.Emrld)
        st.write(fig6)
    
    fig_col7, fig_col8 = st.columns(2)
    with fig_col7:
        st.markdown("#### Annual Storage Cost ($M/yr)")
        fig7 = px.bar(df_storage.sort_values(by="Storage Cost ($M/yr)", ascending=True), x="Storage Cost ($M/yr)", y="CO2 Sink", color_discrete_sequence=px.colors.sequential.Emrld, orientation='h')
        st.write(fig7)        

    with st.expander("See CO2 Storage Results Table"):
            st.dataframe(df_storage)

with tab4:
    fig_col9, fig_col10 = st.columns(2)
    with fig_col9:
        fig8 = px.bar(df_transport.sort_values(by="Length (km)", ascending=True), x="Length (km)", y="Pipeline Arcs", color_discrete_sequence=px.colors.sequential.Oryel, orientation='h')
        st.write(fig8) 

    with fig_col10:
        fig9 = px.bar(df_transport.sort_values(by="CO2 Transported (MTCO2/yr)", ascending=True), x="Pipeline Arcs", y="CO2 Transported (MTCO2/yr)", color="Transport Cost ($M/yr)", 
                       color_continuous_scale=px.colors.sequential.Oryel)
        st.write(fig9)

    with st.expander("See CO2 Transport Results Table"):
            st.dataframe(df_transport)
    
        


