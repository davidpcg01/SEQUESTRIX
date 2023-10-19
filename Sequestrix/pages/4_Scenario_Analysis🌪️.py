import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import csv
import pandas as pd
import numpy as np
import os
import streamlit.components.v1 as components

st.set_page_config(page_title="Scenario Analysis", page_icon="🌪️", layout="wide")

st.write('# Coming Soon')

# with st.sidebar:
#     files = st.file_uploader("Upload :green[Scenario Input Files]", accept_multiple_files=True, help="Upload Excel Input File")
#     clear_button = st.button('Clear')

# def save_uploaded_file(file):
#     with open(os.path.join(f"Sequestrix/app/scenario_files/{file.name}"), "wb") as f:
#         f.write(file.getbuffer())

# if files:
#     for i in range(len(files)):
#         save_uploaded_file(files[i])

# if clear_button:
#     saved_files = os.listdir("Sequestrix/app/scenario_files")
#     for sfile in saved_files:
#         if sfile.endswith('.csv'):
#             os.remove(os.path.join('Sequestrix/app/scenario_files', sfile))



