"""Verify a running local, isolated-container, or Kubernetes API."""

import argparse
import json
import math
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path


def request(base: str, path: str, payload=None):
    body = json.dumps(payload).encode() if payload is not None else None
    message = urllib.request.Request(
        base.rstrip("/") + path, data=body, headers={"Content-Type": "application/json"}
    )
    handlers = []
    if urllib.parse.urlsplit(base).hostname in {"localhost", "127.0.0.1", "::1"}:
        handlers.append(urllib.request.ProxyHandler({}))
    opener = urllib.request.build_opener(*handlers)
    try:
        with opener.open(message, timeout=5) as response:
            return response.status, response.read().decode()
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode()


def verify(base: str, model_dir: Path | None, expected_version: str | None) -> dict:
    deadline = time.monotonic() + 60
    while True:
        try:
            status, text = request(base, "/readyz")
            if status == 200:
                break
        except (OSError, TimeoutError):
            pass
        if time.monotonic() >= deadline:
            raise RuntimeError("API did not become ready within 60 seconds")
        time.sleep(0.5)
    ready = json.loads(text)
    patient = json.loads(Path("examples/patient.json").read_text())
    status, text = request(base, "/predict", patient)
    if status != 200:
        raise AssertionError(f"Valid prediction failed: HTTP {status}")
    prediction = json.loads(text)
    if prediction["prediction"] not in (0, 1):
        raise AssertionError("Invalid predicted class")
    for key in ("confidence", "disease_probability"):
        if not math.isfinite(prediction[key]) or not 0 <= prediction[key] <= 1:
            raise AssertionError(f"Invalid {key}")
    probability = prediction["disease_probability"]
    expected_class = int(probability >= 0.5)
    if prediction["prediction"] != expected_class:
        raise AssertionError("Decision threshold mismatch")
    expected_confidence = probability if expected_class else 1 - probability
    if not math.isclose(prediction["confidence"], expected_confidence, abs_tol=1e-12):
        raise AssertionError("Confidence is not the returned class probability")
    if ready["model_version"] != prediction["model_version"]:
        raise AssertionError("Readiness and prediction identify different models")
    if expected_version and prediction["model_version"] != expected_version:
        raise AssertionError("Served model differs from the release manifest")
    if model_dir:
        from heart_risk.inference import ModelService

        expected = ModelService(model_dir).predict(patient)
        if expected["model_version"] != prediction["model_version"]:
            raise AssertionError("Offline model version differs")
        if not math.isclose(expected["disease_probability"], probability, abs_tol=1e-8):
            raise AssertionError("Offline and served probabilities differ")
    invalid_status, _ = request(base, "/predict", {**patient, "thal": 0})
    if invalid_status != 422:
        raise AssertionError("Invalid category was not rejected")
    status, metrics = request(base, "/metrics")
    if status != 200 or "heart_predictions_total" not in metrics:
        raise AssertionError("Prediction metrics are missing")
    return {
        "verified_at": datetime.now(UTC).isoformat(),
        "base_url": base,
        "status": "passed",
        "prediction": prediction,
        "invalid_status": invalid_status,
        "metrics_available": True,
        "offline_parity_checked": model_dir is not None,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--model-dir", type=Path)
    parser.add_argument("--expected-version")
    parser.add_argument("--output", type=Path, default=Path("reports/evidence/api-smoke.json"))
    arguments = parser.parse_args()
    result = verify(arguments.url, arguments.model_dir, arguments.expected_version)
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
