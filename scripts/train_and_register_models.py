"""
Production Model Training, Registration, and Forecast Database Seeding (Phase 4).
Trains separate forecasting pipelines for Malaria & Typhoid, evaluates baselines,
runs weather ablation, serializes artifacts, and populates model_registry & forecasts tables.
"""

import sys
import os
import json
from pathlib import Path
from datetime import datetime
import numpy as np
import pandas as pd

# Path configuration
SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE_DIR = SCRIPT_DIR.parent
if str(WORKSPACE_DIR) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_DIR))

from src.ml.trainer import DiseaseForecastPipeline, FEATURE_COLUMNS
from src.ml.feature_store import FeatureStore, apply_in_fold_district_baseline
from src.ml.guardrails import ForecastGuardrail
from src.ml.ablation_weather import run_weather_ablation

from backend.database import SessionLocal, engine
from backend.models.ml import ModelRegistry, Forecast
from backend.models.district import District

MODELS_DIR = WORKSPACE_DIR / "models"


def train_register_and_seed():
    print("=" * 80)
    print("SENTINEL HEALTH SURVEILLANCE - PHASE 4 MODEL TRAINING & REGISTRATION")
    print("Expanding-Origin CV, Calibrated Prediction Intervals & Model Registry Integration")
    print("=" * 80)

    db = SessionLocal()
    fs = FeatureStore()

    try:
        # Step 1: Run Weather Feature Ablation Experiment
        print("\n" + "=" * 50)
        print("[STEP 1/3] Running Weather Feature Ablation Experiment...")
        print("=" * 50)
        ablation_summary = run_weather_ablation()

        # Step 2: Train and Tune Separate Pipelines for Malaria and Typhoid
        print("\n" + "=" * 50)
        print("[STEP 2/3] Training & Tuning Disease Forecasting Models...")
        print("=" * 50)

        trained_pipelines = {}
        for disease in ["Malaria", "Typhoid"]:
            pipeline = DiseaseForecastPipeline(disease)
            metrics = pipeline.run_benchmark()
            trained_pipelines[disease] = pipeline

        # Step 3: Seed Model Registry & Forecasts in Database
        print("\n" + "=" * 50)
        print("[STEP 3/3] Registering Models & Seeding Forecasts in Database...")
        print("=" * 50)

        districts = db.query(District).all()
        pcode_to_name = {d.pcode: d.name for d in districts}

        for disease, pipe in trained_pipelines.items():
            clean_disease = disease.strip().capitalize()
            # Deactivate any previous models for this disease
            db.query(ModelRegistry).filter(ModelRegistry.disease == clean_disease).update({"is_active": False})

            # Read saved eval metrics
            eval_file = pipe.model_dir / "eval_metrics.json"
            with open(eval_file, "r", encoding="utf-8") as f:
                eval_data = json.load(f)

            winning_name = pipe.winning_model_name or "Gradient_Boosting"
            bundle = pipe.final_model_bundle
            mean_model = bundle["mean_model"]
            uncertainty_engine = bundle["uncertainty_engine"]
            baseline_dict = bundle["baseline_dict"]

            # Hyperparameters representation
            hyperparams = getattr(mean_model, "get_params", lambda: {"model": winning_name})()
            # Filter non-serializable objects
            safe_hyperparams = {k: str(v) for k, v in hyperparams.items() if isinstance(v, (int, float, str, bool))}

            # Deactivate any prior active models for this disease to maintain strict uniqueness
            db.query(ModelRegistry).filter(
                ModelRegistry.disease == clean_disease,
                ModelRegistry.is_active == True
            ).update({"is_active": False})

            # Insert into ModelRegistry
            registry_entry = ModelRegistry(
                disease=clean_disease,
                model_name=f"{winning_name}_{clean_disease}_ExpandingCV",
                model_type="gradient_boosting" if "Boosting" in winning_name or "XGB" in winning_name else "random_forest",
                version="v1.0",
                feature_names=json.dumps(FEATURE_COLUMNS),
                hyperparams=json.dumps(safe_hyperparams),
                metrics=json.dumps(eval_data["overall_metrics"]),
                artifact_path=str((pipe.model_dir / f"model_bundle_{disease.lower()}_v1.joblib").relative_to(WORKSPACE_DIR)),
                is_active=True,
                created_at=datetime.utcnow()
            )
            db.add(registry_entry)
            db.flush()

            print(f"  -> Registered active model: {registry_entry.model_name} (ID: {registry_entry.id})")

            # Generate t+1 forecasts for all 35 KP districts
            feats_df = fs.build_feature_matrix(clean_disease)

            # Delete prior forecasts for this disease to maintain idempotency
            db.query(Forecast).filter(Forecast.disease == clean_disease).delete()

            # Find latest available origin week per district for t+1 forecast
            latest_origin_rows = []
            for pcode, grp in feats_df.groupby("district_pcode"):
                latest_row = grp.sort_values("origin_t_idx").iloc[-1]
                latest_origin_rows.append(latest_row)

            latest_df = pd.DataFrame(latest_origin_rows)
            latest_df["district_baseline_inc"] = apply_in_fold_district_baseline(latest_df, baseline_dict)

            X_latest = latest_df[FEATURE_COLUMNS].values
            preds_mean = np.maximum(0.0, mean_model.predict(X_latest))
            preds_lower, preds_upper = uncertainty_engine.predict(X_latest, preds_mean)

            forecast_records = []
            withheld_count = 0

            for idx, row in latest_df.reset_index(drop=True).iterrows():
                pcode = row["district_pcode"]
                target_year = int(row["target_year"])
                target_week = int(row["target_epi_week"])
                p_mean = float(preds_mean[idx])
                p_lower = float(preds_lower[idx])
                p_upper = float(preds_upper[idx])
                hist_depth = int(row["history_depth_weeks"])
                cov_4 = float(row["reporting_coverage_4"])

                # Check Withholding Guardrail
                is_withheld, withhold_reason = ForecastGuardrail.evaluate(pcode, hist_depth, cov_4)
                if is_withheld:
                    withheld_count += 1
                    p_mean_val = None
                    p_lower_val = None
                    p_upper_val = None
                else:
                    p_mean_val = round(p_mean, 1)
                    p_lower_val = round(p_lower, 1)
                    p_upper_val = round(p_upper, 1)

                forecast_records.append(Forecast(
                    model_id=registry_entry.id,
                    district_pcode=pcode,
                    target_year=target_year,
                    target_week=target_week,
                    disease=clean_disease,
                    predicted_mean=p_mean_val,
                    ci_lower_95=p_lower_val,
                    ci_upper_95=p_upper_val,
                    is_withheld=is_withheld,
                    withholding_reason=withhold_reason,
                    created_at=datetime.utcnow()
                ))

            db.bulk_save_objects(forecast_records)
            db.commit()
            print(f"  -> Inserted {len(forecast_records)} forecasts for {clean_disease} ({withheld_count} withheld via guardrails).")

        print("\n" + "=" * 80)
        print("PHASE 4 TRAINING, REGISTRATION & SEEDING COMPLETED SUCCESSFULLY")
        print("=" * 80)

    finally:
        db.close()


if __name__ == "__main__":
    train_register_and_seed()
