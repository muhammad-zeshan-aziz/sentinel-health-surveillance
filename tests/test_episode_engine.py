"""
Module 3: Disease-Specific Episode Deduplication & Corrections Tests.
Verifies 30-day Malaria and 42-day Typhoid deduplication windows,
handling of late-arriving corrected lab results, and test volume accounting.
"""

from datetime import date
from src.ingestion.episode_engine import EpisodeEngine

def test_malaria_30_day_deduplication():
    engine = EpisodeEngine()
    patient = "hash_patient_malaria_001"
    disease = "Malaria"

    records = [
        # Day 0: First positive test
        {
            "external_record_id": "EXT-M-01",
            "patient_hash": patient,
            "disease": disease,
            "test_date": date(2026, 5, 1),
            "test_result": "Positive",
            "is_corrected": False
        },
        # Day 15: Repeat positive test within 30 days
        {
            "external_record_id": "EXT-M-02",
            "patient_hash": patient,
            "disease": disease,
            "test_date": date(2026, 5, 16),
            "test_result": "Positive",
            "is_corrected": False
        },
        # Day 45: New positive test outside 30 days (>30d)
        {
            "external_record_id": "EXT-M-03",
            "patient_hash": patient,
            "disease": disease,
            "test_date": date(2026, 6, 15),
            "test_result": "Positive",
            "is_corrected": False
        }
    ]

    df = engine.process_records(records)
    assert len(df) == 3, "All records remain in total test volume"

    # Record 1: New episode
    r1 = df[df["external_record_id"] == "EXT-M-01"].iloc[0]
    assert not r1["is_duplicate_test"]
    assert r1["is_new_episode"]
    ep1_id = r1["episode_id"]

    # Record 2: Repeat within 30 days
    r2 = df[df["external_record_id"] == "EXT-M-02"].iloc[0]
    assert r2["is_duplicate_test"], "Repeat test within 30 days must be duplicate"
    assert not r2["is_new_episode"], "Must not be a new episode"
    assert r2["episode_id"] == ep1_id, "Must share the same episode ID"

    # Record 3: Beyond 30 days
    r3 = df[df["external_record_id"] == "EXT-M-03"].iloc[0]
    assert not r3["is_duplicate_test"]
    assert r3["is_new_episode"]
    assert r3["episode_id"] != ep1_id

def test_typhoid_42_day_deduplication():
    engine = EpisodeEngine()
    patient = "hash_patient_typhoid_001"
    disease = "Typhoid"

    records = [
        # Day 0: Initial
        {
            "external_record_id": "EXT-T-01",
            "patient_hash": patient,
            "disease": disease,
            "test_date": date(2026, 3, 1),
            "test_result": "Positive",
            "is_corrected": False
        },
        # Day 35: Repeat positive test within 42 days
        {
            "external_record_id": "EXT-T-02",
            "patient_hash": patient,
            "disease": disease,
            "test_date": date(2026, 4, 5),
            "test_result": "Positive",
            "is_corrected": False
        },
        # Day 50: Positive test after 42 days
        {
            "external_record_id": "EXT-T-03",
            "patient_hash": patient,
            "disease": disease,
            "test_date": date(2026, 4, 25),
            "test_result": "Positive",
            "is_corrected": False
        }
    ]

    df = engine.process_records(records)
    r1 = df[df["external_record_id"] == "EXT-T-01"].iloc[0]
    r2 = df[df["external_record_id"] == "EXT-T-02"].iloc[0]
    r3 = df[df["external_record_id"] == "EXT-T-03"].iloc[0]

    assert r1["is_new_episode"]
    assert r2["is_duplicate_test"]
    assert not r2["is_new_episode"]
    assert r3["is_new_episode"]

def test_late_arriving_correction_supersedes():
    engine = EpisodeEngine()
    patient = "hash_correction_test"

    records = [
        {
            "external_record_id": "EXT-CORR-01",
            "patient_hash": patient,
            "disease": "Malaria",
            "test_date": date(2026, 5, 10),
            "test_result": "Positive",
            "is_corrected": False
        },
        {
            "external_record_id": "EXT-CORR-01",
            "patient_hash": patient,
            "disease": "Malaria",
            "test_date": date(2026, 5, 10),
            "test_result": "Negative",
            "is_corrected": True
        }
    ]

    df = engine.process_records(records)
    # The late correction with is_corrected=True must supersede the preliminary record
    assert len(df) == 1, "Corrected record supersedes preliminary without duplicate count"
    assert df.iloc[0]["test_result"] == "Negative"
    assert df.iloc[0]["is_corrected"] == True
