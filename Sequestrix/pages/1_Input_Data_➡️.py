import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import time
import pandas as pd
import numpy as np
import os
import sys
from pathlib import Path

st.set_page_config(page_title="Input Data", page_icon="➡️", layout="wide")

ROOT_PATH = Path(__file__).parent.parent.parent.resolve()
STRIX_PATH = ROOT_PATH / "Sequestrix"
sys.path.append(STRIX_PATH)


keys_to_track = ["INPUT_FILE", "PIPELINE_FILE", "direction", "tiein", "exclusion", "only", "etype", "onlyin", "onlyout"]

for key in keys_to_track:
    if key not in st.session_state:
        st.session_state[key] = None

indexes = ["dindex", "findex", "eindex"]
for key in indexes:
    if key not in st.session_state:
        st.session_state[key] = 0

if "point1" not in st.session_state:
    st.session_state.point1 = ["", ""]
if "point2" not in st.session_state:
    st.session_state.point2 = ["", ""]

# st.write(st.session_state)

def save_uploaded_file(file, type):
    if type == "inp":
        with open(os.path.join("Sequestrix/app/input_files/Input_File.xlsx"), "wb") as f:
            f.write(file.getbuffer())
    elif type == "pipe":
        with open(os.path.join("Sequestrix/app/pipeline_files/Pipeline_File.xlsx"), "wb") as f:
            f.write(file.getbuffer())


with st.sidebar:
    #input file
    INPUT_FILE = st.file_uploader("Upload :green[Input File]", help="Upload Excel Input File")
    if INPUT_FILE:
        st.write(":green[Uploaded File: ]", INPUT_FILE.name)
        save_uploaded_file(INPUT_FILE, "inp")
    elif st.session_state["INPUT_FILE"]:
        st.write(":green[Showing File: ]", st.session_state.INPUT_FILE.name)
        

    #pipeline file
    PIPELINE_FILE = st.file_uploader("Upload :green[Pipeline Input]", help="Upload Excel File With Pipeline Details")
    if PIPELINE_FILE or st.session_state.PIPELINE_FILE:
        if PIPELINE_FILE:
            st.write(":green[Uploaded File: ]", PIPELINE_FILE.name)
            save_uploaded_file(PIPELINE_FILE, "pipe")
        else:
            st.write(":green[Uploaded File: ]", st.session_state.PIPELINE_FILE.name)
        direction = st.selectbox("Pipeline Direction",
                             ("unidirectional", "bidirectional"), index=st.session_state.dindex)
        tiein = st.checkbox("Tie In Points", value=st.session_state.tiein)
        if tiein:
            point1 = ["", ""]
            point2 = ["", ""]
            st.write("Point 1 Tie-in location")
            colp1, colp2 = st.columns(2)
            with colp1:
                lat1 = st.text_input("Point 1 Lat", value=st.session_state.point1[0])
            with colp2:
                lon1 = st.text_input("Point 1 lon", value=st.session_state.point1[1])
            if (lat1 != "") and (lon1 != ""):
                point1 = (float(lat1), float(lon1))
                st.session_state.point1 = point1
            else:
                st.session_state.point1 = ["", ""]
                point1 = None

            colp3, colp4 = st.columns(2)
            with colp1:
                lat2 = st.text_input("Point 2 Lat", value=st.session_state.point2[0])
            with colp2:
                lon2 = st.text_input("Point 2 lon", value=st.session_state.point2[1])
            if (lat2 != "") and (lon2 != ""):
                point2 = (float(lat2), float(lon2))
                st.session_state.point2 = point2
            else:
                st.session_state.point2 = ["", ""]
                point2 = None

            st.write(f":orange[Point 1: {point1}]")
            st.write(f":orange[Point 2: {point2}]")

            st.write(":red[Select all that applies Below ⚠️]")
            only = st.selectbox("Flow Direction at Tie-pt(s)",
                            ("Both", "Only-In", "Only-Out"), index=st.session_state.findex)
            onlyin = st.session_state.onlyin = True if only == "Only-In" else False
            onlyout = st.session_state.onlyout = True if only == "Only-Out" else False
            exclusion = st.checkbox("Exclusion", value=st.session_state.exclusion)
            if exclusion:
                etype = st.selectbox("Exclusion Type",
                                    ("before", "after"), index=st.session_state.eindex)


# st.write(st.session_state)        


#SESSION STATE PERSISTENCE
if st.session_state["INPUT_FILE"] is None:
    st.session_state["INPUT_FILE"] = INPUT_FILE
elif (INPUT_FILE) and (INPUT_FILE != st.session_state.INPUT_FILE):
    st.session_state["INPUT_FILE"] = INPUT_FILE

if st.session_state["PIPELINE_FILE"] is None:
    st.session_state["PIPELINE_FILE"] = PIPELINE_FILE
elif (PIPELINE_FILE) and (PIPELINE_FILE != st.session_state.PIPELINE_FILE):
    st.session_state["PIPELINE_FILE"] = PIPELINE_FILE

if PIPELINE_FILE or st.session_state["PIPELINE_FILE"]:
    if st.session_state["tiein"] is None:
        st.session_state["tiein"] = tiein
    elif (tiein is False) and (tiein != st.session_state.tiein):
        st.session_state["tiein"] = tiein
    elif (tiein is True) and (tiein != st.session_state.tiein):
        st.session_state["tiein"] = tiein

    if direction == "unidirectional":
        st.session_state.dindex = 0
        st.session_state.direction = direction
    else:
        st.session_state.dindex = 1
        st.session_state.direction = direction


    if tiein or st.session_state.tiein:
        if st.session_state["exclusion"] is None:
            st.session_state["exclusion"] = exclusion
        elif (exclusion is False) and (exclusion != st.session_state.exclusion):
            st.session_state["exclusion"] = exclusion
        elif (exclusion is True) and (exclusion != st.session_state.exclusion):
            st.session_state["exclusion"] = exclusion

        if only == "Both":
            st.session_state.findex = 0
            st.session_state.only = only
        elif only == "Only-In":
            st.session_state.findex = 1
            st.session_state.only = only
        else:
            st.session_state.findex = 2
            st.session_state.only = only
        if exclusion:
            if etype == "before":
                st.session_state.eindex = 0
                st.session_state.etype = etype
            else:
                st.session_state.eindex = 1
                st.session_state.etype = etype


def showInputResults():
    tab1, tab2, tab3 = st.tabs(["CO2 Sources", "CO2 Sinks", "Network Map"])
    if st.session_state.INPUT_FILE:
        with tab1:
            source_df = pd.read_excel(st.session_state.INPUT_FILE, sheet_name="sources")
            fig_col1, fig_col2 = st.columns(2)
            with fig_col1:
                st.markdown(f"#### Available Annual Capture Volume: {round(source_df['Capture Capacity (MTCO2/yr)'].sum(), 2)} MTCO2/yr")
                fig = px.pie(source_df, values="Capture Capacity (MTCO2/yr)", names="UNIQUE NAME", hole=.5, color_discrete_sequence=px.colors.sequential.RdBu)
                st.plotly_chart(fig, use_container_width=True)

            with fig_col2:
                st.markdown("#### Unit Capture Cost")
                fig2 = px.bar(source_df, x="UNIQUE NAME", y="Total Unit Cost ($/tCO2)", color_discrete_sequence=px.colors.sequential.RdBu)
                st.plotly_chart(fig2, use_container_width=True)

            with st.expander("See CO2 Souces Input Table"):
                st.dataframe(source_df)

        with tab2:
            sink_df = pd.read_excel(st.session_state.INPUT_FILE, sheet_name="sinks")
            fig_col1, fig_col2 = st.columns(2)
            with fig_col1:
                st.markdown(f"#### Available Total Storage Volume: {round(sink_df['Storage Capacity (MTCO2)'].sum(), 2)} MTCO2")
                fig3 = px.pie(sink_df, values="Storage Capacity (MTCO2)", names="UNIQUE NAME", hole=.5, color_discrete_sequence=px.colors.sequential.Emrld)
                st.plotly_chart(fig3, use_container_width=True)

            with fig_col2:
                st.markdown("#### Unit Storage Cost")
                fig4 = px.bar(sink_df, x="UNIQUE NAME", y="Total Unit Cost ($/tCO2)", color_discrete_sequence=px.colors.sequential.Emrld)
                st.plotly_chart(fig4, use_container_width=True)

            with st.expander("See CO2 Sinks Input Table"):
                st.dataframe(sink_df)


        with tab3:
            merged = {"Name": [],
                    "Type": [],
                    "Lat": [],
                    "Lon": []}
            merged["Name"].extend(source_df["UNIQUE NAME"].tolist())
            merged["Name"].extend(sink_df["UNIQUE NAME"].tolist())
            merged["Type"].extend(["source"]*len(source_df))
            merged["Type"].extend(["sink"]*len(sink_df))
            merged["Lat"].extend(source_df["Lat"].tolist())
            merged["Lat"].extend(sink_df["Lat"].tolist())
            merged["Lon"].extend(source_df["Lon"].tolist())
            merged["Lon"].extend(sink_df["Lon"].tolist())

            

            fig5 = px.scatter_mapbox(merged, lat="Lat", lon="Lon", hover_name="Name", color="Type", zoom=8, height=1000, width=1200, size="Lat", 
                                    color_discrete_map={"source":"red", "sink":"green"})
            
            if PIPELINE_FILE or st.session_state.PIPELINE_FILE:
                pipeline_line = {"Name":[], "Lat":[], "Lon": []}
                df = pd.read_excel(st.session_state.PIPELINE_FILE)
                for i in range(len(df)):
                    pipeline_line["Name"].append(df["Name"][0])
                    pipeline_line["Lat"].append(df["Lat"][i])
                    pipeline_line["Lon"].append(df["Long"][i])
                pipeline_line = pd.DataFrame(pipeline_line)

                fig5.add_trace(go.Scattermapbox(
                mode = "lines",
                lat = pipeline_line["Lat"],
                lon = pipeline_line["Lon"],
                showlegend=True,
                opacity=0.5,
                line={'width': 5, 'color':'purple'},
                name = str(pipeline_line["Name"][0])
                ))



            fig5.update_layout(mapbox_style="open-street-map")
            st.plotly_chart(fig5, use_container_width=True)


            with st.expander("See Geolocation Input Data"):
                st.dataframe(merged)

showInputResults()
