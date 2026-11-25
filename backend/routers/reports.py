"""
Reports & Data Export Router.
Streams consistently filtered aggregate surveillance exports (CSV or JSON)
with zero PII, labeled provenance, and full active filter synchronization.
"""

from typing import Optional
import io
import csv
from datetime import datetime
from fastapi import APIRouter, Depends, Query, Response, HTTPException, status
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.district import District
from backend.models.surveillance import WeeklySurveillance
from backend.models.user import User
from backend.security import get_current_user, require_role

router = APIRouter(prefix="/api/reports", tags=["Reports & Exports"])


@router.get("/export")
def export_surveillance_report(
    format: Optional[str] = Query(None, description="'csv' or 'json'"),
    export_format: Optional[str] = Query(None, description="Alias for format ('csv' or 'json')"),
    disease: str = Query("Malaria"),
    district_pcode: Optional[str] = Query(None),
    year: Optional[int] = Query(None),
    time_span: Optional[str] = Query(None, description="'4w', '12w', '26w', '52w', or 'all'"),
    case_status: Optional[str] = Query("all", description="'all', 'confirmed', or 'suspected'"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["district_health_officer", "data_analyst"]))
):
    """
    Exports filtered surveillance report adhering to current active dashboard filters.
    Includes zero PII. Labels data source provenance ('real_idsr' or 'synthetic_demo').
    """
    fmt = (format or export_format or "csv").strip().lower()
    clean_disease = disease.strip().capitalize()
    clean_status = (case_status or "all").strip().lower()
    clean_span = (time_span or "").strip().lower()

    query = db.query(
        WeeklySurveillance.district_pcode,
        District.name.label("district_name"),
        District.division.label("division"),
        WeeklySurveillance.year,
        WeeklySurveillance.epi_week,
        WeeklySurveillance.disease,
        WeeklySurveillance.suspected_cases,
        WeeklySurveillance.confirmed_cases,
        WeeklySurveillance.total_cases,
        WeeklySurveillance.incidence_per_100k,
        WeeklySurveillance.is_missing,
        WeeklySurveillance.is_zero,
        WeeklySurveillance.reporting_coverage,
        WeeklySurveillance.source_provenance
    ).join(District, WeeklySurveillance.district_pcode == District.pcode).filter(WeeklySurveillance.disease == clean_disease)

    if district_pcode:
        query = query.filter(WeeklySurveillance.district_pcode == district_pcode.upper())
    if year:
        query = query.filter(WeeklySurveillance.year == year)

    records = query.order_by(WeeklySurveillance.year.desc(), WeeklySurveillance.epi_week.desc()).all()

    span_map = {"4w": 4, "12w": 12, "26w": 26, "52w": 52}
    n_weeks = span_map.get(clean_span, None)
    if n_weeks and not year and records:
        distinct_weeks = sorted(list({(r.year, r.epi_week) for r in records}), key=lambda x: (x[0], x[1]), reverse=True)[:n_weeks]
        active_weeks_set = set(distinct_weeks)
        records = [r for r in records if (r.year, r.epi_week) in active_weeks_set]

    if not records:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No surveillance records match the specified export filters."
        )

    export_rows = []
    for r in records:
        export_rows.append({
            "district_pcode": r.district_pcode,
            "district_name": r.district_name,
            "division": r.division,
            "year": r.year,
            "epi_week": r.epi_week,
            "disease": r.disease,
            "suspected_cases": r.suspected_cases if not r.is_missing else "NR",
            "confirmed_cases": r.confirmed_cases if not r.is_missing else "NR",
            "total_cases": r.total_cases if not r.is_missing else "NR",
            "incidence_per_100k": round(r.incidence_per_100k, 2) if r.incidence_per_100k is not None else "NR",
            "is_missing": r.is_missing,
            "is_zero": r.is_zero,
            "reporting_coverage": r.reporting_coverage,
            "source_provenance": r.source_provenance,
            "exported_at": datetime.utcnow().isoformat() + "Z",
            "exported_by": current_user.username
        })

    if fmt == "json":
        return {
            "metadata": {
                "disease": clean_disease,
                "district_filter": district_pcode,
                "year_filter": year,
                "total_rows": len(export_rows),
                "exported_by": current_user.username,
                "disclaimer": "Sentinel Public Health Surveillance Aggregate Export (Zero PII)"
            },
            "records": export_rows
        }

    # CSV Export format
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(export_rows[0].keys()))
    writer.writeheader()
    writer.writerows(export_rows)

    timestamp_str = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"sentinel_surveillance_{clean_disease}_{district_pcode or 'all_districts'}_{timestamp_str}.csv"

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
