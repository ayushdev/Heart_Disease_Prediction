"""Original UCI Cleveland feature codes shared by acquisition and inference."""

import math

FEATURES = [
    "age",
    "sex",
    "cp",
    "trestbps",
    "chol",
    "fbs",
    "restecg",
    "thalach",
    "exang",
    "oldpeak",
    "slope",
    "ca",
    "thal",
]
NUMERIC = ["age", "trestbps", "chol", "thalach", "oldpeak"]
CATEGORIES = {
    "sex": [0, 1],
    "cp": [1, 2, 3, 4],
    "fbs": [0, 1],
    "restecg": [0, 1, 2],
    "exang": [0, 1],
    "slope": [1, 2, 3],
    "ca": [0, 1, 2, 3],
    "thal": [3, 6, 7],
}
SCHEMA_VERSION = "uci-cleveland-v1"


def validate_features(record: dict) -> dict[str, float | None]:
    if set(record) != set(FEATURES):
        raise ValueError("Expected exactly the 13 original UCI feature names")
    normalized = {}
    for name in FEATURES:
        value = record[name]
        if value is None:
            if name not in {"ca", "thal"}:
                raise ValueError(f"{name} cannot be missing")
            normalized[name] = None
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{name} must be numeric")
        number = float(value)
        if not math.isfinite(number):
            raise ValueError(f"{name} must be finite")
        if name in CATEGORIES and number not in CATEGORIES[name]:
            raise ValueError(f"{name} must use original UCI codes {CATEGORIES[name]}")
        if name in NUMERIC and (number < 0 or (name != "oldpeak" and number == 0)):
            raise ValueError(f"{name} is outside its nonnegative/positive domain")
        normalized[name] = number
    return normalized


def parse_row(values: list[str]) -> dict[str, float | int | None]:
    if len(values) != 14:
        raise ValueError(f"Expected 14 columns; received {len(values)}")
    features = {
        name: None if value.strip() == "?" else float(value)
        for name, value in zip(FEATURES, values[:13], strict=True)
    }
    result = validate_features(features)
    severity = float(values[13])
    if severity not in (0, 1, 2, 3, 4):
        raise ValueError("UCI severity must be an integer from 0 to 4")
    return {**result, "target": int(severity > 0)}
