import pytest
from pydantic import ValidationError

from app.api.records import _patch_schema
from app.schemas.record import AllergyCreate, MedicationCreate


def test_record_patch_accepts_partial_values():
    schema = _patch_schema(MedicationCreate)
    assert schema.model_validate({"active": False}).model_dump(exclude_unset=True) == {"active": False}


def test_record_patch_rejects_unknown_fields():
    schema = _patch_schema(AllergyCreate)
    with pytest.raises(ValidationError):
        schema.model_validate({"patient_id": "attacker-controlled"})
