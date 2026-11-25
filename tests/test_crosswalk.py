"""
Module 1: Canonical District Crosswalk & Population Ground-Truth Tests.
Verifies 100% resolution of all 35 KP districts, census ground-truth (40,856,097),
merging of tribal sub-divisions, and reconciliation of IDSR spellings.
"""

import json
import pandas as pd
from pathlib import Path

def test_canonical_districts_count_and_population(paths):
    census_file = paths["data_processed"] / "kp_census_2023.csv"
    assert census_file.exists(), "kp_census_2023.csv missing"

    df = pd.read_csv(census_file)
    assert len(df) == 35, f"Expected 35 canonical districts, found {len(df)}"

    total_pop = df["population_2023"].sum()
    assert total_pop == 40856097, f"Expected exactly 40,856,097 population, found {total_pop}"

def test_pcode_crosswalk_coverage(paths):
    crosswalk_file = paths["data_processed"] / "pcode_crosswalk.json"
    assert crosswalk_file.exists(), "pcode_crosswalk.json missing"

    with open(crosswalk_file, "r", encoding="utf-8") as f:
        crosswalk_data = json.load(f)

    districts = crosswalk_data.get("districts", [])
    assert len(districts) == 35, f"Expected 35 districts in crosswalk, got {len(districts)}"

    all_pcodes = {f"PK5{i:02d}" for i in range(1, 36)}
    dist_pcodes = {d["pcode"] for d in districts}
    assert dist_pcodes == all_pcodes

def test_subdivisions_and_tribal_splits(paths):
    crosswalk_file = paths["data_processed"] / "pcode_crosswalk.json"
    with open(crosswalk_file, "r", encoding="utf-8") as f:
        crosswalk_data = json.load(f)

    aliases = crosswalk_data.get("alias_lookup", {})
    # Former FRs / Sub-divisions mapped to parent districts
    assert aliases.get("sd bannu") == "PK503"
    assert aliases.get("bannu") == "PK503"
    assert aliases.get("kurram") == "PK518"

def test_idsr_panel_reconciliation(paths):
    panel_file = paths["data_processed"] / "idsr_weekly_panel.parquet"
    assert panel_file.exists(), "idsr_weekly_panel.parquet missing"

    df = pd.read_parquet(panel_file)
    unique_pcodes = set(df["district_pcode"].unique())
    all_pcodes = {f"PK5{i:02d}" for i in range(1, 36)}
    assert unique_pcodes == all_pcodes, f"Mismatch in panel districts: {all_pcodes ^ unique_pcodes}"
    assert len(df) == 55832, f"Expected exactly 55,832 weekly panel rows, got {len(df)}"
