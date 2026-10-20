import importlib.metadata
import json
import platform
from pathlib import Path

import joblib
import pytest
from fastapi.testclient import TestClient

from heart_risk.api import create_app
from heart_risk.data import sha256, write_json
from heart_risk.inference import ModelService
from heart_risk.modeling import build_pipeline
from heart_risk.schema import FEATURES, SCHEMA_VERSION


@pytest.fixture
def bundle(sample_frame, tmp_path):
    model = build_pipeline("logistic_regression").fit(sample_frame[FEATURES], sample_frame.target)
    path = tmp_path / "pipeline.joblib"
    joblib.dump(model, path)
    write_json(
        tmp_path / "metadata.json",
        {
            "schema_version": SCHEMA_VERSION,
            "features": FEATURES,
            "classes": [0, 1],
            "threshold": 0.5,
            "python": platform.python_version(),
            "model_version": "test-model",
            "model_sha256": sha256(path),
            "versions": {
                name: importlib.metadata.version(name)
                for name in ("numpy", "pandas", "scikit-learn", "joblib")
            },
        },
    )
    return tmp_path


@pytest.fixture
def patient(sample_frame):
    return sample_frame.iloc[1][FEATURES].to_dict()


def test_openapi_example_is_accepted(bundle):
    with TestClient(create_app(bundle)) as client:
        schema = client.get("/openapi.json").json()["components"]["schemas"]["Patient"]
        example = schema["examples"][0]
        assert example == json.loads(Path("examples/patient.json").read_text())
        assert schema["properties"]["ca"]["enum"] == [0, 1, 2, 3, None]
        assert schema["properties"]["thal"]["enum"] == [3, 6, 7, None]
        assert client.post("/predict", json=example).status_code == 200


def test_prediction_parity_metrics_and_private_logs(bundle, patient, caplog):
    expected = ModelService(bundle).predict(patient)
    with TestClient(create_app(bundle)) as client:
        assert client.get("/readyz").status_code == 200
        response = client.post("/predict", json=patient)
        assert response.status_code == 200
        actual = response.json()
        for key, value in expected.items():
            assert actual[key] == value
        assert actual["request_id"] == response.headers["X-Request-ID"]
        assert actual["confidence"] == pytest.approx(
            max(actual["disease_probability"], 1 - actual["disease_probability"])
        )
        metrics = client.get("/metrics").text
        assert "heart_predictions_total{prediction=" in metrics
        assert 'route="/predict",status="200"' in metrics
    records = [
        json.loads(record.message)
        for record in caplog.records
        if record.name == "heart_risk.requests"
    ]
    assert records and all("chol" not in record and "age" not in record for record in records)


@pytest.mark.parametrize(
    "change", [{"thal": 0}, {"cp": 0}, {"age": -1}, {"sex": True}, {"chol": "233"}, {"extra": 1}]
)
def test_invalid_inputs_are_rejected(bundle, patient, change):
    with TestClient(create_app(bundle)) as client:
        assert client.post("/predict", json={**patient, **change}).status_code == 422


def test_missing_keys_and_nullable_features(bundle, patient):
    with TestClient(create_app(bundle)) as client:
        assert client.post("/predict", json={}).status_code == 422
        assert (
            client.post("/predict", json={**patient, "ca": None, "thal": None}).status_code == 200
        )
        assert client.post("/predict", json={**patient, "age": None}).status_code == 422


def test_corrupt_model_and_incompatible_metadata_fail_before_loading(bundle):
    (bundle / "pipeline.joblib").write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="checksum"):
        ModelService(bundle)
    with pytest.raises(FileNotFoundError):
        ModelService(bundle / "absent")


def test_unmatched_routes_have_bounded_labels(bundle):
    with TestClient(create_app(bundle)) as client:
        client.get("/patient/sensitive-id")
        metrics = client.get("/metrics").text
        assert 'route="unmatched"' in metrics
        assert "sensitive-id" not in metrics
