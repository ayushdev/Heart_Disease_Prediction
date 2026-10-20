"""Train both families, select by CV, and export an auditable serving artifact."""

import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
import warnings
from pathlib import Path

import joblib
import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd
from mlflow.models import infer_signature
from sklearn.dummy import DummyClassifier
from sklearn.exceptions import ConvergenceWarning
from sklearn.metrics import ConfusionMatrixDisplay, PrecisionRecallDisplay, RocCurveDisplay
from sklearn.model_selection import GridSearchCV, StratifiedKFold, cross_validate

from heart_risk.data import load_partitions, sha256, write_json
from heart_risk.eda import FIGURES, plt, save, style
from heart_risk.modeling import (
    build_pipeline,
    choose_champion,
    disease_probability,
    evaluate,
    labels_from_probabilities,
)
from heart_risk.schema import FEATURES, SCHEMA_VERSION

METRICS = ["accuracy", "precision", "recall", "f1", "roc_auc"]


def environment_versions() -> dict[str, str]:
    return {
        name: importlib.metadata.version(name)
        for name in (
            "numpy",
            "pandas",
            "scikit-learn",
            "joblib",
            "mlflow",
            "fastapi",
            "pydantic",
        )
    }


def log_candidates(family: str, results: dict, folds: int) -> None:
    for index, parameters in enumerate(results["params"]):
        with mlflow.start_run(run_name=f"{family}-candidate-{index:02d}", nested=True):
            mlflow.log_params({"family": family, **parameters})
            scores = {}
            for metric in METRICS:
                scores[f"cv_{metric}_mean"] = float(results[f"mean_test_{metric}"][index])
                scores[f"cv_{metric}_std"] = float(results[f"std_test_{metric}"][index])
            mlflow.log_metrics(scores)
            fold_scores = {
                metric: [
                    float(results[f"split{fold}_test_{metric}"][index]) for fold in range(folds)
                ]
                for metric in METRICS
            }
            mlflow.log_dict(fold_scores, "fold_scores.json")
            figure, axis = plt.subplots(figsize=(6, 3.5))
            axis.plot(range(1, folds + 1), fold_scores["roc_auc"], marker="o", color="#167d8d")
            axis.set(xlabel="Validation fold", ylabel="ROC-AUC", ylim=(0, 1), title=family)
            mlflow.log_figure(figure, "cv_auc.png")
            plt.close(figure)


def evaluation_figures(family: str, labels, probabilities, threshold: float) -> None:
    figure, axes = plt.subplots(1, 3, figsize=(14, 4))
    RocCurveDisplay.from_predictions(labels, probabilities, ax=axes[0], name=family)
    PrecisionRecallDisplay.from_predictions(labels, probabilities, ax=axes[1], name=family)
    ConfusionMatrixDisplay.from_predictions(
        labels,
        labels_from_probabilities(probabilities, threshold),
        ax=axes[2],
        colorbar=False,
        cmap="Blues",
        display_labels=["Absent", "Present"],
    )
    figure.suptitle(f"Locked holdout evaluation | {family}")
    figure.tight_layout()
    save(figure, f"{family}_evaluation.png")


def run() -> dict:
    config_path = Path("configs/training.json")
    config = json.loads(config_path.read_text())
    if config["selection_metric"] != "roc_auc" or config["threshold"] != 0.5:
        raise ValueError("This experiment fixes ROC-AUC selection and the 0.5 threshold")
    training, testing = load_partitions()
    features, labels = training[FEATURES], training.target
    holdout_features, holdout_labels = testing[FEATURES], testing.target
    style()
    warnings.filterwarnings("error", category=ConvergenceWarning)
    mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", "sqlite:///mlflow.db"))
    experiment_name = "cleveland-heart-risk"
    experiment = mlflow.get_experiment_by_name(experiment_name)
    if experiment is None:
        mlflow.create_experiment(
            experiment_name, artifact_location=Path("mlartifacts").resolve().as_uri()
        )
    mlflow.set_experiment(experiment_name)
    cv = StratifiedKFold(n_splits=config["folds"], shuffle=True, random_state=config["seed"])
    models, cv_scores, comparison = {}, {}, {}
    model_dir = Path("models")
    model_dir.mkdir(exist_ok=True)
    with mlflow.start_run(run_name="two-family-selection") as parent:
        mlflow.log_params(
            {
                "seed": config["seed"],
                "folds": config["folds"],
                "threshold": config["threshold"],
                "selection": "training_cv_roc_auc",
                "numeric_imputation": "median",
                "categorical_imputation": "most_frequent",
                "encoding": "one_hot",
                "train_rows": len(training),
                "holdout_rows": len(testing),
            }
        )
        mlflow.log_dict(config, "training_config.json")
        mlflow.log_artifact("data/manifest.json", "provenance")
        mlflow.log_artifact("data/processed/split.json", "provenance")
        mlflow.log_dict(environment_versions(), "environment.json")
        for family, grid in config["grids"].items():
            print(f"Cross-validating {family}", flush=True)
            search = GridSearchCV(
                build_pipeline(family, config["seed"]),
                grid,
                scoring=METRICS,
                refit="roc_auc",
                cv=cv,
                n_jobs=1,
                error_score="raise",
                return_train_score=False,
            ).fit(features, labels)
            models[family] = search.best_estimator_
            cv_scores[family] = float(search.best_score_)
            if not np.isfinite(search.cv_results_["mean_test_roc_auc"]).all():
                raise ValueError("Non-finite cross-validation metrics")
            log_candidates(family, search.cv_results_, config["folds"])
            pd.DataFrame(search.cv_results_).to_csv(f"reports/{family}_cv.csv", index=False)
            comparison[family] = {
                "parameters": search.best_params_,
                "cv": {
                    metric: {
                        "mean": float(
                            search.cv_results_[f"mean_test_{metric}"][search.best_index_]
                        ),
                        "std": float(search.cv_results_[f"std_test_{metric}"][search.best_index_]),
                    }
                    for metric in METRICS
                },
            }

        champion = choose_champion(cv_scores)
        mlflow.set_tag("champion_locked_before_holdout", champion)
        baseline = cross_validate(
            DummyClassifier(strategy="prior"),
            features,
            labels,
            cv=cv,
            scoring="roc_auc",
            error_score="raise",
        )
        for family, model in models.items():
            probabilities = disease_probability(model, holdout_features)
            measured = evaluate(holdout_labels, probabilities, config["threshold"])
            comparison[family]["holdout"] = measured
            evaluation_figures(family, holdout_labels, probabilities, config["threshold"])
            with mlflow.start_run(run_name=f"{family}-locked-winner", nested=True):
                mlflow.log_params(comparison[family]["parameters"])
                mlflow.log_metrics({f"holdout_{key}": value for key, value in measured.items()})
                mlflow.log_dict(comparison[family]["cv"], "cv_summary.json")
                mlflow.log_artifact(str(FIGURES / f"{family}_evaluation.png"))
                sample = features.head(3).astype(float)
                mlflow.sklearn.log_model(
                    model,
                    name="pipeline",
                    input_example=sample,
                    serialization_format="cloudpickle",
                    signature=infer_signature(sample, model.predict(sample)),
                    pip_requirements=[
                        f"{name}=={version}" for name, version in environment_versions().items()
                    ],
                )

        selected = models[champion]
        model_path = model_dir / "pipeline.joblib"
        joblib.dump(selected, model_path, compress=3)
        np.testing.assert_allclose(
            disease_probability(selected, holdout_features),
            disease_probability(joblib.load(model_path), holdout_features),
            rtol=1e-12,
            atol=1e-12,
        )
        model_hash = sha256(model_path)
        source_hash = hashlib.sha256(
            b"".join(path.read_bytes() for path in sorted(Path("src/heart_risk").glob("*.py")))
        ).hexdigest()
        metadata = {
            "family": champion,
            "model_version": model_hash[:12],
            "model_sha256": model_hash,
            "features": FEATURES,
            "schema_version": SCHEMA_VERSION,
            "classes": [0, 1],
            "threshold": config["threshold"],
            "python": platform.python_version(),
            "versions": environment_versions(),
            "run_id": parent.info.run_id,
            "source_revision": os.environ.get("GITHUB_SHA", "local-uncommitted"),
            "source_sha256": source_hash,
            "config_sha256": sha256(config_path),
            "data_sha256": sha256(Path("data/processed/heart_clean.csv")),
            "split_sha256": sha256(Path("data/processed/split.json")),
            "confidence_semantics": "Probability of the returned class; not medical certainty",
        }
        write_json(model_dir / "metadata.json", metadata)
        result = {
            "champion": champion,
            "run_id": parent.info.run_id,
            "selection": "Five-fold training CV ROC-AUC; holdout excluded from selection",
            "train_rows": len(training),
            "test_rows": len(testing),
            "baseline_cv_auc": float(np.mean(baseline["test_score"])),
            "models": comparison,
            "model_version": metadata["model_version"],
        }
        write_json(Path("reports/results.json"), result)
        mlflow.log_metrics(
            {
                f"champion_holdout_{key}": value
                for key, value in comparison[champion]["holdout"].items()
            }
        )
        mlflow.log_artifacts(str(model_dir), "serving_bundle")
        mlflow.log_artifacts(str(FIGURES), "figures")
        mlflow.log_artifact("reports/results.json")
        for family in models:
            mlflow.log_artifact(f"reports/{family}_cv.csv")
        environment = subprocess.check_output([os.sys.executable, "-m", "pip", "freeze"], text=True)
        Path("reports/environment.txt").write_text(environment, encoding="utf-8")
        mlflow.log_artifact("reports/environment.txt")
    print(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    run()
