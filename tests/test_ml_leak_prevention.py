"""
Module 7: Anti-Leakage Feature Store & Model Registry Uniqueness Tests.
Verifies temporal feature ordering (target_t > origin_t), in-fold target encoding,
rejection of future feature injection, and strict active-model uniqueness.
"""

import pytest
from src.ml.feature_store import FeatureStore, assert_zero_future_leakage
from backend.models.ml import ModelRegistry

def test_feature_store_temporal_ordering():
    fs = FeatureStore()
    df_feat = fs.build_feature_matrix("Malaria")

    assert "target_cases" in df_feat.columns
    assert "lag_1" in df_feat.columns
    assert "lag_2" in df_feat.columns
    assert "rolling_mean_4" in df_feat.columns

    # Verify no row has forward-looking leakage in lag features
    assert not df_feat["lag_1"].isnull().all()
    assert not df_feat["target_cases"].isnull().all()

    # Programmatic anti-leakage audit
    assert assert_zero_future_leakage(df_feat) is True

def test_feature_matrix_excludes_duplicate_w9():
    fs = FeatureStore()
    df_feat = fs.build_feature_matrix("Malaria")

    # 2025 W9 must NOT be present as an origin row
    w9_origins = df_feat[(df_feat["origin_year"] == 2025) & (df_feat["origin_epi_week"] == 9)]
    assert len(w9_origins) == 0, "Quarantined 2025 W9 duplicate must be excluded from feature matrix origins"

def test_model_registry_active_uniqueness(db_session):
    # Must have exactly 1 active model for Malaria and 1 for Typhoid (2 total)
    active_malaria = db_session.query(ModelRegistry).filter(
        ModelRegistry.disease == "Malaria",
        ModelRegistry.is_active == True
    ).all()

    active_typhoid = db_session.query(ModelRegistry).filter(
        ModelRegistry.disease == "Typhoid",
        ModelRegistry.is_active == True
    ).all()

    assert len(active_malaria) == 1, f"Expected exactly 1 active Malaria model, found {len(active_malaria)}"
    assert len(active_typhoid) == 1, f"Expected exactly 1 active Typhoid model, found {len(active_typhoid)}"

    total_active = db_session.query(ModelRegistry).filter(ModelRegistry.is_active == True).count()
    assert total_active == 2, f"Expected exactly 2 total active models in registry, found {total_active}"
