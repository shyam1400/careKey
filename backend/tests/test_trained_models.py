import pytest

from app.services import trained_models


@pytest.mark.parametrize("model_key", list(trained_models.SPECS))
def test_local_model_loads_and_runs_real_inference(model_key):
    spec = trained_models.SPECS[model_key]
    result = trained_models.predict(model_key, spec.defaults)
    assert 0 <= result["sigmoid_output"] <= 1
    assert result["category"] in {"high_risk", "low_risk"}
    assert result["threshold"] == 0.5
    model, scaler = trained_models._load_model(model_key)
    assert model.input_shape[-1] == len(spec.features)
    assert scaler.n_features_in_ == len(spec.features)


@pytest.mark.parametrize("model_key", list(trained_models.SPECS))
def test_model_rejects_missing_extra_and_invalid_inputs(model_key):
    spec = trained_models.SPECS[model_key]
    with pytest.raises(ValueError):
        trained_models.validate_inputs(model_key, {})
    with pytest.raises(ValueError):
        trained_models.validate_inputs(model_key, {**spec.defaults, "unexpected": 1})
    invalid = dict(spec.defaults)
    invalid[spec.features[0]] = float("nan")
    with pytest.raises(ValueError):
        trained_models.validate_inputs(model_key, invalid)


def test_model_rejects_wrong_feature_dimension():
    spec = trained_models.SPECS["diabetes_brfss"]
    invalid = dict(spec.defaults)
    invalid.pop(spec.features[-1])
    with pytest.raises(ValueError):
        trained_models.validate_inputs(spec.key, invalid)


def test_model_inference_failure_is_failed_closed(monkeypatch):
    def fail(_key):
        raise trained_models.ModelUnavailable("test failure")

    monkeypatch.setattr(trained_models, "_load_model", fail)
    with pytest.raises(trained_models.ModelUnavailable):
        trained_models.predict("diabetes_brfss", trained_models.SPECS["diabetes_brfss"].defaults)


def test_missing_model_weights_fail_closed(monkeypatch, tmp_path):
    monkeypatch.setattr(trained_models, "MODEL_DIR", tmp_path)
    trained_models._load_model.cache_clear()
    with pytest.raises(trained_models.ModelUnavailable, match="artifacts are missing"):
        trained_models.predict("diabetes_brfss", trained_models.SPECS["diabetes_brfss"].defaults)
    trained_models._load_model.cache_clear()


def test_preprocessing_failure_fails_closed(monkeypatch):
    class BadScaler:
        def transform(self, _frame):
            raise RuntimeError("bad preprocessing")

    class Model:
        def predict(self, *_args, **_kwargs):
            return [[0.5]]

    monkeypatch.setattr(trained_models, "_load_model", lambda _key: (Model(), BadScaler()))
    with pytest.raises(trained_models.ModelUnavailable, match="preprocessing or inference failed"):
        trained_models.predict("diabetes_brfss", trained_models.SPECS["diabetes_brfss"].defaults)
