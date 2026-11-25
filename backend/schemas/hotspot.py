"""
Pydantic Schemas for Hotspots, Leaflet Choropleth Map, and District Drilldowns.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel


class DistrictMapProperties(BaseModel):
    adm2_pcode: str
    adm2_name: str
    adm1_name: str = "Khyber Pakhtunkhwa"
    division: str
    population_2023: int
    cases: Optional[int] = None
    incidence_per_100k: Optional[float] = None
    hotspot_tier: str # 'priority_review', 'watch', 'routine', 'data_incomplete'
    ears_aberration_flag: bool = False
    forecast_breach: bool = False
    is_missing: bool = False
    reporting_coverage_pct: float = 100.0
    forecast_upper_95: Optional[float] = None


class GeoJSONFeature(BaseModel):
    type: str = "Feature"
    properties: DistrictMapProperties
    geometry: Dict[str, Any]


class GeoJSONFeatureCollection(BaseModel):
    type: str = "FeatureCollection"
    features: List[GeoJSONFeature]


class DistrictDrilldownResponse(BaseModel):
    district_pcode: str
    district_name: str
    division: str
    population_2023: int
    incidence_per_100k: float
    hotspot_tier: str
    reporting_facilities_count: int
    facilities: List[Dict[str, Any]]
    recent_trend: List[Dict[str, Any]]
