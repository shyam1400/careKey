"""Local, deterministic extraction of common laboratory values from text-based PDFs.

No document text is persisted or sent to an external AI/OCR service. All results are
unverified candidates until the patient confirms them.
"""

import re
from dataclasses import dataclass
from io import BytesIO

from fastapi import HTTPException
from pypdf import PdfReader


PARSER_VERSION = "lab-text-v1"


@dataclass(frozen=True)
class LabCandidate:
    measurement_type: str
    value: float
    unit: str
    source_page: int
    source_label: str


_PATTERNS: tuple[tuple[str, re.Pattern[str], dict[str, str]], ...] = (
    ("hba1c", re.compile(r"\b(?:HbA1c|Hemoglobin\s+A1c|Glycated\s+Hemoglobin)\b\s*[:=\-]?\s*([0-9]+(?:\.[0-9]+)?)\s*(%|mmol/mol)", re.I), {"%": "%", "mmol/mol": "mmol/mol"}),
    ("fasting_glucose", re.compile(r"\b(?:Fasting\s+(?:Blood\s+)?Glucose|Fasting\s+Plasma\s+Glucose)\b\s*[:=\-]?\s*([0-9]+(?:\.[0-9]+)?)\s*(mg/dL|mmol/L)", re.I), {"mg/dl": "mg/dL", "mmol/l": "mmol/L"}),
    ("total_cholesterol", re.compile(r"\b(?:Total\s+Cholesterol|Cholesterol\s+Total)\b\s*[:=\-]?\s*([0-9]+(?:\.[0-9]+)?)\s*(mg/dL|mmol/L)", re.I), {"mg/dl": "mg/dL", "mmol/l": "mmol/L"}),
    ("hdl_cholesterol", re.compile(r"\bHDL(?:\s+Cholesterol)?\b\s*[:=\-]?\s*([0-9]+(?:\.[0-9]+)?)\s*(mg/dL|mmol/L)", re.I), {"mg/dl": "mg/dL", "mmol/l": "mmol/L"}),
    ("ldl_cholesterol", re.compile(r"\bLDL(?:\s+Cholesterol)?\b\s*[:=\-]?\s*([0-9]+(?:\.[0-9]+)?)\s*(mg/dL|mmol/L)", re.I), {"mg/dl": "mg/dL", "mmol/l": "mmol/L"}),
    ("triglycerides", re.compile(r"\bTriglycerides?\b\s*[:=\-]?\s*([0-9]+(?:\.[0-9]+)?)\s*(mg/dL|mmol/L)", re.I), {"mg/dl": "mg/dL", "mmol/l": "mmol/L"}),
    ("serum_creatinine", re.compile(r"\b(?:Serum\s+)?Creatinine\b\s*[:=\-]?\s*([0-9]+(?:\.[0-9]+)?)\s*(mg/dL|umol/L|µmol/L)", re.I), {"mg/dl": "mg/dL", "umol/l": "umol/L", "µmol/l": "umol/L"}),
    ("egfr", re.compile(r"\b(?:eGFR|Estimated\s+GFR)\b\s*[:=\-]?\s*([0-9]+(?:\.[0-9]+)?)\s*(mL/min/1\.73\s*m2|mL/min/1\.73m2)", re.I), {"ml/min/1.73 m2": "mL/min/1.73m2", "ml/min/1.73m2": "mL/min/1.73m2"}),
    ("uacr", re.compile(r"\b(?:UACR|Urine\s+Albumin(?:\s*[-/ ]\s*Creatinine)?\s+Ratio)\b\s*[:=\-]?\s*([0-9]+(?:\.[0-9]+)?)\s*(mg/g|mg/mmol)", re.I), {"mg/g": "mg/g", "mg/mmol": "mg/mmol"}),
)


def extract_lab_candidates(pdf_bytes: bytes) -> list[LabCandidate]:
    if not pdf_bytes.startswith(b"%PDF-"):
        raise HTTPException(status_code=415, detail="Only text-based PDF reports can be extracted currently")
    try:
        reader = PdfReader(BytesIO(pdf_bytes), strict=False)
        if len(reader.pages) > 50:
            raise HTTPException(status_code=413, detail="Report exceeds the 50-page extraction limit")
        candidates: list[LabCandidate] = []
        for page_number, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            candidates.extend(extract_page_candidates(text, page_number))
        return candidates
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=422, detail="The PDF could not be read") from None


def extract_page_candidates(text: str, page_number: int) -> list[LabCandidate]:
    candidates: list[LabCandidate] = []
    seen: set[tuple[str, str, str, int]] = set()
    for line in text.splitlines():
        for measurement_type, pattern, unit_map in _PATTERNS:
            match = pattern.search(line)
            if not match:
                continue
            unit = unit_map.get(match.group(2).lower())
            if not unit:
                continue
            value = float(match.group(1))
            key = (measurement_type, str(value), unit, page_number)
            if key in seen:
                continue
            seen.add(key)
            candidates.append(LabCandidate(
                measurement_type=measurement_type, value=value, unit=unit,
                source_page=page_number, source_label=measurement_type.replace("_", " "),
            ))
    return candidates
