"""Lazy, versioned inference adapters for the local CareKey Keras models."""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd


MODEL_DIR = Path(__file__).resolve().parents[3] / "ML-models"
MODEL_LIMITATIONS = (
    "Academic prototype output only; not clinically validated for CareKey patients.",
    "A low model score does not rule out disease. Do not use this output for diagnosis or treatment decisions.",
    "The displayed probability is the model's sigmoid output and must not be interpreted as a calibrated clinical risk.",
)


@dataclass(frozen=True)
class ModelSpec:
    key: str
    name: str
    category: str
    purpose: str
    dataset: str
    metrics: str
    model_file: str
    scaler_file: str
    features: tuple[str, ...]
    defaults: dict[str, int | float]
    field_specs: tuple[dict[str, Any], ...]

    @property
    def version(self) -> str:
        digest = hashlib.sha256()
        for filename in (self.model_file, self.scaler_file):
            path = MODEL_DIR / filename
            if not path.is_file():
                return "unavailable"
            with path.open("rb") as artifact:
                for chunk in iter(lambda: artifact.read(1024 * 1024), b""):
                    digest.update(chunk)
        return f"sha256:{digest.hexdigest()[:32]}"


def _binary(name: str, label: str) -> dict[str, Any]:
    return {"name": name, "label": label, "type": "boolean", "options": [{"value": 0, "label": "No"}, {"value": 1, "label": "Yes"}]}


def _brfss_fields(diabetes: bool) -> tuple[dict[str, Any], ...]:
    fields: list[dict[str, Any]] = [
        _binary("HighBP", "High blood pressure"), _binary("HighChol", "High cholesterol"),
        _binary("CholCheck", "Cholesterol checked within five years"),
        {"name": "BMI", "label": "Body mass index (kg/m²)", "type": "number", "min": 10, "max": 100, "step": 0.1},
        _binary("Smoker", "Smoked at least 100 cigarettes in your life"), _binary("Stroke", "Ever told you had a stroke"),
    ]
    if diabetes:
        fields.append(_binary("HeartDiseaseorAttack", "Coronary heart disease or heart attack"))
    fields.extend([
        _binary("PhysActivity", "Physical activity in the past 30 days"), _binary("Fruits", "Consume fruit at least once daily"),
        _binary("Veggies", "Consume vegetables at least once daily"), _binary("HvyAlcoholConsump", "Heavy alcohol consumption"),
        _binary("AnyHealthcare", "Have healthcare coverage"), _binary("NoDocbcCost", "Could not see a doctor due to cost"),
        {"name": "GenHlth", "label": "General health", "type": "select", "options": [
            {"value": 1, "label": "Excellent"}, {"value": 2, "label": "Very good"}, {"value": 3, "label": "Good"},
            {"value": 4, "label": "Fair"}, {"value": 5, "label": "Poor"}]},
        {"name": "MentHlth", "label": "Days mental health was not good (past 30 days)", "type": "number", "min": 0, "max": 30, "step": 1},
        {"name": "PhysHlth", "label": "Days physical health was not good (past 30 days)", "type": "number", "min": 0, "max": 30, "step": 1},
        _binary("DiffWalk", "Difficulty walking or climbing stairs"),
        {"name": "Sex", "label": "Sex used by the source dataset", "type": "select", "options": [{"value": 0, "label": "Female"}, {"value": 1, "label": "Male"}]},
        {"name": "Age", "label": "Age group", "type": "select", "options": [
            {"value": 1, "label": "18–24"}, {"value": 2, "label": "25–29"}, {"value": 3, "label": "30–34"},
            {"value": 4, "label": "35–39"}, {"value": 5, "label": "40–44"}, {"value": 6, "label": "45–49"},
            {"value": 7, "label": "50–54"}, {"value": 8, "label": "55–59"}, {"value": 9, "label": "60–64"},
            {"value": 10, "label": "65–69"}, {"value": 11, "label": "70–74"}, {"value": 12, "label": "75–79"}, {"value": 13, "label": "80+"}]},
        {"name": "Education", "label": "Education category", "type": "select", "options": [
            {"value": 1, "label": "Never attended or kindergarten"}, {"value": 2, "label": "Grades 1–8"}, {"value": 3, "label": "Grades 9–11"},
            {"value": 4, "label": "Grade 12 or GED"}, {"value": 5, "label": "College 1–3 years"}, {"value": 6, "label": "College 4+ years"}]},
        {"name": "Income", "label": "Annual household income category", "type": "select", "options": [
            {"value": 1, "label": "Under $10,000"}, {"value": 2, "label": "$10,000–$15,000"}, {"value": 3, "label": "$15,000–$20,000"},
            {"value": 4, "label": "$20,000–$25,000"}, {"value": 5, "label": "$25,000–$35,000"}, {"value": 6, "label": "$35,000–$50,000"},
            {"value": 7, "label": "$50,000–$75,000"}, {"value": 8, "label": "$75,000 or more"}]},
    ])
    if not diabetes:
        fields.append(_binary("Diabetes_binary", "Ever told you had diabetes"))
    return tuple(fields)


DIABETES_FEATURES = ("HighBP", "HighChol", "CholCheck", "BMI", "Smoker", "Stroke", "HeartDiseaseorAttack", "PhysActivity", "Fruits", "Veggies", "HvyAlcoholConsump", "AnyHealthcare", "NoDocbcCost", "GenHlth", "MentHlth", "PhysHlth", "DiffWalk", "Sex", "Age", "Education", "Income")
HEART_FEATURES = ("HighBP", "HighChol", "CholCheck", "BMI", "Smoker", "Stroke", "PhysActivity", "Fruits", "Veggies", "HvyAlcoholConsump", "AnyHealthcare", "NoDocbcCost", "GenHlth", "MentHlth", "PhysHlth", "DiffWalk", "Sex", "Age", "Education", "Income", "Diabetes_binary")
CANCER_FEATURES = ("GENDER", "AGE", "SMOKING", "YELLOW_FINGERS", "ANXIETY", "PEER_PRESSURE", "CHRONIC DISEASE", "FATIGUE", "ALLERGY", "WHEEZING", "ALCOHOL CONSUMING", "COUGHING", "SHORTNESS OF BREATH", "SWALLOWING DIFFICULTY", "CHEST PAIN")

DIABETES_DEFAULTS = dict(zip(DIABETES_FEATURES, (0, 0, 1, 27.0, 0, 0, 0, 1, 1, 1, 0, 1, 0, 2, 0, 0, 0, 0, 8, 5, 7)))
HEART_DEFAULTS = dict(zip(HEART_FEATURES, (0, 0, 1, 27.0, 0, 0, 1, 1, 1, 0, 1, 0, 2, 0, 0, 0, 0, 8, 5, 7, 0)))
CANCER_DEFAULTS = dict(zip(CANCER_FEATURES, (0, 50, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)))

_cancer_fields = (
    {"name": "GENDER", "label": "Gender", "type": "select", "options": [{"value": 0, "label": "Female"}, {"value": 1, "label": "Male"}]},
    {"name": "AGE", "label": "Age (years)", "type": "number", "min": 18, "max": 120, "step": 1},
    *tuple(_binary(name, label) for name, label in zip(CANCER_FEATURES[2:], ("Smoking", "Yellow fingers", "Anxiety", "Peer pressure", "Chronic disease", "Fatigue", "Allergy", "Wheezing", "Alcohol consumption", "Coughing", "Shortness of breath", "Swallowing difficulty", "Chest pain"))),
)

SPECS: dict[str, ModelSpec] = {
    "diabetes_brfss": ModelSpec("diabetes_brfss", "Diabetes health indicators", "diabetes", "Experimental binary classification using CDC BRFSS health indicators.", "CDC Diabetes Health Indicators (BRFSS), 253,680 rows", "Test ROC-AUC 0.8237; positive recall 0.79", "diabetes_model.keras", "diabetes_scaler.pkl", DIABETES_FEATURES, DIABETES_DEFAULTS, _brfss_fields(True)),
    "heart_disease_brfss": ModelSpec("heart_disease_brfss", "Heart disease health indicators", "cardiovascular", "Experimental classification of the BRFSS heart disease target.", "CDC Heart Disease / BRFSS Indicators, 253,680 rows; target HeartDiseaseorAttack", "Test ROC-AUC approximately 0.83", "heart_model.keras", "heart_scaler.pkl", HEART_FEATURES, HEART_DEFAULTS, _brfss_fields(False)),
    "lung_cancer_survey": ModelSpec("lung_cancer_survey", "Lung cancer survey classifier", "lung_cancer", "Experimental classification from a symptom and behavior survey; not imaging analysis.", "Lung Cancer Survey Dataset; target LUNG_CANCER", "No evaluation metric provided", "cancer_model.keras", "cancer_scaler.pkl", CANCER_FEATURES, CANCER_DEFAULTS, tuple(_cancer_fields)),
}


class ModelUnavailable(RuntimeError):
    """Model assets or runtime could not be loaded; callers must fail closed."""


def validate_inputs(model_key: str, values: dict[str, Any]) -> dict[str, int | float]:
    spec = SPECS[model_key]
    if set(values) != set(spec.features):
        missing = sorted(set(spec.features) - set(values))
        extra = sorted(set(values) - set(spec.features))
        raise ValueError(f"Input fields do not match the model contract (missing={missing}, extra={extra})")
    checked: dict[str, int | float] = {}
    for field in spec.field_specs:
        name = field["name"]
        value = values[name]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f"{name} must be a finite numeric value")
        if value < field.get("min", -math.inf) or value > field.get("max", math.inf):
            raise ValueError(f"{name} is outside its allowed range")
        if field["type"] in ("boolean", "select"):
            allowed = {option["value"] for option in field["options"]}
            if value not in allowed:
                raise ValueError(f"{name} has an unsupported encoded value")
        if field["type"] == "number" and field.get("step") == 1 and int(value) != value:
            raise ValueError(f"{name} must be an integer")
        checked[name] = int(value) if field["type"] in ("boolean", "select") or field.get("step") == 1 else float(value)
    return checked


@lru_cache(maxsize=3)
def _load_model(model_key: str):
    spec = SPECS[model_key]
    model_path, scaler_path = MODEL_DIR / spec.model_file, MODEL_DIR / spec.scaler_file
    if not model_path.is_file() or not scaler_path.is_file():
        raise ModelUnavailable("Model artifacts are missing")
    try:
        import tensorflow as tf
        scaler = joblib.load(scaler_path)
        model = tf.keras.models.load_model(model_path, compile=False)
    except Exception as exc:
        raise ModelUnavailable("Model artifacts could not be loaded by the configured inference runtime") from exc
    if getattr(scaler, "n_features_in_", None) != len(spec.features):
        raise ModelUnavailable("Scaler input dimension does not match the documented model contract")
    if tuple(getattr(scaler, "feature_names_in_", ())) != spec.features:
        raise ModelUnavailable("Scaler feature order does not match the documented model contract")
    if tuple(model.input_shape[1:]) != (len(spec.features),) or tuple(model.output_shape[1:]) != (1,):
        raise ModelUnavailable("Keras model dimensions do not match the documented contract")
    return model, scaler


def predict(model_key: str, values: dict[str, Any]) -> dict[str, Any]:
    spec = SPECS[model_key]
    checked = validate_inputs(model_key, values)
    model, scaler = _load_model(model_key)
    frame = pd.DataFrame([[checked[name] for name in spec.features]], columns=spec.features)
    try:
        scaled = scaler.transform(frame)
        output = np.asarray(model.predict(scaled, verbose=0), dtype=float)
    except Exception as exc:
        raise ModelUnavailable("Model preprocessing or inference failed") from exc
    if output.shape != (1, 1) or not np.isfinite(output[0, 0]) or not 0 <= output[0, 0] <= 1:
        raise ModelUnavailable("Model returned an invalid sigmoid output")
    probability = float(output[0, 0])
    return {"sigmoid_output": probability, "threshold": 0.5, "category": "high_risk" if probability >= 0.5 else "low_risk", "output_semantics": "un-calibrated sigmoid classifier output; not a clinical risk probability"}


@lru_cache(maxsize=3)
def model_available(model_key: str) -> bool:
    try:
        predict(model_key, SPECS[model_key].defaults)
    except (ModelUnavailable, ValueError, KeyError):
        return False
    return True
