import joblib
import numpy as np
import pytest

from heart_risk.modeling import (
    build_pipeline,
    choose_champion,
    disease_probability,
    evaluate,
    labels_from_probabilities,
)
from heart_risk.schema import FEATURES, NUMERIC


@pytest.mark.parametrize("family", ["logistic_regression", "random_forest"])
def test_pipeline_roundtrip_and_determinism(family, sample_frame, tmp_path):
    features = sample_frame[FEATURES]
    model = build_pipeline(family).fit(features, sample_frame.target)
    expected = disease_probability(model, features)
    path = tmp_path / "pipeline.joblib"
    joblib.dump(model, path)
    np.testing.assert_allclose(expected, disease_probability(joblib.load(path), features))
    repeated = build_pipeline(family).fit(features, sample_frame.target)
    np.testing.assert_allclose(expected, disease_probability(repeated, features))


def test_preprocessing_fits_training_statistics_only(sample_frame):
    training = sample_frame.iloc[:30]
    testing = sample_frame.iloc[30:].copy()
    testing["chol"] = 99999
    model = build_pipeline("logistic_regression").fit(training[FEATURES], training.target)
    preprocess = model.named_steps["preprocess"]
    means = preprocess.named_transformers_["numeric"].named_steps["scale"].mean_.copy()
    np.testing.assert_allclose(means, training[NUMERIC].mean())
    testing["thal"] = 99
    assert np.isfinite(disease_probability(model, testing[FEATURES])).all()
    np.testing.assert_array_equal(means, preprocess.named_transformers_["numeric"]["scale"].mean_)


def test_model_selection_and_probability_semantics():
    assert (
        choose_champion({"random_forest": 0.9, "logistic_regression": 0.9}) == "logistic_regression"
    )
    assert choose_champion({"random_forest": 0.91, "logistic_regression": 0.9}) == "random_forest"
    assert labels_from_probabilities([0.1, 0.5, 0.9]).tolist() == [0, 1, 1]
    assert evaluate([0, 1], [0.1, 0.9])["roc_auc"] == 1.0
    with pytest.raises(ValueError):
        choose_champion({"broken": float("nan")})
