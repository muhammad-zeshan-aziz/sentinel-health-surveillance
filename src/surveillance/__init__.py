"""
Sentinel Health Surveillance - Outbreak Detection & Hotspots Subsystem (Phase 5).
Implements CDC EARS (C1, C2, C3) weekly aberration detectors,
dual-layer observed and forecast hotspot scoring, and historical alert backtesting.
"""

from src.surveillance.ears_detector import (
    EARSDetector,
    calculate_ears_scores_for_series,
    EARSScore
)
from src.surveillance.hotspot_engine import (
    HotspotEngine,
    DistrictHotspotAssessment,
    DualLayerHotspotMap
)
from src.surveillance.backtester import AlertBacktester, OutbreakEvent

__all__ = [
    "EARSDetector",
    "calculate_ears_scores_for_series",
    "EARSScore",
    "HotspotEngine",
    "DistrictHotspotAssessment",
    "DualLayerHotspotMap",
    "AlertBacktester",
    "OutbreakEvent"
]
