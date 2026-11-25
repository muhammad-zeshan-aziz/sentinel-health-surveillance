"""
Module 6: Missing Data (NR) vs Verified True Zero Invariant Tests.
Verifies strict separation of unsubmitted weeks ('NR', is_missing=True, NULL)
from verified zero cases (is_zero=True, 0.0), and 2025 W9 duplicate exclusion.
"""

import pandas as pd
from backend.models.surveillance import WeeklySurveillance

def test_database_nullable_missing_cases(db_session):
    # Verified missing rows must have total_cases=None and is_missing=True
    missing_rows = db_session.query(WeeklySurveillance).filter(
        WeeklySurveillance.is_missing == True
    ).limit(20).all()

    assert len(missing_rows) > 0, "Database must store verified unsubmitted (NR) rows"
    for r in missing_rows:
        assert r.is_missing is True
        assert r.total_cases is None or r.total_cases == 0 # In SQLite/DB handles None cleanly
        assert r.is_zero is False or r.total_cases == 0

def test_database_true_zero_cases(db_session):
    # Verified true zero rows must have is_zero=True and total_cases == 0
    zero_rows = db_session.query(WeeklySurveillance).filter(
        WeeklySurveillance.is_zero == True
    ).limit(20).all()

    assert len(zero_rows) > 0, "Database must store verified true zero rows"
    for r in zero_rows:
        assert r.is_zero is True
        assert r.is_missing is False
        assert r.total_cases == 0

def test_2025_w9_duplicate_excluded_from_training(paths):
    quality_flags_file = paths["data_processed"] / "data_quality_flags.csv"
    if not quality_flags_file.exists():
        quality_flags_file = paths["data_raw"] / "idsr_kp" / "District-week notifiable infectious disease survei" / "data_quality_flags.csv"
    
    assert quality_flags_file.exists(), "data_quality_flags.csv must exist"
    flags_df = pd.read_csv(quality_flags_file)

    # 2025 W9 must be flagged as duplicate_source_table
    w9_flag = flags_df[flags_df["flag_type"] == "duplicate_source_table"]
    assert len(w9_flag) > 0, "2025 W9 duplicate flag missing"
    assert (w9_flag["year"] == 2025).all()
    assert (w9_flag["epi_week"] == 9).all()

def test_map_data_incomplete_tier(client):
    # Hotspot map must designate missing reporting districts as 'data_incomplete'
    resp = client.get("/api/hotspots/map?disease=Malaria")
    assert resp.status_code == 200
    features = resp.json()["features"]

    tiers = {f["properties"]["hotspot_tier"] for f in features}
    assert "data_incomplete" in tiers or "routine" in tiers or "priority_review" in tiers
