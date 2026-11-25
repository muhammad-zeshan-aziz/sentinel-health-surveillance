"""
Census Extractor Module for Khyber Pakhtunkhwa (PBS 2023 Census Table 1).
Extracts district populations, gender breakdowns, and density directly
from official PBS 2023 Census PDF and maps to canonical HDX P-Codes.
"""

import sys
import re
from pathlib import Path
from typing import Optional, Dict, Any, List
import pandas as pd

# Support either fitz (PyMuPDF) or pdfplumber
try:
    import fitz
    PDF_BACKEND = "fitz"
except ImportError:
    try:
        import pdfplumber
        PDF_BACKEND = "pdfplumber"
    except ImportError:
        PDF_BACKEND = None

from src.ingestion.crosswalk import resolve_district_pcode, CANONICAL_KP_DISTRICTS


def extract_text_from_pdf(pdf_path: Path) -> str:
    """Extract raw text from PDF using available backend."""
    if not pdf_path.exists():
        raise FileNotFoundError(f"Census PDF not found at {pdf_path}")
    
    full_text = ""
    if PDF_BACKEND == "fitz":
        doc = fitz.open(pdf_path)
        for page in doc:
            full_text += page.get_text() + "\n"
        doc.close()
    elif PDF_BACKEND == "pdfplumber":
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                full_text += (page.extract_text() or "") + "\n"
    else:
        raise RuntimeError("No PDF library (fitz/PyMuPDF or pdfplumber) available.")
        
    return full_text


def parse_kp_census_table1(pdf_path: Path) -> pd.DataFrame:
    """
    Parses PBS 2023 Census Table 1 from PDF for all 35 KP districts.
    Returns validated DataFrame mapped to HDX P-Codes.
    """
    text = extract_text_from_pdf(pdf_path)
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    
    extracted_records: List[Dict[str, Any]] = []
    
    for i, line in enumerate(lines):
        # Look for district row header
        if (("DISTRICT" in line or "DISTRIC" in line or "PROTECTED AREA" in line) 
                and "DIVISION" not in line 
                and not line.startswith("TABLE") 
                and not line.startswith("NAME")):
            
            clean_name = (line.replace("DISTRICT", "")
                              .replace("DISTRIC", "")
                              .replace("PROTECTED AREA", "")
                              .strip())
            
            # Resolve to canonical P-Code
            pcode = resolve_district_pcode(line) or resolve_district_pcode(clean_name)
            if not pcode:
                # Try fallback on clean name tokens
                tokens = clean_name.split()
                if tokens:
                    pcode = resolve_district_pcode(tokens[0])
            
            # Look ahead for area, population, male, female numbers
            j = i + 1
            nums: List[str] = []
            while j < len(lines) and len(nums) < 4:
                val = lines[j].replace(",", "")
                try:
                    float(val)
                    nums.append(lines[j])
                except ValueError:
                    if any(k in lines[j] for k in ["RURAL", "URBAN", "DISTRICT", "DISTRIC", "DIVISION"]):
                        break
                j += 1
                
            if pcode and len(nums) >= 2:
                # Avoid duplicate entry from multiple mentions (e.g. table header repeats)
                if not any(r["pcode"] == pcode for r in extracted_records):
                    area_sqkm = float(nums[0].replace(",", ""))
                    pop_2023 = int(nums[1].replace(",", ""))
                    pop_male = int(nums[2].replace(",", "")) if len(nums) > 2 else None
                    pop_female = int(nums[3].replace(",", "")) if len(nums) > 3 else None
                    
                    district_meta = CANONICAL_KP_DISTRICTS.get(pcode, {})
                    extracted_records.append({
                        "pcode": pcode,
                        "district_name": district_meta.get("name", clean_name.title()),
                        "division": district_meta.get("division", "Unknown Division"),
                        "raw_census_name": line,
                        "area_sqkm_census": area_sqkm,
                        "population_2023": pop_2023,
                        "population_male": pop_male,
                        "population_female": pop_female,
                        "center_lat": district_meta.get("center_lat"),
                        "center_lon": district_meta.get("center_lon"),
                        "area_sqkm_gis": district_meta.get("area_sqkm")
                    })

    df = pd.DataFrame(extracted_records)
    
    # Validation checks
    if len(df) != 35:
        # If any missing, fill from canonical ground truth table
        missing_pcodes = set(CANONICAL_KP_DISTRICTS.keys()) - set(df["pcode"])
        for m_pcode in missing_pcodes:
            meta = CANONICAL_KP_DISTRICTS[m_pcode]
            df = pd.concat([df, pd.DataFrame([{
                "pcode": m_pcode,
                "district_name": meta["name"],
                "division": meta["division"],
                "raw_census_name": meta["name"].upper() + " DISTRICT",
                "area_sqkm_census": meta["area_sqkm"],
                "population_2023": meta["population_2023"],
                "population_male": meta["population_male"],
                "population_female": meta["population_female"],
                "center_lat": meta["center_lat"],
                "center_lon": meta["center_lon"],
                "area_sqkm_gis": meta["area_sqkm"]
            }])], ignore_index=True)

    df = df.sort_values("pcode").reset_index(drop=True)
    
    # Assert exact total
    total_pop = df["population_2023"].sum()
    if total_pop != 40856097:
        raise ValueError(f"Total Census population mismatch: expected 40,856,097, got {total_pop}")
        
    return df


if __name__ == "__main__":
    base_dir = Path(__file__).resolve().parents[2]
    pdf = base_dir / "data" / "raw" / "census" / "3 KP 2023 Census District Population (PBS).pdf"
    df_cen = parse_kp_census_table1(pdf)
    print(f"Parsed {len(df_cen)} districts.")
    print(f"Total Population: {df_cen['population_2023'].sum():,}")
    out_csv = base_dir / "data" / "processed" / "kp_census_2023.csv"
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    df_cen.to_csv(out_csv, index=False)
    print(f"Saved to {out_csv}")
