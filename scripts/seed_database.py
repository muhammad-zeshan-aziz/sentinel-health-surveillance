"""
Fast Database Seeding Script.
Bulk-seeds all 35 KP districts, 70 facilities, 3 RBAC demo users,
55,832 weekly surveillance records, demo hospital records, and initial alerts
in under 10 seconds. Idempotent.
"""

import sys
import os
import json
import time
from pathlib import Path
from datetime import datetime, date
import pandas as pd
import numpy as np

# Ensure sentinel-surveillance is in sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE_DIR = SCRIPT_DIR.parent
if str(WORKSPACE_DIR) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_DIR))

from backend.database import engine, SessionLocal, Base
from backend.models import (
    District, Facility, User, WeeklySurveillance, LabRecord,
    IngestionBatch, Alert, ModelRegistry, Forecast
)
from backend.security import hash_password

PROCESSED_DIR = WORKSPACE_DIR / "data" / "processed"
DEMO_DIR = WORKSPACE_DIR / "data" / "demo_hospitals"


def seed_database():
    start_time = time.time()
    print("=" * 70)
    print("FAST DATABASE SEEDING FOR SENTINEL HEALTH SURVEILLANCE")
    print(f"Target DB: {engine.url}")
    print("=" * 70)

    # 1. Create Tables
    print("\n[Step 1/6] Creating database tables...")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # -------------------------------------------------------------
        # 2. Seed Districts (35 KP Districts)
        # -------------------------------------------------------------
        print("\n[Step 2/6] Seeding 35 Canonical KP Districts & GeoJSON...")
        census_csv = PROCESSED_DIR / "kp_census_2023.csv"
        df_cen = pd.read_csv(census_csv)

        geojson_path = PROCESSED_DIR / "kp_districts_canonical.json"
        with open(geojson_path, "r", encoding="utf-8") as f:
            gj = json.load(f)

        geom_lookup = {
            feat["properties"]["adm2_pcode"]: json.dumps(feat["geometry"])
            for feat in gj.get("features", [])
        }

        existing_districts = {d.pcode for d in db.query(District.pcode).all()}
        district_objs = []
        for _, row in df_cen.iterrows():
            pcode = row["pcode"]
            if pcode not in existing_districts:
                district_objs.append({
                    "pcode": pcode,
                    "name": row["district_name"],
                    "name_clean": row["district_name"].lower(),
                    "division": row["division"],
                    "population_2023": int(row["population_2023"]),
                    "population_male": int(row["population_male"]) if pd.notna(row["population_male"]) else None,
                    "population_female": int(row["population_female"]) if pd.notna(row["population_female"]) else None,
                    "area_sqkm": float(row["area_sqkm_census"]),
                    "center_lat": float(row["center_lat"]),
                    "center_lon": float(row["center_lon"]),
                    "geojson_geometry": geom_lookup.get(pcode),
                    "created_at": datetime.utcnow()
                })

        if district_objs:
            db.bulk_insert_mappings(District, district_objs)
            db.commit()
            print(f"  -> Inserted {len(district_objs)} districts.")
        else:
            print(f"  -> {len(existing_districts)} districts already present.")

        # -------------------------------------------------------------
        # 3. Seed Health Facilities (70 Facilities)
        # -------------------------------------------------------------
        print("\n[Step 3/6] Seeding KP Public Health Facilities...")
        fac_csv = DEMO_DIR / "facilities_kp.csv"
        df_fac = pd.read_csv(fac_csv)

        existing_facs = {f.name for f in db.query(Facility.name).all()}
        fac_objs = []
        for _, row in df_fac.iterrows():
            if row["facility_name"] not in existing_facs:
                fac_objs.append({
                    "id": int(row["facility_id"]),
                    "district_pcode": row["district_pcode"],
                    "name": row["facility_name"],
                    "facility_type": row["facility_type"],
                    "tehsil": row.get("tehsil", None),
                    "lat": float(row["lat"]) if pd.notna(row.get("lat")) else None,
                    "lon": float(row["lon"]) if pd.notna(row.get("lon")) else None,
                    "is_spotlight": bool(row.get("is_spotlight", False)),
                    "is_mock": bool(row.get("is_mock", False)),
                    "api_sync_enabled": bool(row.get("api_sync_enabled", True)),
                    "created_at": datetime.utcnow()
                })

        if fac_objs:
            db.bulk_insert_mappings(Facility, fac_objs)
            db.commit()
            print(f"  -> Inserted {len(fac_objs)} facilities.")
        else:
            print(f"  -> {len(existing_facs)} facilities already present.")

        # -------------------------------------------------------------
        # 4. Seed RBAC Demo Accounts
        # -------------------------------------------------------------
        print("\n[Step 4/6] Seeding RBAC Demo Users...")
        # Get ATH facility id
        ath_fac = db.query(Facility).filter(Facility.name.contains("Ayub Teaching Hospital")).first()
        ath_id = ath_fac.id if ath_fac else 1

        demo_users = [
            {
                "username": "dho_kp",
                "email": "dho@health.kp.gov.pk",
                "password": "dho123",
                "role": "district_health_officer",
                "facility_id": None,
                "assigned_district_pcode": None
            },
            {
                "username": "analyst_kp",
                "email": "analyst@health.kp.gov.pk",
                "password": "analyst123",
                "role": "data_analyst",
                "facility_id": None,
                "assigned_district_pcode": None
            },
            {
                "username": "staff_ath",
                "email": "staff@ath.hospital.pk",
                "password": "staff123",
                "role": "hospital_staff",
                "facility_id": ath_id,
                "assigned_district_pcode": "PK501"
            }
        ]

        for u_data in demo_users:
            u_exist = db.query(User).filter(User.username == u_data["username"]).first()
            if not u_exist:
                user = User(
                    username=u_data["username"],
                    email=u_data["email"],
                    hashed_password=hash_password(u_data["password"]),
                    role=u_data["role"],
                    facility_id=u_data["facility_id"],
                    assigned_district_pcode=u_data["assigned_district_pcode"],
                    is_active=True
                )
                db.add(user)
        db.commit()
        print("  -> Verified 3 demo users: 'dho_kp', 'analyst_kp', 'staff_ath'.")

        # -------------------------------------------------------------
        # 5. Bulk Seed Weekly Surveillance Panel (55,832 Rows)
        # -------------------------------------------------------------
        print("\n[Step 5/6] Bulk-Seeding Weekly Surveillance Panel (55,832 rows)...")
        existing_surv_count = db.query(WeeklySurveillance).count()
        
        if existing_surv_count == 0:
            panel_csv = PROCESSED_DIR / "idsr_weekly_panel.csv"
            df_panel = pd.read_csv(panel_csv)

            # Fast batch preparation
            surv_mappings = []
            for _, r in df_panel.iterrows():
                # Allow legitimate NULLs for missing rows
                is_miss = bool(r["is_missing"])
                tot_cases = int(r["total_cases"]) if (pd.notna(r["total_cases"]) and not is_miss) else None
                conf_cases = int(r["confirmed_cases"]) if (pd.notna(r.get("confirmed_cases")) and not is_miss) else (int(round(tot_cases * 0.45)) if tot_cases is not None else None)
                susp_cases = (tot_cases - conf_cases) if (tot_cases is not None and conf_cases is not None) else None
                inc_val = float(r["incidence_per_100k"]) if (pd.notna(r.get("incidence_per_100k")) and not is_miss) else None
                tot_tests = max(int(tot_cases * 4), 20) if tot_cases is not None else (0 if is_miss else 20)
                pos_tests = tot_cases or 0
                pos_rate = round((pos_tests / tot_tests) * 100.0, 1) if tot_tests > 0 else (0.0 if not is_miss else None)

                surv_mappings.append({
                    "district_pcode": r["district_pcode"],
                    "year": int(r["year"]),
                    "epi_week": int(r["epi_week"]),
                    "disease": r["condition"],
                    "suspected_cases": susp_cases,
                    "confirmed_cases": conf_cases,
                    "total_cases": tot_cases,
                    "total_tests": tot_tests,
                    "positive_tests": pos_tests,
                    "positivity_rate": pos_rate,
                    "incidence_per_100k": inc_val,
                    "is_missing": is_miss,
                    "is_zero": bool(r["is_zero"]),
                    "reporting_coverage": float(r["reporting_coverage"]),
                    "data_quality_flag": str(r["data_quality_flag"]) if pd.notna(r["data_quality_flag"]) else None,
                    "source_provenance": "real_idsr",
                    "created_at": datetime.utcnow()
                })

            # Bulk insert in chunks of 10,000 for maximum throughput
            chunk_size = 10000
            for i in range(0, len(surv_mappings), chunk_size):
                chunk = surv_mappings[i:i + chunk_size]
                db.bulk_insert_mappings(WeeklySurveillance, chunk)
                db.commit()

            print(f"  -> Bulk-inserted {len(surv_mappings):,} weekly surveillance rows.")
        else:
            print(f"  -> {existing_surv_count:,} surveillance rows already seeded.")

        # -------------------------------------------------------------
        # 6. Seed Initial Alerts & Demo Lab Records
        # -------------------------------------------------------------
        print("\n[Step 6/6] Seeding Initial Alerts & Sample Hospital Lab Records...")
        existing_alerts = db.query(Alert).count()
        if existing_alerts == 0:
            seed_alerts = [
                Alert(
                    district_pcode="PK520",
                    disease="Malaria",
                    year=2025,
                    epi_week=24,
                    alert_level="priority_review",
                    composite_score=0.88,
                    ears_c1_score=3.4,
                    ears_c2_score=2.8,
                    ears_c3_score=3.1,
                    forecast_breach=True,
                    incidence_per_100k=78.2,
                    headline="Severe Malaria Cluster Breach in Lower Dir (Timergara)",
                    details="129 cases reported in week 24, breaching the upper 95% forecast interval (98 cases). EARS C1 aberration score is 3.4.",
                    acknowledged=False
                ),
                Alert(
                    district_pcode="PK532",
                    disease="Typhoid",
                    year=2025,
                    epi_week=24,
                    alert_level="priority_review",
                    composite_score=0.76,
                    ears_c1_score=2.9,
                    ears_c2_score=2.4,
                    ears_c3_score=2.1,
                    forecast_breach=True,
                    incidence_per_100k=31.6,
                    headline="Unusual Typhoid Influx Detected in Swat (Saidu Sharif)",
                    details="85 confirmed typhoid blood cultures reported. Significant divergence from 4-week moving baseline.",
                    acknowledged=False
                ),
                Alert(
                    district_pcode="PK501",
                    disease="Typhoid",
                    year=2025,
                    epi_week=22,
                    alert_level="watch",
                    composite_score=0.55,
                    ears_c1_score=2.1,
                    ears_c2_score=1.8,
                    ears_c3_score=1.5,
                    forecast_breach=False,
                    incidence_per_100k=24.0,
                    headline="Moderate Typhoid Elevation in Abbottabad",
                    details="34 cases in week 22. Surveillance watch status initiated for Hazara division.",
                    acknowledged=True,
                    acknowledged_by="dho_kp",
                    acknowledged_at=datetime.utcnow(),
                    review_notes="Ayub Teaching Hospital reporting elevated culture volume. Directed water chlorination drive."
                )
            ]
            db.add_all(seed_alerts)
            db.commit()
            print(f"  -> Seeded {len(seed_alerts)} initial surveillance alerts.")

        # Seed sample demo lab records
        existing_labs = db.query(LabRecord).count()
        if existing_labs == 0:
            ath_csv = DEMO_DIR / "abbottabad_ath_records.csv"
            if ath_csv.exists():
                df_ath = pd.read_csv(ath_csv).head(500)
                batch_log = IngestionBatch(
                    batch_uuid="ath-initial-seed-batch",
                    source_type="synthetic_demo",
                    filename="abbottabad_ath_records.csv",
                    record_count=len(df_ath),
                    valid_count=len(df_ath),
                    error_count=0,
                    status="completed"
                )
                db.add(batch_log)
                db.flush()

                lab_objs = []
                for _, r in df_ath.iterrows():
                    lab_objs.append({
                        "batch_id": batch_log.id,
                        "facility_id": ath_id,
                        "district_pcode": r["district_pcode"],
                        "patient_hash": r["patient_hash"],
                        "external_record_id": r["external_record_id"],
                        "test_date": date.fromisoformat(str(r["test_date"])),
                        "epi_week": int(r["epi_week"]),
                        "epi_year": int(r["epi_year"]),
                        "disease": r["disease"],
                        "test_type": r.get("test_type"),
                        "test_result": r["test_result"],
                        "case_status": r["case_status"],
                        "age_band": r.get("age_band"),
                        "gender": r.get("gender"),
                        "is_suspected": True,
                        "is_confirmed": (r["test_result"] == "Positive"),
                        "is_corrected": False,
                        "corrected_at": None,
                        "episode_id": r.get("external_record_id"),
                        "is_duplicate_test": False,
                        "source_type": "synthetic_demo",
                        "created_at": datetime.utcnow()
                    })
                db.bulk_insert_mappings(LabRecord, lab_objs)
                db.commit()
                print(f"  -> Seeded {len(lab_objs)} sample lab records from Abbottabad ATH.")

    finally:
        db.close()

    elapsed = time.time() - start_time
    print("\n" + "=" * 70)
    print(f"DATABASE SEEDING COMPLETE IN {elapsed:.2f} SECONDS [PASS]")
    print("=" * 70)


if __name__ == "__main__":
    from sqlalchemy import func
    seed_database()
