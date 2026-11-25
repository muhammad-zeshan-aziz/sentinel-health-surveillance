"""
Deterministic Calibrated Synthetic Hospital and Laboratory Generator.
Grounded in real IDSR district-week panel data (2025 weeks 20-24).
Generates:
  1. Master facility directory (data/demo_hospitals/facilities_kp.csv)
  2. Spotlight district hospital CSVs (ATH Abbottabad, DHQ Mansehra, Swat, Lower Dir, Haripur)
  3. Controlled edge-case test fixtures (invalid, duplicates, late corrected, missing vs zero)
"""

import sys
import os
import random
from pathlib import Path
from datetime import date, datetime, timedelta
from typing import Dict, Any, List, Tuple
import pandas as pd
import numpy as np

# Ensure workspace root in path
SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE_DIR = SCRIPT_DIR.parent.parent
if str(WORKSPACE_DIR) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_DIR))

from src.ingestion.crosswalk import CANONICAL_KP_DISTRICTS, resolve_district_pcode
from src.ingestion.pseudonymizer import hash_patient_id, DEFAULT_SERVER_PEPPER

# Set deterministic seeds
RANDOM_SEED = 42
random.seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)

AGE_BANDS = ["0-4", "5-14", "15-24", "25-44", "45-64", "65+"]
AGE_BAND_WEIGHTS = [0.15, 0.20, 0.25, 0.22, 0.12, 0.06]

GENDERS = ["Male", "Female"]
GENDER_WEIGHTS = [0.52, 0.48]

TEST_TYPES = {
    "Malaria": ["RDT (Rapid Diagnostic Test)", "Microscopy (Thick & Thin Smear)"],
    "Typhoid": ["Blood Culture", "Typhidot (IgM/IgG)", "Widal Agglutination"]
}

# Calibration Window
CALIBRATION_YEAR = 2025
CALIBRATION_WEEKS = [20, 21, 22, 23, 24]

# Spotlight facilities definition
SPOTLIGHT_FACILITIES = {
    "PK501": {
        "name": "Ayub Teaching Hospital (ATH)",
        "facility_type": "tertiary_hospital",
        "tehsil": "Abbottabad",
        "file_name": "abbottabad_ath_records.csv",
        "share_of_district": 0.85
    },
    "PK522": {
        "name": "District Headquarter (DHQ) Hospital Mansehra",
        "facility_type": "dhq",
        "tehsil": "Mansehra",
        "file_name": "mansehra_dhq_records.csv",
        "share_of_district": 0.75
    },
    "PK532": {
        "name": "Saidu Teaching & DHQ Hospital Swat",
        "facility_type": "tertiary_hospital",
        "tehsil": "Saidu Sharif",
        "file_name": "swat_dhq_records.csv",
        "share_of_district": 0.80
    },
    "PK520": {
        "name": "DHQ Hospital Timergara",
        "facility_type": "dhq",
        "tehsil": "Timergara",
        "file_name": "lower_dir_dhq_records.csv",
        "share_of_district": 0.82
    },
    "PK511": {
        "name": "DHQ Hospital Haripur",
        "facility_type": "dhq",
        "tehsil": "Haripur",
        "file_name": "haripur_dhq_records.csv",
        "share_of_district": 0.78
    }
}


def epiweek_to_dates(year: int, week: int) -> List[date]:
    """Returns 7 calendar dates corresponding to the ISO epi week."""
    # First day of ISO week: Monday
    d = date.fromisocalendar(year, week, 1)
    return [d + timedelta(days=i) for i in range(7)]


def build_facility_master() -> pd.DataFrame:
    """Builds comprehensive master directory of public hospitals & labs across all 35 KP districts."""
    facilities: List[Dict[str, Any]] = []
    fac_id = 1

    for pcode, meta in sorted(CANONICAL_KP_DISTRICTS.items()):
        d_name = meta["name"]
        lat = meta["center_lat"]
        lon = meta["center_lon"]

        # Spotlight facility or primary DHQ
        if pcode in SPOTLIGHT_FACILITIES:
            sf = SPOTLIGHT_FACILITIES[pcode]
            facilities.append({
                "facility_id": fac_id,
                "district_pcode": pcode,
                "district_name": d_name,
                "facility_name": sf["name"],
                "facility_type": sf["facility_type"],
                "tehsil": sf["tehsil"],
                "lat": lat + 0.01,
                "lon": lon + 0.01,
                "is_spotlight": True,
                "is_mock": False,
                "api_sync_enabled": True
            })
            fac_id += 1
        else:
            facilities.append({
                "facility_id": fac_id,
                "district_pcode": pcode,
                "district_name": d_name,
                "facility_name": f"DHQ Hospital {d_name}",
                "facility_type": "dhq",
                "tehsil": d_name,
                "lat": lat,
                "lon": lon,
                "is_spotlight": False,
                "is_mock": False,
                "api_sync_enabled": True
            })
            fac_id += 1

        # Secondary facility (THQ / Diagnostic Lab)
        facilities.append({
            "facility_id": fac_id,
            "district_pcode": pcode,
            "district_name": d_name,
            "facility_name": f"{d_name} District Public Health Diagnostic Lab",
            "facility_type": "lab",
            "tehsil": d_name,
            "lat": lat - 0.01,
            "lon": lon - 0.01,
            "is_spotlight": False,
            "is_mock": True,
            "api_sync_enabled": True
        })
        fac_id += 1

    return pd.DataFrame(facilities)


def generate_calibrated_records(panel_df: pd.DataFrame, facilities_df: pd.DataFrame) -> Tuple[Dict[str, pd.DataFrame], pd.DataFrame]:
    """
    Generates calibrated synthetic lab records grounded in IDSR 2025 weeks 20-24.
    Returns:
      spotlight_files: Dict[filename -> DataFrame]
      all_kp_records: DataFrame
    """
    all_rows: List[Dict[str, Any]] = []
    spotlight_rows: Dict[str, List[Dict[str, Any]]] = {
        meta["file_name"]: [] for meta in SPOTLIGHT_FACILITIES.values()
    }

    # Filter panel to calibration window
    sub_panel = panel_df[
        (panel_df["year"] == CALIBRATION_YEAR) & 
        (panel_df["epi_week"].isin(CALIBRATION_WEEKS)) &
        (panel_df["condition"].isin(["Malaria", "Typhoid"]))
    ]

    record_counter = 100000

    for pcode, meta in CANONICAL_KP_DISTRICTS.items():
        dist_panel = sub_panel[sub_panel["district_pcode"] == pcode]
        fac_sub = facilities_df[facilities_df["district_pcode"] == pcode]
        primary_fac = fac_sub.iloc[0]["facility_name"]
        primary_fac_id = fac_sub.iloc[0]["facility_id"]
        is_spotlight = pcode in SPOTLIGHT_FACILITIES

        for week in CALIBRATION_WEEKS:
            week_dates = epiweek_to_dates(CALIBRATION_YEAR, week)

            for disease in ["Malaria", "Typhoid"]:
                cond_row = dist_panel[(dist_panel["epi_week"] == week) & (dist_panel["condition"] == disease)]
                
                if cond_row.empty or cond_row["is_missing"].iloc[0]:
                    # Missing report gap: no records submitted
                    continue

                total_real_cases = int(cond_row["total_cases"].iloc[0]) if pd.notna(cond_row["total_cases"].iloc[0]) else 0

                # Determine how many positive cases to assign to primary facility
                if is_spotlight:
                    share = SPOTLIGHT_FACILITIES[pcode]["share_of_district"]
                    fac_positives = int(round(total_real_cases * share))
                else:
                    fac_positives = int(round(total_real_cases * 0.70))

                # Clinical positivity rate: Malaria ~15%, Typhoid ~25%
                pos_rate = 0.15 if disease == "Malaria" else 0.25
                # Negative tests needed to establish realistic denominator
                if fac_positives > 0:
                    fac_negatives = int(round(fac_positives * ((1.0 - pos_rate) / pos_rate)))
                else:
                    # True zero reporting: laboratory conducted surveillance tests, all negative
                    fac_negatives = random.randint(15, 40)

                total_tests = fac_positives + fac_negatives
                test_results = ["Positive"] * fac_positives + ["Negative"] * fac_negatives
                random.shuffle(test_results)

                for res in test_results:
                    record_counter += 1
                    ext_id = f"ATH-{CALIBRATION_YEAR}-W{week:02d}-{record_counter}" if pcode == "PK501" else f"LAB-{pcode}-{CALIBRATION_YEAR}-{record_counter}"
                    t_date = random.choice(week_dates)
                    age_band = np.random.choice(AGE_BANDS, p=AGE_BAND_WEIGHTS)
                    gender = np.random.choice(GENDERS, p=GENDER_WEIGHTS)
                    t_type = random.choice(TEST_TYPES[disease])
                    
                    # Generate deterministic synthetic patient identifier
                    raw_simulated_cnic = f"13101{random.randint(1000000, 9999999)}1"
                    p_hash = hash_patient_id(raw_simulated_cnic, district_salt=pcode)

                    rec = {
                        "external_record_id": ext_id,
                        "test_date": t_date.isoformat(),
                        "epi_week": week,
                        "epi_year": CALIBRATION_YEAR,
                        "facility_name": primary_fac,
                        "facility_id": primary_fac_id,
                        "district_pcode": pcode,
                        "district_name": meta["name"],
                        "division": meta["division"],
                        "disease": disease,
                        "test_type": t_type,
                        "test_result": res,
                        "case_status": "confirmed" if res == "Positive" else "suspected",
                        "age_band": age_band,
                        "gender": gender,
                        "patient_hash": p_hash,
                        "is_corrected": False,
                        "corrected_at": None,
                        "source_type": "synthetic_demo"
                    }

                    all_rows.append(rec)
                    if is_spotlight:
                        fname = SPOTLIGHT_FACILITIES[pcode]["file_name"]
                        spotlight_rows[fname].append(rec)

    spotlight_dfs = {fname: pd.DataFrame(rows) for fname, rows in spotlight_rows.items()}
    all_df = pd.DataFrame(all_rows)
    return spotlight_dfs, all_df


def generate_edge_case_fixtures(out_dir: Path):
    """
    Generates controlled edge case test fixtures in data/demo_hospitals/:
      1. edge_cases_invalid.csv
      2. edge_cases_duplicates.csv
      3. edge_cases_late_labs.csv
      4. edge_cases_missing_vs_zero.csv
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    # -----------------------------------------------------------------
    # FIXTURE 1: edge_cases_invalid.csv
    # Contains corrupt dates, future dates, illegal districts, unknown diseases,
    # and intentional raw PII column check.
    # -----------------------------------------------------------------
    invalid_rows = [
        # Missing external_record_id
        {
            "external_record_id": "",
            "test_date": "2025-05-15",
            "facility_name": "Ayub Teaching Hospital",
            "district": "Abbottabad",
            "disease": "Malaria",
            "test_type": "RDT",
            "test_result": "Positive",
            "age_band": "25-44",
            "gender": "Male",
            "patient_hash": "a" * 64,
            "source_type": "synthetic_demo"
        },
        # Future date beyond 2026
        {
            "external_record_id": "ERR-FUTURE-001",
            "test_date": "2030-08-20",
            "facility_name": "DHQ Hospital Swat",
            "district": "Swat",
            "disease": "Typhoid",
            "test_type": "Blood Culture",
            "test_result": "Positive",
            "age_band": "15-24",
            "gender": "Female",
            "patient_hash": "b" * 64,
            "source_type": "synthetic_demo"
        },
        # Corrupt calendar date
        {
            "external_record_id": "ERR-DATE-002",
            "test_date": "2025-02-31",
            "facility_name": "DHQ Hospital Haripur",
            "district": "Haripur",
            "disease": "Malaria",
            "test_type": "RDT",
            "test_result": "Negative",
            "age_band": "5-14",
            "gender": "Male",
            "patient_hash": "c" * 64,
            "source_type": "synthetic_demo"
        },
        # Unresolvable fictitious district
        {
            "external_record_id": "ERR-DIST-003",
            "test_date": "2025-05-12",
            "facility_name": "Atlantis Regional Center",
            "district": "Atlantis",
            "disease": "Malaria",
            "test_type": "RDT",
            "test_result": "Positive",
            "age_band": "25-44",
            "gender": "Male",
            "patient_hash": "d" * 64,
            "source_type": "synthetic_demo"
        },
        # Unsupported disease condition
        {
            "external_record_id": "ERR-DIS-004",
            "test_date": "2025-05-14",
            "facility_name": "DHQ Hospital Mansehra",
            "district": "Mansehra",
            "disease": "Vampirism",
            "test_type": "PCR",
            "test_result": "Positive",
            "age_band": "45-64",
            "gender": "Female",
            "patient_hash": "e" * 64,
            "source_type": "synthetic_demo"
        },
        # Invalid test result string
        {
            "external_record_id": "ERR-RES-005",
            "test_date": "2025-05-16",
            "facility_name": "DHQ Hospital Timergara",
            "district": "Lower Dir",
            "disease": "Typhoid",
            "test_type": "Widal",
            "test_result": "Maybe",
            "age_band": "25-44",
            "gender": "Male",
            "patient_hash": "f" * 64,
            "source_type": "synthetic_demo"
        },
        # Raw PII Column header violation check
        {
            "external_record_id": "ERR-PII-006",
            "PATIENT_NAME": "Muhammad Ali", # Direct PII
            "test_date": "2025-05-18",
            "facility_name": "Ayub Teaching Hospital",
            "district": "Abbottabad",
            "disease": "Malaria",
            "test_type": "RDT",
            "test_result": "Positive",
            "age_band": "25-44",
            "gender": "Male",
            "patient_hash": "1" * 64,
            "source_type": "synthetic_demo"
        }
    ]
    pd.DataFrame(invalid_rows).to_csv(out_dir / "edge_cases_invalid.csv", index=False)

    # -----------------------------------------------------------------
    # FIXTURE 2: edge_cases_duplicates.csv
    # Exact duplicate submissions + Repeat positive tests within episode window (30d Malaria, 42d Typhoid)
    # + A repeat test after window (new episode).
    # -----------------------------------------------------------------
    test_patient_hash_malaria = hash_patient_id("1310111111111", district_salt="PK501")
    test_patient_hash_typhoid = hash_patient_id("1310122222222", district_salt="PK532")

    duplicate_rows = [
        # Record 1: Initial Malaria positive on Day 1
        {
            "external_record_id": "MAL-EP-001",
            "test_date": "2025-05-01",
            "facility_name": "Ayub Teaching Hospital",
            "district": "Abbottabad",
            "disease": "Malaria",
            "test_type": "Microscopy",
            "test_result": "Positive",
            "age_band": "25-44",
            "gender": "Male",
            "patient_hash": test_patient_hash_malaria,
            "is_corrected": False,
            "source_type": "synthetic_demo"
        },
        # Record 2: Exact duplicate submission of MAL-EP-001 (same ID, date, result)
        {
            "external_record_id": "MAL-EP-001",
            "test_date": "2025-05-01",
            "facility_name": "Ayub Teaching Hospital",
            "district": "Abbottabad",
            "disease": "Malaria",
            "test_type": "Microscopy",
            "test_result": "Positive",
            "age_band": "25-44",
            "gender": "Male",
            "patient_hash": test_patient_hash_malaria,
            "is_corrected": False,
            "source_type": "synthetic_demo"
        },
        # Record 3: Repeat positive test on Day 12 (within 30d window) -> Must be flagged is_duplicate_test=True
        {
            "external_record_id": "MAL-EP-002",
            "test_date": "2025-05-13",
            "facility_name": "Ayub Teaching Hospital",
            "district": "Abbottabad",
            "disease": "Malaria",
            "test_type": "RDT",
            "test_result": "Positive",
            "age_band": "25-44",
            "gender": "Male",
            "patient_hash": test_patient_hash_malaria,
            "is_corrected": False,
            "source_type": "synthetic_demo"
        },
        # Record 4: Repeat positive test on Day 45 (outside 30d window) -> New clinical episode
        {
            "external_record_id": "MAL-EP-003",
            "test_date": "2025-06-15",
            "facility_name": "Ayub Teaching Hospital",
            "district": "Abbottabad",
            "disease": "Malaria",
            "test_type": "Microscopy",
            "test_result": "Positive",
            "age_band": "25-44",
            "gender": "Male",
            "patient_hash": test_patient_hash_malaria,
            "is_corrected": False,
            "source_type": "synthetic_demo"
        },
        # Record 5: Typhoid positive test on Day 1
        {
            "external_record_id": "TYP-EP-001",
            "test_date": "2025-05-02",
            "facility_name": "Saidu Teaching & DHQ Hospital Swat",
            "district": "Swat",
            "disease": "Typhoid",
            "test_type": "Blood Culture",
            "test_result": "Positive",
            "age_band": "15-24",
            "gender": "Female",
            "patient_hash": test_patient_hash_typhoid,
            "is_corrected": False,
            "source_type": "synthetic_demo"
        },
        # Record 6: Typhoid repeat positive test on Day 35 (within 42d window) -> is_duplicate_test=True
        {
            "external_record_id": "TYP-EP-002",
            "test_date": "2025-06-06",
            "facility_name": "Saidu Teaching & DHQ Hospital Swat",
            "district": "Swat",
            "disease": "Typhoid",
            "test_type": "Typhidot",
            "test_result": "Positive",
            "age_band": "15-24",
            "gender": "Female",
            "patient_hash": test_patient_hash_typhoid,
            "is_corrected": False,
            "source_type": "synthetic_demo"
        }
    ]
    pd.DataFrame(duplicate_rows).to_csv(out_dir / "edge_cases_duplicates.csv", index=False)

    # -----------------------------------------------------------------
    # FIXTURE 3: edge_cases_late_labs.csv
    # Preliminary preliminary / indeterminate / suspected results later corrected
    # via matching external_record_id and is_corrected=True.
    # -----------------------------------------------------------------
    patient_corr_1 = hash_patient_id("1310133333333", district_salt="PK520")
    patient_corr_2 = hash_patient_id("1310144444444", district_salt="PK511")

    late_lab_rows = [
        # Preliminary 1: Indeterminate blood culture on May 10
        {
            "external_record_id": "CORR-REQ-101",
            "test_date": "2025-05-10",
            "facility_name": "DHQ Hospital Timergara",
            "district": "Lower Dir",
            "disease": "Typhoid",
            "test_type": "Blood Culture",
            "test_result": "Indeterminate",
            "case_status": "suspected",
            "age_band": "5-14",
            "gender": "Male",
            "patient_hash": patient_corr_1,
            "is_corrected": False,
            "corrected_at": None,
            "source_type": "synthetic_demo"
        },
        # Corrected 1: Late confirmatory report supersedes on May 13 to Positive
        {
            "external_record_id": "CORR-REQ-101",
            "test_date": "2025-05-10",
            "facility_name": "DHQ Hospital Timergara",
            "district": "Lower Dir",
            "disease": "Typhoid",
            "test_type": "Blood Culture",
            "test_result": "Positive",
            "case_status": "confirmed",
            "age_band": "5-14",
            "gender": "Male",
            "patient_hash": patient_corr_1,
            "is_corrected": True,
            "corrected_at": "2025-05-13 11:30:00",
            "source_type": "synthetic_demo"
        },
        # Preliminary 2: Rapid test on May 12 reported Positive
        {
            "external_record_id": "CORR-REQ-202",
            "test_date": "2025-05-12",
            "facility_name": "DHQ Hospital Haripur",
            "district": "Haripur",
            "disease": "Malaria",
            "test_type": "RDT",
            "test_result": "Positive",
            "case_status": "confirmed",
            "age_band": "25-44",
            "gender": "Female",
            "patient_hash": patient_corr_2,
            "is_corrected": False,
            "corrected_at": None,
            "source_type": "synthetic_demo"
        },
        # Corrected 2: Microscopy confirms False Positive (re-classified to Negative on May 14)
        {
            "external_record_id": "CORR-REQ-202",
            "test_date": "2025-05-12",
            "facility_name": "DHQ Hospital Haripur",
            "district": "Haripur",
            "disease": "Malaria",
            "test_type": "Microscopy Confirmed",
            "test_result": "Negative",
            "case_status": "suspected",
            "age_band": "25-44",
            "gender": "Female",
            "patient_hash": patient_corr_2,
            "is_corrected": True,
            "corrected_at": "2025-05-14 16:45:00",
            "source_type": "synthetic_demo"
        }
    ]
    pd.DataFrame(late_lab_rows).to_csv(out_dir / "edge_cases_late_labs.csv", index=False)

    # -----------------------------------------------------------------
    # FIXTURE 4: edge_cases_missing_vs_zero.csv
    # Explicit facility zero-case submission vs facility non-reporting gap
    # -----------------------------------------------------------------
    missing_vs_zero_rows = []
    # Facility A: Active negative surveillance (30 negative tests, 0 positive)
    for i in range(25):
        missing_vs_zero_rows.append({
            "external_record_id": f"SURV-ZERO-A-{i:03d}",
            "test_date": "2025-05-20",
            "facility_name": "Mansehra District Public Health Diagnostic Lab",
            "district": "Mansehra",
            "disease": "Malaria",
            "test_type": "Microscopy",
            "test_result": "Negative",
            "case_status": "suspected",
            "age_band": "25-44",
            "gender": "Male",
            "patient_hash": hash_patient_id(f"13101888{i:05d}", district_salt="PK522"),
            "is_corrected": False,
            "source_type": "synthetic_demo",
            "reporting_status": "submitted_active_zero"
        })
    # Facility B: Another facility in district submitted positive cases
    for i in range(5):
        missing_vs_zero_rows.append({
            "external_record_id": f"SURV-POS-B-{i:03d}",
            "test_date": "2025-05-20",
            "facility_name": "District Headquarter (DHQ) Hospital Mansehra",
            "district": "Mansehra",
            "disease": "Malaria",
            "test_type": "RDT",
            "test_result": "Positive",
            "case_status": "confirmed",
            "age_band": "15-24",
            "gender": "Female",
            "patient_hash": hash_patient_id(f"13101999{i:05d}", district_salt="PK522"),
            "is_corrected": False,
            "source_type": "synthetic_demo",
            "reporting_status": "submitted_positive"
        })
    # Note: Facility C in Mansehra ("THQ Balakot") submitted ZERO files (Unsubmitted/Missing Report)
    pd.DataFrame(missing_vs_zero_rows).to_csv(out_dir / "edge_cases_missing_vs_zero.csv", index=False)


def run_generator():
    print("=" * 70)
    print("RUNNING CALIBRATED SYNTHETIC HOSPITAL / LAB GENERATOR")
    print("=" * 70)

    out_dir = WORKSPACE_DIR / "data" / "demo_hospitals"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Build facilities master list
    print("\n[1/4] Generating Khyber Pakhtunkhwa Health Facilities Master List...")
    df_facilities = build_facility_master()
    fac_csv = out_dir / "facilities_kp.csv"
    df_facilities.to_csv(fac_csv, index=False)
    print(f"  -> Generated {len(df_facilities)} facilities across 35 KP districts.")
    print(f"  -> Saved: {fac_csv}")

    # 2. Ingest IDSR weekly panel for ground-truth calibration
    print("\n[2/4] Reading IDSR Panel to Calibrate 2025 Weeks 20-24 Counts...")
    panel_csv = WORKSPACE_DIR / "data" / "processed" / "idsr_weekly_panel.csv"
    df_panel = pd.read_csv(panel_csv)

    # 3. Generate Spotlight Hospital CSVs & Provincial Demo Panel
    print("\n[3/4] Generating Spotlight Hospital Records (Zero-PII, Calibrated)...")
    spotlight_dfs, all_kp_df = generate_calibrated_records(df_panel, df_facilities)

    for fname, df_spot in spotlight_dfs.items():
        fpath = out_dir / fname
        df_spot.to_csv(fpath, index=False)
        pos = (df_spot["test_result"] == "Positive").sum()
        total = len(df_spot)
        print(f"  -> {fname}: {total:,} tests ({pos:,} confirmed positive, {pos/total:.1%} pos rate) -> {fpath.name}")

    # Save provincial consolidated demo file
    all_demo_path = out_dir / "kp_demo_lab_records.csv"
    all_kp_df.to_csv(all_demo_path, index=False)
    print(f"  -> Consolidated Provincial Demo Lab Records: {len(all_kp_df):,} rows -> {all_demo_path.name}")

    # 4. Generate Edge-Case Fixtures
    print("\n[4/4] Generating Controlled Edge-Case Fixtures...")
    generate_edge_case_fixtures(out_dir)
    print(f"  -> edge_cases_invalid.csv")
    print(f"  -> edge_cases_duplicates.csv")
    print(f"  -> edge_cases_late_labs.csv")
    print(f"  -> edge_cases_missing_vs_zero.csv")

    print("\n" + "=" * 70)
    print("CALIBRATED SYNTHETIC GENERATION COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    run_generator()
