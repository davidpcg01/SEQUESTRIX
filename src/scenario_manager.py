import os
import re
import csv
import json
import shutil
from datetime import datetime

import pandas as pd
import plotly.io as pio

SCENARIO_DIR = os.path.join("Sequestrix", "app", "scenario_files")


def _validate_name(name):
    if not name or not name.strip():
        return False, "Scenario name cannot be empty."
    name = name.strip()
    if len(name) > 50:
        return False, "Scenario name must be 50 characters or fewer."
    if not re.match(r'^[\w\s\-]+$', name):
        return False, "Scenario name can only contain letters, digits, spaces, hyphens, and underscores."
    return True, name


def scenario_exists(name):
    valid, clean = _validate_name(name)
    if not valid:
        return False
    return os.path.isdir(os.path.join(SCENARIO_DIR, clean))


def save_scenario(name, solution_csv_src, metadata_dict, network_map_fig=None):
    valid, result = _validate_name(name)
    if not valid:
        return False, result

    clean_name = result
    scenario_path = os.path.join(SCENARIO_DIR, clean_name)
    os.makedirs(scenario_path, exist_ok=True)

    try:
        shutil.copy2(solution_csv_src, os.path.join(scenario_path, "solution.csv"))
    except Exception as e:
        return False, f"Failed to copy solution CSV: {e}"

    meta = dict(metadata_dict)
    if "dur" in meta:
        try:
            meta["dur"] = int(meta["dur"])
        except (ValueError, TypeError):
            pass
    meta["saved_at"] = datetime.now().isoformat()

    try:
        with open(os.path.join(scenario_path, "metadata.json"), "w") as f:
            json.dump(meta, f, indent=2)
    except Exception as e:
        return False, f"Failed to write metadata: {e}"

    if network_map_fig is not None:
        try:
            fig_json = pio.to_json(network_map_fig)
            with open(os.path.join(scenario_path, "network_map.json"), "w") as f:
                f.write(fig_json)
        except Exception as e:
            return False, f"Failed to serialize network map: {e}"

    return True, f"Scenario '{clean_name}' saved successfully."


def list_scenarios():
    if not os.path.isdir(SCENARIO_DIR):
        return []
    scenarios = []
    for entry in sorted(os.listdir(SCENARIO_DIR)):
        entry_path = os.path.join(SCENARIO_DIR, entry)
        if os.path.isdir(entry_path):
            csv_path = os.path.join(entry_path, "solution.csv")
            if os.path.isfile(csv_path):
                scenarios.append(entry)
    return scenarios


def load_scenario_metadata(name):
    meta_path = os.path.join(SCENARIO_DIR, name, "metadata.json")
    if not os.path.isfile(meta_path):
        return None
    try:
        with open(meta_path, "r") as f:
            return json.load(f)
    except Exception:
        return None


def load_scenario_results(name):
    csv_path = os.path.join(SCENARIO_DIR, name, "solution.csv")
    if not os.path.isfile(csv_path):
        return None

    df_capture = {"CO2 Source ID": [], "CO2 Source Name": [],
                  "Capture Amount (MTCO2/yr)": [], "Capture Cost ($M/yr)": []}
    df_storage = {"CO2 Sink ID": [], "CO2 Sink Name": [],
                  "Storage Amount (MTCO2/yr)": [], "Storage Cost ($M/yr)": []}
    df_transport = {"Start Point": [], "End Point": [], "Length (km)": [],
                    "Weight": [], "CO2 Transported (MTCO2/yr)": [],
                    "Transport Cost ($M/yr)": []}

    try:
        with open(csv_path, "r") as read_obj:
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
                df_transport["Weight"].append(float(curr[3]))
                df_transport["CO2 Transported (MTCO2/yr)"].append(float(curr[4]))
                df_transport["Transport Cost ($M/yr)"].append(float(curr[5]))
                curr = next(csv_reader)

        df_capture = pd.DataFrame(df_capture)
        df_storage = pd.DataFrame(df_storage)
        df_transport = pd.DataFrame(df_transport)

        return df_capture, df_storage, df_transport, dur, target, total_cap

    except Exception:
        return None


def load_scenario_map(name):
    map_path = os.path.join(SCENARIO_DIR, name, "network_map.json")
    if not os.path.isfile(map_path):
        return None
    try:
        with open(map_path, "r") as f:
            return pio.from_json(f.read())
    except Exception:
        return None


def delete_scenario(name):
    scenario_path = os.path.join(SCENARIO_DIR, name)
    if not os.path.isdir(scenario_path):
        return False, f"Scenario '{name}' not found."
    try:
        shutil.rmtree(scenario_path)
        return True, f"Scenario '{name}' deleted."
    except Exception as e:
        return False, f"Failed to delete scenario: {e}"
