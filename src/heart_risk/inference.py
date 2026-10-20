"""Load only a trusted, version-matched training artifact; never fit on requests."""

import argparse
import importlib.metadata
import json
import platform
from pathlib import Path

import joblib
import pandas as pd

from heart_risk.data import sha256
from heart_risk.modeling import disease_probability, labels_from_probabilities
from heart_risk.schema import FEATURES, SCHEMA_VERSION, validate_features


class ModelService:
    def __init__(self, directory: Path):
        metadata_path = directory / "metadata.json"
        model_path = directory / "pipeline.joblib"
        self.metadata = json.loads(metadata_path.read_text())
        if (
            self.metadata["schema_version"] != SCHEMA_VERSION
            or self.metadata["features"] != FEATURES
        ):
            raise ValueError("Model schema does not match the API contract")
        if self.metadata["classes"] != [0, 1] or self.metadata["threshold"] != 0.5:
            raise ValueError("Model decision contract is incompatible")
        if self.metadata["python"].split(".")[:2] != platform.python_version().split(".")[:2]:
            raise ValueError("Python minor version differs from training")
        for name in ("numpy", "pandas", "scikit-learn", "joblib"):
            if self.metadata["versions"][name] != importlib.metadata.version(name):
                raise ValueError(f"{name} version differs from training; use locked requirements")
        if sha256(model_path) != self.metadata["model_sha256"]:
            raise ValueError("Model checksum mismatch; refusing deserialization")
        self.model = joblib.load(model_path)
        if list(self.model.feature_names_in_) != FEATURES or list(self.model.classes_) != [0, 1]:
            raise ValueError("Serialized model disagrees with metadata")

    def predict(self, record: dict) -> dict:
        normalized = validate_features(record)
        frame = pd.DataFrame([normalized], columns=FEATURES, dtype=float)
        probability = float(disease_probability(self.model, frame)[0])
        prediction = int(labels_from_probabilities([probability], self.metadata["threshold"])[0])
        return {
            "prediction": prediction,
            "disease_probability": probability,
            "confidence": probability if prediction == 1 else 1.0 - probability,
            "model_version": self.metadata["model_version"],
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("examples/patient.json"))
    parser.add_argument("--model-dir", type=Path, default=Path("models"))
    arguments = parser.parse_args()
    print(
        json.dumps(
            ModelService(arguments.model_dir).predict(json.loads(arguments.input.read_text())),
            indent=2,
        )
    )
