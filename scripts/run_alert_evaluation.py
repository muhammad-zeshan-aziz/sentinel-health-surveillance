"""
Comprehensive Alert Evaluation, Hotspot Scoring & Database Seeding (Phase 5).
Generates EARS C1/C2/C3 statistics, observed & forecast hotspot assessments,
disaggregated backtesting results for Malaria & Typhoid, and seeds live database alerts.
"""

import sys
import os
import json
from pathlib import Path
from datetime import datetime
import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE_DIR = SCRIPT_DIR.parent
if str(WORKSPACE_DIR) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_DIR))

from src.surveillance.ears_detector import EARSDetector
from src.surveillance.hotspot_engine import HotspotEngine, DualLayerHotspotMap, DistrictHotspotAssessment
from src.surveillance.backtester import AlertBacktester, evaluate_all_diseases

from backend.database import SessionLocal
from backend.models.alert import Alert
from backend.models.district import District
from backend.models.ml import Forecast

PROCESSED_DIR = WORKSPACE_DIR / "data" / "processed"


def run_full_surveillance_pipeline():
    print("=" * 80)
    print("SENTINEL HEALTH SURVEILLANCE - PHASE 5 OUTBREAK ABERRATION & HOTSPOTS")
    print("EARS C1/C2/C3 Engines, Dual-Layer Hotspot Map & Historical Alert Backtesting")
    print("=" * 80)

    db = SessionLocal()
    engine = HotspotEngine()

    try:
        # -------------------------------------------------------------
        # STEP 1: Run Disaggregated Historical Alert Backtesting
        # -------------------------------------------------------------
        print("\n" + "=" * 50)
        print("[STEP 1/3] Running Historical Alert Backtesting...")
        print("=" * 50)
        backtest_results = evaluate_all_diseases()

        for d_key in ["malaria", "typhoid"]:
            res = backtest_results[d_key]
            m = res["metrics"]
            print(f"\n  -- {d_key.upper()} BACKTEST PERFORMANCE --")
            print(f"  Precision                       : {m['precision']:.1%}")
            print(f"  Recall                          : {m['recall']:.1%}")
            print(f"  Outbreaks (Detected / Total)    : {m['detected_outbreaks']} / {m['total_outbreaks']}")
            print(f"  Alerts (True / False / Total)   : {m['true_alerts']} / {m['false_alerts']} / {m['total_alerts']}")
            print(f"  False Alert Frequency (per yr)  : {m['false_alert_freq_per_district_year']:.1f} per district-year")
            print(f"  Average Lead Time               : {m['average_lead_time_weeks']:.1f} weeks before outbreak peak")

        # -------------------------------------------------------------
        # STEP 2: Assess Latest Surveillance Week for Dual-Layer Hotspots
        # -------------------------------------------------------------
        print("\n" + "=" * 50)
        print("[STEP 2/3] Generating Dual-Layer Hotspot Assessments...")
        print("=" * 50)

        panel_file = PROCESSED_DIR / "idsr_weekly_panel.csv"
        df = pd.read_csv(panel_file)
        if "condition" in df.columns and "disease" not in df.columns:
            df["disease"] = df["condition"]

        # Filter out 2025 W9 duplicate
        if "data_quality_flag" in df.columns:
            df = df[~df["data_quality_flag"].astype(str).str.contains("duplicate_source_table", na=False)].copy()

        df["t_idx"] = (df["year"] - 2023) * 52 + df["epi_week"] - 16
        df = df.sort_values(["district_pcode", "t_idx"]).reset_index(drop=True)

        latest_assessments_by_disease: Dict[str, Dict[str, DistrictHotspotAssessment]] = {}

        for disease in ["Malaria", "Typhoid"]:
            d_df = df[df["disease"].str.capitalize() == disease].copy()
            # Fetch latest forecasts from DB
            db_forecasts = db.query(Forecast).filter(Forecast.disease == disease).all()
            forecast_lookup = {f.district_pcode: f for f in db_forecasts}

            disease_asmts: Dict[str, DistrictHotspotAssessment] = {}

            for pcode, grp in d_df.groupby("district_pcode"):
                grp = grp.sort_values("t_idx").reset_index(drop=True)
                d_name = grp["district_name"].iloc[0]
                div = grp["division"].iloc[0]
                pop = float(grp["population_2023"].iloc[0])

                latest_row = grp.iloc[-1]
                t_idx = int(latest_row["t_idx"])
                yr = int(latest_row["year"])
                wk = int(latest_row["epi_week"])
                cur_cases = latest_row["total_cases"]
                is_miss = bool(latest_row["is_missing"]) or (cur_cases is None) or np.isnan(cur_cases)

                cases_hist = grp.iloc[:-1]["total_cases"].tolist()

                # Get Phase 4 forecast
                fc = forecast_lookup.get(pcode)
                fc_mean = fc.predicted_mean if fc else None
                fc_upper = fc.ci_upper_95 if fc else None
                fc_withheld = fc.is_withheld if fc else False

                asmt = engine.assess_district(
                    district_pcode=pcode,
                    district_name=d_name,
                    division=div,
                    disease=disease,
                    year=yr,
                    epi_week=wk,
                    population_2023=pop,
                    current_cases=cur_cases,
                    is_missing=is_miss,
                    history_cases=cases_hist,
                    forecast_mean=fc_mean,
                    forecast_ci_upper=fc_upper,
                    is_forecast_withheld=fc_withheld
                )
                disease_asmts[pcode] = asmt

            latest_assessments_by_disease[disease.lower()] = disease_asmts

            # Build dual-layer GeoJSON
            map_builder = DualLayerHotspotMap()
            geojson = map_builder.build_feature_collection(disease_asmts)

            # Save GeoJSON for fast serving
            out_geojson = PROCESSED_DIR / f"hotspots_map_{disease.lower()}.json"
            with open(out_geojson, "w", encoding="utf-8") as f:
                json.dump(geojson, f, indent=2)

            # Summarize tiers
            tiers = [a.observed_hotspot_tier for a in disease_asmts.values()]
            fc_tiers = [a.forecast_hotspot_tier for a in disease_asmts.values()]
            print(f"  -> {disease} Observed Tiers : {pd.Series(tiers).value_counts().to_dict()}")
            print(f"  -> {disease} Forecast Tiers : {pd.Series(fc_tiers).value_counts().to_dict()}")
            print(f"  -> Saved dual-layer map to: {out_geojson}")

        # -------------------------------------------------------------
        # STEP 3: Seed Live EARS Alerts into Database Table
        # -------------------------------------------------------------
        print("\n" + "=" * 50)
        print("[STEP 3/3] Seeding Live EARS Outbreak Alerts in Database...")
        print("=" * 50)

        # Clear existing alerts
        db.query(Alert).delete()

        alert_entries = []
        alert_id_counter = 1

        for disease_key, asmts in latest_assessments_by_disease.items():
            for pcode, asmt in asmts.items():
                if asmt.observed_hotspot_tier in ["priority_review", "watch"]:
                    # Create actionable alert
                    # Leave first alert unacknowledged for DHO testing
                    is_ack = False
                    ack_by = None
                    ack_at = None
                    notes = None

                    # If lower priority watch in demo, simulate a resolved historical alert
                    if asmt.observed_hotspot_tier == "watch" and alert_id_counter > 3:
                        is_ack = True
                        ack_by = "dho_kp"
                        ack_at = datetime.utcnow()
                        notes = "Routine epidemiological monitoring protocol initiated. Water testing teams dispatched."

                    alert_entries.append(Alert(
                        district_pcode=pcode,
                        disease=asmt.disease,
                        year=asmt.year,
                        epi_week=asmt.epi_week,
                        alert_level=asmt.observed_hotspot_tier,
                        composite_score=asmt.composite_score,
                        ears_c1_score=asmt.ears_z1,
                        ears_c2_score=asmt.ears_z2,
                        ears_c3_score=asmt.ears_c3,
                        forecast_breach=asmt.forecast_breach,
                        incidence_per_100k=asmt.incidence_per_100k or 0.0,
                        headline=asmt.headline,
                        details=asmt.details,
                        acknowledged=is_ack,
                        acknowledged_by=ack_by,
                        acknowledged_at=ack_at,
                        review_notes=notes,
                        created_at=datetime.utcnow()
                    ))
                    alert_id_counter += 1

        db.bulk_save_objects(alert_entries)
        db.commit()

        active_count = sum(1 for a in alert_entries if not a.acknowledged)
        print(f"  -> Inserted {len(alert_entries)} live EARS alerts ({active_count} active / unreviewed).")

        print("\n" + "=" * 80)
        print("PHASE 5 SURVEILLANCE PIPELINE EXECUTION COMPLETED SUCCESSFULLY")
        print("=" * 80)

    finally:
        db.close()


if __name__ == "__main__":
    run_full_surveillance_pipeline()
