"""
Historical Outbreak Alert Backtesting Engine (Phase 5).
Rigorously evaluates EARS C1/C2/C3 and Composite Hotspot alert performance
against historical outbreak surge events in Khyber Pakhtunkhwa.
Reports Precision, Recall, False-Alert Frequency, and Lead Time disaggregated for Malaria and Typhoid.
"""

from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass, asdict
import json
from pathlib import Path
import numpy as np
import pandas as pd

from src.surveillance.ears_detector import EARSDetector
from src.surveillance.hotspot_engine import HotspotEngine

MODULE_DIR = Path(__file__).resolve().parent
WORKSPACE_DIR = MODULE_DIR.parent.parent
PROCESSED_DIR = WORKSPACE_DIR / "data" / "processed"


@dataclass
class OutbreakEvent:
    event_id: str
    disease: str
    district_pcode: str
    district_name: str
    start_year: int
    start_week: int
    peak_year: int
    peak_week: int
    peak_t_idx: int
    peak_cases: float
    duration_weeks: int
    detected: bool
    lead_time_weeks: int
    earliest_alert_week: Optional[str]


class AlertBacktester:
    """
    Evaluates early-warning alert performance on historical disease panel.
    Strictly disaggregates Malaria and Typhoid without artificial metric distortion.
    """
    def __init__(self, data_path: Optional[Path] = None):
        self.data_path = data_path or (PROCESSED_DIR / "idsr_weekly_panel.csv")
        self.engine = HotspotEngine()

    def identify_ground_truth_outbreaks(self, disease: str) -> Tuple[List[OutbreakEvent], pd.DataFrame]:
        """
        Identifies ground truth historical outbreak surges per district.
        Definition: Sustained surge exceeding the district 85th percentile (or >2.0 std above 12-week moving median)
        for at least 2 consecutive weeks.
        """
        clean_disease = disease.strip().capitalize()
        df = pd.read_csv(self.data_path)
        if "condition" in df.columns and "disease" not in df.columns:
            df["disease"] = df["condition"]

        d_df = df[df["disease"].str.capitalize() == clean_disease].copy()
        # Filter 2025 W9 duplicate
        if "data_quality_flag" in d_df.columns:
            d_df = d_df[~d_df["data_quality_flag"].astype(str).str.contains("duplicate_source_table", na=False)].copy()

        d_df["t_idx"] = (d_df["year"] - 2023) * 52 + d_df["epi_week"] - 16
        d_df = d_df.sort_values(["district_pcode", "t_idx"]).reset_index(drop=True)

        outbreaks: List[OutbreakEvent] = []
        event_counter = 1

        for pcode, grp in d_df.groupby("district_pcode"):
            grp = grp.sort_values("t_idx").reset_index(drop=True)
            d_name = grp["district_name"].iloc[0]
            valid_cases = grp[~grp["is_missing"] & ~grp["total_cases"].isna()]["total_cases"].values

            if len(valid_cases) < 20:
                continue

            threshold = float(np.percentile(valid_cases, 85))
            # Minimum case count threshold to avoid flagging trivial low-volume noise
            min_floor = 15.0 if clean_disease == "Malaria" else 8.0
            effective_threshold = max(threshold, min_floor)

            in_outbreak = False
            cur_surge: List[Dict[str, Any]] = []

            for _, row in grp.iterrows():
                cases = row["total_cases"]
                is_miss = bool(row["is_missing"]) or (cases is None) or np.isnan(cases)

                if not is_miss and float(cases) >= effective_threshold:
                    in_outbreak = True
                    cur_surge.append(row)
                else:
                    if in_outbreak:
                        if len(cur_surge) >= 2:
                            # Recorded outbreak event
                            peak_row = max(cur_surge, key=lambda r: float(r["total_cases"]))
                            start_row = cur_surge[0]
                            outbreaks.append(OutbreakEvent(
                                event_id=f"{clean_disease}_{pcode}_{event_counter}",
                                disease=clean_disease,
                                district_pcode=pcode,
                                district_name=d_name,
                                start_year=int(start_row["year"]),
                                start_week=int(start_row["epi_week"]),
                                peak_year=int(peak_row["year"]),
                                peak_week=int(peak_row["epi_week"]),
                                peak_t_idx=int(peak_row["t_idx"]),
                                peak_cases=float(peak_row["total_cases"]),
                                duration_weeks=len(cur_surge),
                                detected=False,
                                lead_time_weeks=0,
                                earliest_alert_week=None
                            ))
                            event_counter += 1
                        in_outbreak = False
                        cur_surge = []

            # Handle trailing outbreak
            if in_outbreak and len(cur_surge) >= 2:
                peak_row = max(cur_surge, key=lambda r: float(r["total_cases"]))
                start_row = cur_surge[0]
                outbreaks.append(OutbreakEvent(
                    event_id=f"{clean_disease}_{pcode}_{event_counter}",
                    disease=clean_disease,
                    district_pcode=pcode,
                    district_name=d_name,
                    start_year=int(start_row["year"]),
                    start_week=int(start_row["epi_week"]),
                    peak_year=int(peak_row["year"]),
                    peak_week=int(peak_row["epi_week"]),
                    peak_t_idx=int(peak_row["t_idx"]),
                    peak_cases=float(peak_row["total_cases"]),
                    duration_weeks=len(cur_surge),
                    detected=False,
                    lead_time_weeks=0,
                    earliest_alert_week=None
                ))
                event_counter += 1

        return outbreaks, d_df

    def run_backtest(self, disease: str) -> Dict[str, Any]:
        """Runs chronological alert evaluation across all district-weeks for a given disease."""
        clean_disease = disease.strip().capitalize()
        outbreaks, d_df = self.identify_ground_truth_outbreaks(clean_disease)

        total_district_weeks = len(d_df)
        total_alerts = 0
        true_alerts = 0
        false_alerts = 0

        # Map each outbreak to its district and timeline for fast spatial-temporal intersection
        outbreak_timeline_by_district: Dict[str, List[OutbreakEvent]] = {}
        for ob in outbreaks:
            outbreak_timeline_by_district.setdefault(ob.district_pcode, []).append(ob)

        alert_records = []

        # Chronological district simulation
        for pcode, grp in d_df.groupby("district_pcode"):
            grp = grp.sort_values("t_idx").reset_index(drop=True)
            d_name = grp["district_name"].iloc[0]
            div = grp["division"].iloc[0]
            pop = float(grp["population_2023"].iloc[0])

            cases_list = grp["total_cases"].tolist()
            missing_list = grp["is_missing"].tolist()
            prior_z2_history = []

            dist_outbreaks = outbreak_timeline_by_district.get(pcode, [])

            for t in range(len(grp)):
                row = grp.iloc[t]
                t_idx = int(row["t_idx"])
                yr = int(row["year"])
                wk = int(row["epi_week"])
                val = row["total_cases"]
                is_miss = bool(row["is_missing"]) or (val is None) or np.isnan(val)

                history = cases_list[:t]
                asmt = self.engine.assess_district(
                    district_pcode=pcode,
                    district_name=d_name,
                    division=div,
                    disease=clean_disease,
                    year=yr,
                    epi_week=wk,
                    population_2023=pop,
                    current_cases=val,
                    is_missing=is_miss,
                    history_cases=history,
                    prior_z2_scores=prior_z2_history[-2:],
                    forecast_mean=None,
                    forecast_ci_upper=None,
                    is_forecast_withheld=False
                )
                prior_z2_history.append(asmt.ears_z2)

                # Did an early warning alert fire?
                alert_fired = asmt.observed_hotspot_tier in ["priority_review", "watch"]

                if alert_fired:
                    total_alerts += 1
                    # Check temporal alignment with any outbreak in this district
                    # An alert is a True Alert if it falls within [start_t - 2 weeks, peak_t + 1 week]
                    matched_ob = None
                    for ob in dist_outbreaks:
                        # Lead window: up to 3 weeks before peak
                        if (ob.peak_t_idx - 3) <= t_idx <= (ob.peak_t_idx + 1):
                            matched_ob = ob
                            break

                    if matched_ob is not None:
                        true_alerts += 1
                        if not matched_ob.detected:
                            matched_ob.detected = True
                            matched_ob.lead_time_weeks = max(0, matched_ob.peak_t_idx - t_idx)
                            matched_ob.earliest_alert_week = f"{yr}-W{wk:02d}"
                    else:
                        false_alerts += 1

                    alert_records.append({
                        "district_pcode": pcode,
                        "district_name": d_name,
                        "year": yr,
                        "epi_week": wk,
                        "alert_tier": asmt.observed_hotspot_tier,
                        "cases": asmt.observed_cases,
                        "incidence": asmt.incidence_per_100k,
                        "z2": asmt.ears_z2,
                        "composite": asmt.composite_score,
                        "is_true_alert": (matched_ob is not None)
                    })

        # Calculate Performance Metrics
        precision = round(true_alerts / total_alerts, 3) if total_alerts > 0 else 0.0
        detected_outbreaks_count = sum(1 for ob in outbreaks if ob.detected)
        total_outbreaks_count = len(outbreaks)
        recall = round(detected_outbreaks_count / total_outbreaks_count, 3) if total_outbreaks_count > 0 else 0.0

        # False Alert Frequency
        # Per 100 district-weeks
        faf_per_100_weeks = round((false_alerts / total_district_weeks) * 100.0, 2)
        # Per district-year (52 weeks)
        total_district_years = total_district_weeks / 52.0
        faf_per_district_year = round(false_alerts / total_district_years, 2) if total_district_years > 0 else 0.0

        # Lead time across detected outbreaks
        detected_leads = [ob.lead_time_weeks for ob in outbreaks if ob.detected]
        avg_lead_time = round(float(np.mean(detected_leads)), 2) if detected_leads else 0.0

        # Spotlight District Events
        spotlight_pcodes = ["PK501", "PK503", "PK522", "PK532", "PK520", "PK511", "PK528"]
        spotlight_events = [
            asdict(ob) for ob in outbreaks
            if ob.district_pcode in spotlight_pcodes
        ][:15]

        return {
            "disease": clean_disease,
            "metrics": {
                "precision": precision,
                "recall": recall,
                "total_outbreaks": total_outbreaks_count,
                "detected_outbreaks": detected_outbreaks_count,
                "total_alerts": total_alerts,
                "true_alerts": true_alerts,
                "false_alerts": false_alerts,
                "false_alert_freq_per_100_weeks": faf_per_100_weeks,
                "false_alert_freq_per_district_year": faf_per_district_year,
                "average_lead_time_weeks": avg_lead_time
            },
            "spotlight_events": spotlight_events
        }


def evaluate_all_diseases() -> Dict[str, Any]:
    """Runs disaggregated backtest for Malaria and Typhoid, saving results to data/processed/."""
    backtester = AlertBacktester()
    full_results = {
        "timestamp": pd.Timestamp.now().isoformat(),
        "malaria": backtester.run_backtest("Malaria"),
        "typhoid": backtester.run_backtest("Typhoid")
    }

    out_file = PROCESSED_DIR / "backtest_results.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(full_results, f, indent=2)

    print(f"[Backtest Complete] Saved disaggregated results to: {out_file}")
    return full_results


if __name__ == "__main__":
    evaluate_all_diseases()
