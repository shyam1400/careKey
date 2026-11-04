import pytest
from datetime import datetime, timezone
from uuid import uuid4
from fastapi import HTTPException

from app.api.assessments import generate_assessment
from app.models.audit import AccessLog
from app.models.enums import AppRole
from app.models.patient import Patient
from app.models.profile import Profile
from app.models.user import User
from app.services.assessment_engine import TOOLS, run_calculator


def test_initial_tools_have_population_license_and_use_gates():
    assert set(TOOLS) == {"prevent_cvd", "idrs_type2_diabetes", "qdiabetes_2018", "bcrat_breast_cancer", "who_2019_south_asia_cvd"}
    assert all(tool.availability == "disabled" for key, tool in TOOLS.items() if key != "who_2019_south_asia_cvd")
    assert TOOLS["who_2019_south_asia_cvd"].availability == "enabled"
    assert "U.S." in TOOLS["prevent_cvd"].validated_population
    assert "not future-onset prediction" in TOOLS["idrs_type2_diabetes"].intended_use
    assert "UK adults" in TOOLS["qdiabetes_2018"].validated_population
    assert "BRCA1/2" in " ".join(TOOLS["bcrat_breast_cancer"].limitations)


def test_unlicensed_or_unimplemented_calculator_never_returns_a_score():
    with pytest.raises(PermissionError):
        run_calculator("prevent_cvd", {"age": 54})


def test_unknown_calculator_is_rejected():
    with pytest.raises(KeyError):
        run_calculator("invented_model", {})


def test_disabled_assessment_attempt_is_audited(monkeypatch):
    from app.api import assessments

    patient_id = uuid4()
    user = User(id=patient_id, firebase_uid="uid", role=AppRole.PATIENT, is_active=True)

    class Db:
        def __init__(self):
            self.added = []

        def scalar(self, statement):
            entity = statement.column_descriptions[0]["entity"]
            if entity is Patient:
                return patient_id
            if entity is Profile:
                return None
            return None

        def add(self, row): self.added.append(row)
        def commit(self): pass

    db = Db()
    monkeypatch.setattr(assessments, "run_calculator", lambda *_args: (_ for _ in ()).throw(PermissionError("license pending")))
    with pytest.raises(HTTPException) as error:
        generate_assessment("prevent_cvd", db, user)
    assert error.value.status_code == 409
    assert any(isinstance(row, AccessLog) and row.access_type == "health_assessment" and not row.success for row in db.added)
