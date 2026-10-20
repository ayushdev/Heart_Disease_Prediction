"""Leakage-resistant estimators and consistent binary decision semantics."""

import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from heart_risk.schema import CATEGORIES, NUMERIC


def build_pipeline(family: str, seed: int = 42) -> Pipeline:
    numeric = Pipeline([("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler())])
    categorical = Pipeline(
        [
            ("impute", SimpleImputer(strategy="most_frequent")),
            ("encode", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
        ]
    )
    preprocess = ColumnTransformer(
        [
            ("numeric", numeric, NUMERIC),
            ("categorical", categorical, list(CATEGORIES)),
        ]
    )
    if family == "logistic_regression":
        classifier = LogisticRegression(max_iter=3000, random_state=seed)
    elif family == "random_forest":
        classifier = RandomForestClassifier(n_estimators=200, random_state=seed, n_jobs=1)
    else:
        raise ValueError(f"Unknown model family: {family}")
    return Pipeline([("preprocess", preprocess), ("classifier", classifier)])


def disease_probability(model, features) -> np.ndarray:
    classes = list(model.classes_)
    if classes != [0, 1]:
        raise ValueError(f"Expected binary classes [0, 1]; got {classes}")
    probabilities = model.predict_proba(features)[:, classes.index(1)]
    if not np.isfinite(probabilities).all() or ((probabilities < 0) | (probabilities > 1)).any():
        raise ValueError("Model returned invalid probabilities")
    return probabilities


def labels_from_probabilities(probabilities, threshold: float = 0.5) -> np.ndarray:
    return (np.asarray(probabilities) >= threshold).astype(int)


def evaluate(labels, probabilities, threshold: float = 0.5) -> dict[str, float]:
    predictions = labels_from_probabilities(probabilities, threshold)
    return {
        "accuracy": float(accuracy_score(labels, predictions)),
        "precision": float(precision_score(labels, predictions, zero_division=0)),
        "recall": float(recall_score(labels, predictions, zero_division=0)),
        "f1": float(f1_score(labels, predictions, zero_division=0)),
        "roc_auc": float(roc_auc_score(labels, probabilities)),
    }


def choose_champion(scores: dict[str, float]) -> str:
    if not scores or not all(np.isfinite(value) for value in scores.values()):
        raise ValueError("Model selection requires finite CV scores")
    best = max(scores.values())
    if "logistic_regression" in scores and best - scores["logistic_regression"] <= 1e-12:
        return "logistic_regression"
    return max(scores, key=scores.get)
