import importlib.util
import json
from pathlib import Path

import pytest
import yaml

spec = importlib.util.spec_from_file_location("release", Path("scripts/release.py"))
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


def test_release_rejects_mutable_images():
    for image in ("ghcr.io/user/repo:latest", "shell;bad", "local:1"):
        with pytest.raises(ValueError):
            release.validate_image(image)


def test_rendered_deployment_is_immutable_and_probed():
    image = "ghcr.io/example/heart-risk@sha256:" + "a" * 64
    documents = release.render({"image": image})
    deployment = next(document for document in documents if document["kind"] == "Deployment")
    container = deployment["spec"]["template"]["spec"]["containers"][0]
    assert container["image"] == image
    assert all(name in container for name in ("startupProbe", "readinessProbe", "livenessProbe"))
    assert deployment["spec"]["replicas"] == 2
    service = next(document for document in documents if document["kind"] == "Service")
    assert service["spec"]["type"] == "LoadBalancer"


def test_ci_failures_block_training_and_delivery():
    workflow = yaml.safe_load(Path(".github/workflows/ci.yml").read_text())
    assert workflow["jobs"]["train"]["needs"] == "quality"
    assert workflow["jobs"]["container"]["needs"] == "train"
    for job in workflow["jobs"].values():
        assert not job.get("continue-on-error", False)
        for step in job["steps"]:
            assert not step.get("continue-on-error", False)
            if "uses" in step:
                assert len(step["uses"].rsplit("@", 1)[1]) == 40


def test_monitoring_scrapes_individual_pods():
    config = yaml.safe_load(Path("monitoring/prometheus.yml").read_text())
    assert config["scrape_configs"][0]["kubernetes_sd_configs"][0]["role"] == "pod"
    dashboard = json.loads(Path("monitoring/grafana/dashboard.json").read_text())
    assert len(dashboard["panels"]) == 5


def test_monitoring_is_namespace_scoped_and_uses_secret():
    documents = list(yaml.safe_load_all(Path("deploy/k8s/monitoring.yaml").read_text()))
    assert all(document["metadata"]["namespace"] == "heart-risk" for document in documents)
    role = next(document for document in documents if document["kind"] == "Role")
    assert role["rules"][0]["resources"] == ["pods"]
    grafana = next(
        document
        for document in documents
        if document["kind"] == "Deployment" and document["metadata"]["name"] == "grafana"
    )
    variables = grafana["spec"]["template"]["spec"]["containers"][0]["env"]
    password = next(
        variable for variable in variables if variable["name"] == "GF_SECURITY_ADMIN_PASSWORD"
    )
    assert password["valueFrom"]["secretKeyRef"]["name"] == "grafana-admin"
