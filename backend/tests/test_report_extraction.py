from fastapi import HTTPException
import pytest

from app.services.report_extraction import extract_lab_candidates, extract_page_candidates


def test_parser_extracts_known_labs_with_units_and_page_provenance():
    candidates = extract_page_candidates(
        "HbA1c: 6.2%\nTotal Cholesterol: 184 mg/dL\nFasting Glucose 98 mg/dL",
        page_number=2,
    )
    assert [(item.measurement_type, item.value, item.unit, item.source_page) for item in candidates] == [
        ("hba1c", 6.2, "%", 2),
        ("total_cholesterol", 184.0, "mg/dL", 2),
        ("fasting_glucose", 98.0, "mg/dL", 2),
    ]
    assert all("\n" not in item.source_label for item in candidates)


def test_parser_does_not_guess_units_or_accept_unlabeled_values():
    candidates = extract_page_candidates("HbA1c: 6.2\nResult: 98 mg/dL", page_number=1)
    assert candidates == []


def test_parser_rejects_images_and_non_pdf_documents():
    with pytest.raises(HTTPException) as error:
        extract_lab_candidates(b"\x89PNG\r\n")
    assert error.value.status_code == 415
