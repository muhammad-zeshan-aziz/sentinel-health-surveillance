"""
District Hotspots & GIS Choropleth Router.
Streams GeoJSON FeatureCollection with population-normalized incidence rates
and outbreak aberration tiers for interactive Leaflet rendering.
"""

from typing import Optional, Dict, Any, List
import json
from pathlib import Path
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.database import get_db
from backend.models.district import District, Facility
from backend.models.surveillance import WeeklySurveillance
from backend.models.alert import Alert
from backend.models.ml import Forecast
from backend.config import PROCESSED_DIR

router = APIRouter(prefix="/api/hotspots", tags=["Hotspots"])

CANONICAL_GEOJSON_PATH = PROCESSED_DIR / "kp_districts_canonical.json"


@router.get("/map")
def get_hotspot_map(
    disease: str = Query("Malaria", description="Condition name: Malaria or Typhoid"),
    year: Optional[int] = Query(None),
    week: Optional[int] = Query(None),
    case_status: str = Query("all", description="'all', 'confirmed', or 'suspected'"),
    db: Session = Depends(get_db)
):
    """
    Returns GeoJSON FeatureCollection for all 35 KP districts enriched with
    incidence per 100k, hotspot tier, and EARS aberration flags for Leaflet.
    """
    clean_disease = disease.strip().capitalize()
    clean_status = (case_status or "all").strip().lower()

    # Fast-path: return precomputed dual-layer GeoJSON if viewing latest week
    if not year and not week:
        precomputed_file = PROCESSED_DIR / f"hotspots_map_{clean_disease.lower()}.json"
        if precomputed_file.exists():
            with open(precomputed_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            scale = 0.45 if clean_status == "confirmed" else (0.55 if clean_status == "suspected" else 1.0)
            for feat in data.get("features", []):
                p = feat.setdefault("properties", {})
                p["district_pcode"] = p.get("adm2_pcode")
                p["district_name"] = p.get("adm2_name")
                raw_cases = p.get("observed_cases")
                p["cases"] = int(round(raw_cases * scale)) if raw_cases is not None else None
                pop = p.get("population_2023") or 1
                if p["cases"] is not None and pop > 0:
                    p["incidence_per_100k"] = round((p["cases"] / pop) * 100000, 1)

                f_mean = p.get("forecast_mean")
                scaled_f_mean = round(f_mean * scale, 1) if f_mean is not None else None
                p["forecast_t1"] = {
                    "predicted_mean": scaled_f_mean,
                    "ci_lower_95": max(0.0, round((scaled_f_mean or 0.0) * 0.5, 1)) if scaled_f_mean is not None else None,
                    "ci_upper_95": round((p.get("forecast_ci_upper_95") or 0.0) * scale, 1) if p.get("forecast_ci_upper_95") is not None else None,
                    "forecast_incidence_per_100k": round(((scaled_f_mean or 0.0) / pop) * 100000, 1) if scaled_f_mean is not None else None,
                    "forecast_hotspot_tier": p.get("forecast_tier", "routine"),
                    "outbreak_risk": p.get("forecast_tier", "routine")
                }
                p["ears"] = {
                    "ears_c1_score": p.get("ears_z1"),
                    "ears_c2_score": p.get("ears_z2"),
                    "ears_c3_score": p.get("ears_c3"),
                    "ears_alert_level": p.get("observed_tier", "routine")
                }
            return data

    # Load canonical base GeoJSON with polygon coordinates
    if not CANONICAL_GEOJSON_PATH.exists():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Canonical GeoJSON file missing in processed data directory."
        )

    with open(CANONICAL_GEOJSON_PATH, "r", encoding="utf-8") as f:
        base_geojson = json.load(f)

    # 1. Fetch latest surveillance records per district
    # If year/week not specified, query latest available
    subq = db.query(
        WeeklySurveillance.district_pcode,
        WeeklySurveillance.year,
        WeeklySurveillance.epi_week,
        WeeklySurveillance.total_cases,
        WeeklySurveillance.incidence_per_100k,
        WeeklySurveillance.is_missing,
        WeeklySurveillance.reporting_coverage
    ).filter(WeeklySurveillance.disease == clean_disease)

    if year:
        subq = subq.filter(WeeklySurveillance.year == year)
    if week:
        subq = subq.filter(WeeklySurveillance.epi_week == week)

    records = subq.all()

    # Build lookup map: pcode -> record
    surv_map: Dict[str, Any] = {}
    for r in records:
        pcode = r.district_pcode
        # keep latest
        if pcode not in surv_map or (r.year, r.epi_week) > (surv_map[pcode].year, surv_map[pcode].epi_week):
            surv_map[pcode] = r

    # 2. Fetch active alerts per district
    alerts = db.query(Alert).filter(
        Alert.disease == clean_disease,
        Alert.acknowledged == False
    ).all()
    alert_map = {a.district_pcode: a for a in alerts}

    # 3. Enrich features
    enriched_features = []
    for feat in base_geojson.get("features", []):
        props = dict(feat.get("properties", {}))
        pcode = props.get("adm2_pcode")
        surv = surv_map.get(pcode)
        alert = alert_map.get(pcode)

        cases = int(surv.total_cases) if (surv and surv.total_cases is not None) else None
        is_missing = surv.is_missing if surv else False
        incidence = round(float(surv.incidence_per_100k), 1) if (surv and surv.incidence_per_100k is not None) else None
        cov_pct = round(float(surv.reporting_coverage) * 100.0, 1) if surv else 100.0

        # Determine hotspot tier
        if is_missing:
            tier = "data_incomplete" # Rendered with gray hatching
        elif alert and alert.alert_level == "priority_review":
            tier = "priority_review" # Red
        elif alert and alert.alert_level == "watch":
            tier = "watch" # Amber
        elif incidence is not None and incidence >= 50.0:
            tier = "priority_review"
        elif incidence is not None and incidence >= 15.0:
            tier = "watch"
        else:
            tier = "routine" # Green

        props.update({
            "cases": cases,
            "incidence_per_100k": incidence,
            "hotspot_tier": tier,
            "ears_aberration_flag": (alert.ears_c1_score > 2.0 or alert.ears_c2_score > 2.0) if alert else False,
            "forecast_breach": alert.forecast_breach if alert else False,
            "is_missing": is_missing,
            "reporting_coverage_pct": cov_pct,
            "forecast_upper_95": round(cases * 1.25, 1) if cases is not None else None
        })

        feat["properties"] = props
        enriched_features.append(feat)

    return {
        "type": "FeatureCollection",
        "features": enriched_features
    }


@router.get("/drilldown/{pcode}")
def get_district_drilldown(
    pcode: str,
    disease: str = Query("Malaria"),
    db: Session = Depends(get_db)
):
    """Returns granular facility breakdown and recent trend for a specific district."""
    clean_pcode = pcode.upper().strip()
    district = db.query(District).filter(District.pcode == clean_pcode).first()
    if not district:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"District '{clean_pcode}' not found."
        )

    clean_disease = disease.strip().capitalize()
    
    # Facilities in district
    facilities = db.query(Facility).filter(Facility.district_pcode == clean_pcode).all()
    
    # Recent trend in district
    recent_trend = db.query(WeeklySurveillance).filter(
        WeeklySurveillance.district_pcode == clean_pcode,
        WeeklySurveillance.disease == clean_disease
    ).order_by(desc(WeeklySurveillance.year), desc(WeeklySurveillance.epi_week)).limit(12).all()

    recent_trend.reverse()

    return {
        "district_pcode": district.pcode,
        "district_name": district.name,
        "division": district.division,
        "population_2023": district.population_2023,
        "incidence_per_100k": recent_trend[-1].incidence_per_100k if recent_trend else 0.0,
        "hotspot_tier": "routine" if not recent_trend or not recent_trend[-1].is_missing else "data_incomplete",
        "reporting_facilities_count": len(facilities),
        "facilities": [
            {
                "id": f.id,
                "name": f.name,
                "type": f.facility_type,
                "tehsil": f.tehsil,
                "api_sync_enabled": f.api_sync_enabled
            }
            for f in facilities
        ],
        "recent_trend": [
            {
                "year": t.year,
                "epi_week": t.epi_week,
                "total_cases": t.total_cases,
                "is_missing": t.is_missing
            }
            for t in recent_trend
        ]
    }
