import sys
from pathlib import Path

ROOT_PATH = Path(__file__).parent.parent.parent.resolve()
SRC_PATH = ROOT_PATH.joinpath("src")
if str(SRC_PATH) not in sys.path:
    sys.path.insert(1, str(SRC_PATH))

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import scenario_manager

st.set_page_config(page_title="Scenario Analysis", page_icon="🌪️", layout="wide")

scenarios = scenario_manager.list_scenarios()

with st.sidebar:
    st.header("Scenario Analysis")

    if not scenarios:
        st.info("No scenarios saved yet. Run a solve and save as scenario from the Solve or Dashboard page.")
        selected = []
    else:
        selected = st.multiselect("Select Scenarios to Compare", scenarios, default=None)

        st.divider()
        st.subheader("Manage Scenarios")
        delete_target = st.selectbox("Delete a Scenario", [""] + scenarios, index=0,
                                     key="delete_scenario_select")
        if st.button("Delete", key="delete_scenario_btn") and delete_target:
            ok, msg = scenario_manager.delete_scenario(delete_target)
            if ok:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)

if not selected:
    st.write("# Scenario Analysis")
    if scenarios:
        st.info("Select one or more scenarios from the sidebar to view or compare results.")
    else:
        st.info("No scenarios saved yet. Run a solve and save as scenario to get started.")
    st.stop()

# ---- Load data for all selected scenarios ----
loaded = {}
for name in selected:
    result = scenario_manager.load_scenario_results(name)
    meta = scenario_manager.load_scenario_metadata(name)
    if result is None:
        st.warning(f"Could not load results for scenario '{name}'. Skipping.")
        continue
    df_cap, df_sto, df_trans, dur, target, total_cap = result
    loaded[name] = {
        "df_capture": df_cap,
        "df_storage": df_sto,
        "df_transport": df_trans,
        "dur": dur,
        "target": target,
        "total_cap": total_cap,
        "metadata": meta or {},
    }

if not loaded:
    st.error("No valid scenario data could be loaded.")
    st.stop()

# ---- Single scenario view ----
if len(loaded) == 1:
    name = list(loaded.keys())[0]
    data = loaded[name]
    df_capture = data["df_capture"]
    df_storage = data["df_storage"]
    df_transport = data["df_transport"]
    dur = data["dur"]
    target = data["target"]
    total_cap = data["total_cap"]
    meta = data["metadata"]

    st.write(f"# Scenario: {name}")

    col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
    col1.metric("Project Duration (yrs)", dur)
    col2.metric("Total CO2 Sequestered (MTCO2)", round(total_cap * dur, 1))
    col3.metric("Number of Sources", len(df_capture))
    col4.metric("Number of Sinks", len(df_storage))

    if not df_capture.empty and df_capture["Capture Amount (MTCO2/yr)"].sum() > 0:
        unit_cap = sum(df_capture["Capture Cost ($M/yr)"]) / sum(df_capture["Capture Amount (MTCO2/yr)"])
        unit_sto = sum(df_storage["Storage Cost ($M/yr)"]) / sum(df_storage["Storage Amount (MTCO2/yr)"])
        unit_trans = sum(df_transport["Transport Cost ($M/yr)"]) / sum(df_capture["Capture Amount (MTCO2/yr)"])

        st.markdown("---")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Unit Capture Cost ($/tCO2)", round(unit_cap, 2))
        c2.metric("Unit Storage Cost ($/tCO2)", round(unit_sto, 2))
        c3.metric("Unit Transport Cost ($/tCO2)", round(unit_trans, 2))
        c4.metric("Total Unit Cost ($/tCO2)", round(unit_cap + unit_sto + unit_trans, 2))

    tab1, tab2, tab3, tab4 = st.tabs(["Capture", "Storage", "Transport", "Network Map"])

    with tab1:
        if not df_capture.empty:
            fig = px.bar(df_capture, x="CO2 Source ID", y="Capture Amount (MTCO2/yr)",
                         hover_name="CO2 Source Name", color_discrete_sequence=px.colors.sequential.RdBu)
            st.plotly_chart(fig, use_container_width=True)
        with st.expander("Capture Data"):
            st.dataframe(df_capture)

    with tab2:
        if not df_storage.empty:
            fig = px.bar(df_storage, x="CO2 Sink ID", y="Storage Amount (MTCO2/yr)",
                         hover_name="CO2 Sink Name", color_discrete_sequence=px.colors.sequential.Emrld)
            st.plotly_chart(fig, use_container_width=True)
        with st.expander("Storage Data"):
            st.dataframe(df_storage)

    with tab3:
        if not df_transport.empty:
            df_transport["Pipeline Arcs"] = df_transport["Start Point"] + " - " + df_transport["End Point"]
            fig = px.bar(df_transport, x="Pipeline Arcs", y="CO2 Transported (MTCO2/yr)",
                         color="Transport Cost ($M/yr)", color_continuous_scale=px.colors.sequential.Oryel)
            st.plotly_chart(fig, use_container_width=True)
        with st.expander("Transport Data"):
            st.dataframe(df_transport)

    with tab4:
        map_fig = scenario_manager.load_scenario_map(name)
        if map_fig is not None:
            st.plotly_chart(map_fig, use_container_width=True)
        else:
            st.info("No network map saved for this scenario.")

    st.stop()

# ---- Multi-scenario comparison ----
st.write("# Scenario Comparison")

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Summary", "Capture", "Storage", "Transport", "Network Maps"])

# -- Tab 1: Summary --
with tab1:
    summary_rows = []
    for name, data in loaded.items():
        df_cap = data["df_capture"]
        df_sto = data["df_storage"]
        df_trans = data["df_transport"]
        dur = data["dur"]
        total_cap = data["total_cap"]

        total_cap_cost = df_cap["Capture Cost ($M/yr)"].sum() if not df_cap.empty else 0
        total_sto_cost = df_sto["Storage Cost ($M/yr)"].sum() if not df_sto.empty else 0
        total_trans_cost = df_trans["Transport Cost ($M/yr)"].sum() if not df_trans.empty else 0
        total_cost = total_cap_cost + total_sto_cost + total_trans_cost
        total_captured = df_cap["Capture Amount (MTCO2/yr)"].sum() if not df_cap.empty else 0

        unit_cap = total_cap_cost / total_captured if total_captured > 0 else 0
        unit_sto = total_sto_cost / total_captured if total_captured > 0 else 0
        unit_trans = total_trans_cost / total_captured if total_captured > 0 else 0
        unit_total = unit_cap + unit_sto + unit_trans

        status = "Economic" if unit_total <= -5 else "Marginal" if unit_total < 0 else "Sub-Economic"

        summary_rows.append({
            "Scenario": name,
            "Duration (yrs)": dur,
            "Target (MTCO2/yr)": data["target"],
            "Actual Capture (MTCO2/yr)": round(total_captured, 4),
            "Total Stored (MTCO2)": round(total_cap * dur, 2) if total_cap else 0,
            "Capture Cost ($M/yr)": round(total_cap_cost, 2),
            "Storage Cost ($M/yr)": round(total_sto_cost, 2),
            "Transport Cost ($M/yr)": round(total_trans_cost, 2),
            "Total Cost ($M/yr)": round(total_cost, 2),
            "Unit Cost ($/tCO2)": round(unit_total, 2),
            "Status": status,
        })

    summary_df = pd.DataFrame(summary_rows)
    st.dataframe(summary_df, use_container_width=True, hide_index=True)

    st.markdown("#### Total Cost Breakdown by Scenario")
    cost_df = summary_df.melt(
        id_vars=["Scenario"],
        value_vars=["Capture Cost ($M/yr)", "Storage Cost ($M/yr)", "Transport Cost ($M/yr)"],
        var_name="Cost Type", value_name="Cost ($M/yr)")
    fig_cost = px.bar(cost_df, x="Scenario", y="Cost ($M/yr)", color="Cost Type",
                      barmode="group", color_discrete_sequence=px.colors.qualitative.Set2)
    st.plotly_chart(fig_cost, use_container_width=True)

    st.markdown("#### Unit Cost Comparison")
    unit_rows = []
    for row in summary_rows:
        s = row["Scenario"]
        cap_amt = row["Actual Capture (MTCO2/yr)"]
        if cap_amt > 0:
            unit_rows.append({"Scenario": s, "Cost Type": "Capture", "$/tCO2": round(row["Capture Cost ($M/yr)"] / cap_amt, 2)})
            unit_rows.append({"Scenario": s, "Cost Type": "Storage", "$/tCO2": round(row["Storage Cost ($M/yr)"] / cap_amt, 2)})
            unit_rows.append({"Scenario": s, "Cost Type": "Transport", "$/tCO2": round(row["Transport Cost ($M/yr)"] / cap_amt, 2)})
    if unit_rows:
        unit_df = pd.DataFrame(unit_rows)
        fig_unit = px.bar(unit_df, x="Scenario", y="$/tCO2", color="Cost Type",
                          barmode="group", color_discrete_sequence=px.colors.qualitative.Pastel)
        st.plotly_chart(fig_unit, use_container_width=True)

# -- Tab 2: Capture Comparison --
with tab2:
    all_cap_rows = []
    for name, data in loaded.items():
        df = data["df_capture"].copy()
        if not df.empty:
            df["Scenario"] = name
            all_cap_rows.append(df)

    if all_cap_rows:
        all_cap_df = pd.concat(all_cap_rows, ignore_index=True)

        st.markdown("#### Capture Amount by Source Across Scenarios")
        fig_cap = px.bar(all_cap_df, x="CO2 Source ID", y="Capture Amount (MTCO2/yr)",
                         color="Scenario", barmode="group", hover_name="CO2 Source Name",
                         color_discrete_sequence=px.colors.qualitative.Set1)
        st.plotly_chart(fig_cap, use_container_width=True)

        st.markdown("#### Capture Cost by Source Across Scenarios")
        fig_cap_cost = px.bar(all_cap_df, x="CO2 Source ID", y="Capture Cost ($M/yr)",
                              color="Scenario", barmode="group",
                              color_discrete_sequence=px.colors.qualitative.Set2)
        st.plotly_chart(fig_cap_cost, use_container_width=True)

        with st.expander("All Capture Data"):
            st.dataframe(all_cap_df, use_container_width=True, hide_index=True)
    else:
        st.info("No capture data available.")

# -- Tab 3: Storage Comparison --
with tab3:
    all_sto_rows = []
    for name, data in loaded.items():
        df = data["df_storage"].copy()
        if not df.empty:
            df["Scenario"] = name
            all_sto_rows.append(df)

    if all_sto_rows:
        all_sto_df = pd.concat(all_sto_rows, ignore_index=True)

        st.markdown("#### Storage Amount by Sink Across Scenarios")
        fig_sto = px.bar(all_sto_df, x="CO2 Sink ID", y="Storage Amount (MTCO2/yr)",
                         color="Scenario", barmode="group", hover_name="CO2 Sink Name",
                         color_discrete_sequence=px.colors.qualitative.Set1)
        st.plotly_chart(fig_sto, use_container_width=True)

        st.markdown("#### Storage Cost by Sink Across Scenarios")
        fig_sto_cost = px.bar(all_sto_df, x="CO2 Sink ID", y="Storage Cost ($M/yr)",
                              color="Scenario", barmode="group",
                              color_discrete_sequence=px.colors.qualitative.Set2)
        st.plotly_chart(fig_sto_cost, use_container_width=True)

        with st.expander("All Storage Data"):
            st.dataframe(all_sto_df, use_container_width=True, hide_index=True)
    else:
        st.info("No storage data available.")

# -- Tab 4: Transport Comparison --
with tab4:
    all_trans_rows = []
    for name, data in loaded.items():
        df = data["df_transport"].copy()
        if not df.empty:
            df["Scenario"] = name
            df["Pipeline Arcs"] = df["Start Point"] + " - " + df["End Point"]
            all_trans_rows.append(df)

    if all_trans_rows:
        all_trans_df = pd.concat(all_trans_rows, ignore_index=True)

        st.markdown("#### CO2 Transported by Pipeline Across Scenarios")
        fig_trans = px.bar(all_trans_df, x="Pipeline Arcs", y="CO2 Transported (MTCO2/yr)",
                           color="Scenario", barmode="group",
                           color_discrete_sequence=px.colors.qualitative.Set1)
        st.plotly_chart(fig_trans, use_container_width=True)

        st.markdown("#### Transport Cost by Pipeline Across Scenarios")
        fig_trans_cost = px.bar(all_trans_df, x="Pipeline Arcs", y="Transport Cost ($M/yr)",
                                color="Scenario", barmode="group",
                                color_discrete_sequence=px.colors.qualitative.Set2)
        st.plotly_chart(fig_trans_cost, use_container_width=True)

        with st.expander("All Transport Data"):
            st.dataframe(all_trans_df, use_container_width=True, hide_index=True)
    else:
        st.info("No transport data available.")

# -- Tab 5: Network Maps --
with tab5:
    st.markdown("#### Side-by-Side Network Maps")
    map_cols = st.columns(len(loaded))
    for idx, (name, data) in enumerate(loaded.items()):
        with map_cols[idx]:
            st.markdown(f"**{name}**")
            map_fig = scenario_manager.load_scenario_map(name)
            if map_fig is not None:
                st.plotly_chart(map_fig, use_container_width=True)
            else:
                st.info("No network map saved.")
