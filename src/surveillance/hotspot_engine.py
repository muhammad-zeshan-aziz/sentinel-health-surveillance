"""
District Hotspot & Forecast Hotspot Classification Engine (Phase 5).
Computes population-normalized incidence rates, forecast upper-bound breaches,
composite outbreak risk scores, and dual-layer Leaflet GeoJSON features
(Observed Hotspots + Forecast Hotspots t+1).
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import json
from pathlib import Path
import numpy as np
import pandas as pd

from src.surveillance.ears_detector import EARSDetector, EARSScore

MODULE_DIR = Path(__file__).resolve().parent
WORKSPACE_DIR = MODULE_DIR.parent.parent
PROCESSED_DIR = WORKSPACE_DIR / "data" / "processed"


@dataclass
class DistrictHotspotAssessment:
    district_pcode: str
    district_name: str
    division: str
    disease: str
    year: int
    epi_week: int
    population_2023: float
    observed_cases: Optional[float]
    is_missing: bool
    incidence_per_100k: Optional[float]
    ears_z1: float
    ears_z2: float
    ears_c3: float
    forecast_mean: Optional[float]
    forecast_ci_upper_95: Optional[float]
    forecast_breach: bool
    is_forecast_withheld: bool
    composite_score: float
    observed_hotspot_tier: str  # 'priority_review', 'watch', 'routine', 'data_incomplete'
    forecast_hotspot_tier: str  # 'priority_review', 'watch', 'routine', 'forecast_withheld'
    headline: str
    details: str


class HotspotEngine:
    """
    Composite Hotspot & Aberration Classifier (Blueprint Section 5.7).
    Scores districts using multi-criteria epidemiological risk:
    - EARS aberration Z-scores (40%)
    - Forecast upper-bound breach (35%)
    - Population-normalized incidence (25%)
    """
    # Population incidence thresholds per 100k population
    INCIDENCE_THRESHOLDS = {
        "Malaria": 50.0,
        "Typhoid": 15.0
    }

    def __init__(self):
        self.detector = EARSDetector()

    def assess_district(
        self,
        district_pcode: str,
        district_name: str,
        division: str,
        disease: str,
        year: int,
        epi_week: int,
        population_2023: float,
        current_cases: Optional[float],
        is_missing: bool,
        history_cases: List[Optional[float]],
        prior_z2_scores: Optional[List[float]] = None,
        forecast_mean: Optional[float] = None,
        forecast_ci_upper: Optional[float] = None,
        is_forecast_withheld: bool = False
    ) -> DistrictHotspotAssessment:
        clean_disease = disease.strip().capitalize()
        threshold_inc = self.INCIDENCE_THRESHOLDS.get(clean_disease, 30.0)

        # -------------------------------------------------------------
        # 1. Handle Incomplete / Missing Reporting Data
        # -------------------------------------------------------------
        if is_missing or current_cases is None:
            return DistrictHotspotAssessment(
                district_pcode=district_pcode,
                district_name=district_name,
                division=division,
                disease=clean_disease,
                year=year,
                epi_week=epi_week,
                population_2023=population_2023,
                observed_cases=None,
                is_missing=True,
                incidence_per_100k=None,
                ears_z1=0.0,
                ears_z2=0.0,
                ears_c3=0.0,
                forecast_mean=forecast_mean,
                forecast_ci_upper_95=forecast_ci_upper,
                forecast_breach=False,
                is_forecast_withheld=is_forecast_withheld,
                composite_score=0.0,
                observed_hotspot_tier="data_incomplete",
                forecast_hotspot_tier="forecast_withheld" if is_forecast_withheld else "routine",
                headline=f"Missing Surveillance Report for {district_name}",
                details=f"Facility surveillance report for {district_name} was unsubmitted or marked NR in bulletin {year}-W{epi_week:02d}."
            )

        # -------------------------------------------------------------
        # 2. Compute EARS Statistics
        # -------------------------------------------------------------
        ears = self.detector.compute_single_point(
            current_case_count=current_cases,
            history_cases=history_cases,
            is_missing=False,
            prior_z2_scores=prior_z2_scores
        )

        # -------------------------------------------------------------
        # 3. Compute Incidence & Forecast Breach
        # -------------------------------------------------------------
        pop_safe = max(1000.0, float(population_2023))
        incidence = round((float(current_cases) / pop_safe) * 100000.0, 1)

        forecast_breach = False
        if forecast_ci_upper is not None and not is_forecast_withheld:
            if float(current_cases) > float(forecast_ci_upper):
                forecast_breach = True

        # -------------------------------------------------------------
        # 4. Calculate Composite Hotspot Risk Score: S_d(t)
        # S_d(t) = 0.40 * min(1.0, max(Z1, Z2)/3.0) + 0.35 * Breach + 0.25 * min(1.0, Inc/Threshold)
        # -------------------------------------------------------------
        z_component = min(1.0, max(0.0, max(ears.z1, ears.z2)) / 3.0)
        breach_component = 1.0 if forecast_breach else 0.0
        inc_component = min(1.0, max(0.0, incidence) / threshold_inc)

        composite_score = round(0.40 * z_component + 0.35 * breach_component + 0.25 * inc_component, 3)

        # -------------------------------------------------------------
        # 5. Determine Observed Hotspot Tier
        # -------------------------------------------------------------
        if composite_score >= 0.70 or (ears.z2 >= 3.0 and forecast_breach) or (incidence >= 2.0 * threshold_inc):
            observed_tier = "priority_review"
            headline = f"Outbreak Alert (Priority Review) in {district_name}"
            details = f"{district_name} reported {int(current_cases)} {clean_disease} cases (Incidence: {incidence}/100k, EARS Z2: {ears.z2}, Composite Risk: {composite_score})."
        elif composite_score >= 0.40 or ears.z1 >= 2.0 or ears.c3 >= 2.0 or (incidence >= threshold_inc):
            observed_tier = "watch"
            headline = f"Early Warning Watch in {district_name}"
            details = f"{district_name} exhibits emerging transmission spike ({int(current_cases)} cases, EARS Z1: {ears.z1}, Composite: {composite_score})."
        else:
            observed_tier = "routine"
            headline = f"Routine Surveillance for {district_name}"
            details = f"{district_name} cases are within baseline expectations ({int(current_cases)} cases, Incidence: {incidence}/100k)."

        # -------------------------------------------------------------
        # 6. Determine Forecast Hotspot Layer (t+1 projection)
        # -------------------------------------------------------------
        if is_forecast_withheld or forecast_mean is None:
            forecast_tier = "forecast_withheld"
        else:
            fc_inc = (float(forecast_mean) / pop_safe) * 100000.0
            prev_cases = float(current_cases) if current_cases > 0 else 1.0
            growth_rate = (float(forecast_mean) - prev_cases) / prev_cases

            if fc_inc >= threshold_inc or growth_rate >= 0.50:
                forecast_tier = "priority_review"
            elif fc_inc >= 0.60 * threshold_inc or growth_rate >= 0.20:
                forecast_tier = "watch"
            else:
                forecast_tier = "routine"

        return DistrictHotspotAssessment(
            district_pcode=district_pcode,
            district_name=district_name,
            division=division,
            disease=clean_disease,
            year=year,
            epi_week=epi_week,
            population_2023=population_2023,
            observed_cases=float(current_cases),
            is_missing=False,
            incidence_per_100k=incidence,
            ears_z1=ears.z1,
            ears_z2=ears.z2,
            ears_c3=ears.c3,
            forecast_mean=forecast_mean,
            forecast_ci_upper_95=forecast_ci_upper,
            forecast_breach=forecast_breach,
            is_forecast_withheld=is_forecast_withheld,
            composite_score=composite_score,
            observed_hotspot_tier=observed_tier,
            forecast_hotspot_tier=forecast_tier,
            headline=headline,
            details=details
        )


class DualLayerHotspotMap:
    """
    Enriches base canonical GeoJSON polygons with Observed and Forecast Hotspot attributes
    for Leaflet interactive choropleth maps.
    """
    def __init__(self, geojson_path: Optional[Path] = None):
        self.geojson_path = geojson_path or (PROCESSED_DIR / "kp_districts_canonical.json")

    def build_feature_collection(
        self,
        assessments: Dict[str, DistrictHotspotAssessment]
    ) -> Dict[str, Any]:
        with open(self.geojson_path, "r", encoding="utf-8") as f:
            base_data = json.load(f)

        enriched_features = []
        for feat in base_data.get("features", []):
            feat_copy = json.loads(json.dumps(feat))
            props = feat_copy.get("properties", {})
            pcode = props.get("adm2_pcode")
            asmt = assessments.get(pcode)

            if asmt:
                props.update({
                    "disease": asmt.disease,
                    "year": asmt.year,
                    "epi_week": asmt.epi_week,
                    "observed_cases": asmt.observed_cases,
                    "is_missing": asmt.is_missing,
                    "incidence_per_100k": asmt.incidence_per_100k,
                    "ears_z1": asmt.ears_z1,
                    "ears_z2": asmt.ears_z2,
                    "ears_c3": asmt.ears_c3,
                    "composite_score": asmt.composite_score,
                    "observed_tier": asmt.observed_hotspot_tier,
                    "hotspot_tier": asmt.observed_hotspot_tier, # Primary Leaflet property
                    "forecast_mean": asmt.forecast_mean,
                    "forecast_ci_upper_95": asmt.forecast_ci_upper_95,
                    "forecast_breach": asmt.forecast_breach,
                    "forecast_tier": asmt.forecast_hotspot_tier,
                    "is_forecast_withheld": asmt.is_forecast_withheld,
                    "headline": asmt.headline,
                    "details": asmt.details
                })
            else:
                props.update({
                    "observed_tier": "data_incomplete",
                    "hotspot_tier": "data_incomplete",
                    "forecast_tier": "forecast_withheld",
                    "is_missing": True
                })

            feat_copy["properties"] = props
            enriched_features.append(feat_copy)

        return {
            "type": "FeatureCollection",
            "features": enriched_features
        }
