"""Tie a tested image digest to its model, or render a deployment from that release."""

import argparse
import json
import os
import re
from pathlib import Path


def validate_image(image: str) -> str:
    if not re.fullmatch(r"ghcr\.io/[a-z0-9_./-]+@sha256:[a-f0-9]{64}", image):
        raise ValueError("Expected an immutable ghcr.io image@sha256:<64 hex digits>")
    return image


def create_release(image: str, metadata: dict) -> dict:
    return {
        "image": validate_image(image),
        "model_version": metadata["model_version"],
        "model_sha256": metadata["model_sha256"],
        "data_sha256": metadata["data_sha256"],
        "source_revision": metadata["source_revision"],
        "ci_url": (
            f"https://github.com/{os.environ['GITHUB_REPOSITORY']}/actions/runs/"
            f"{os.environ['GITHUB_RUN_ID']}"
        )
        if "GITHUB_RUN_ID" in os.environ
        else None,
    }


def render(release: dict, pull_secret: str | None = None) -> list[dict]:
    import yaml

    documents = list(yaml.safe_load_all(Path("deploy/k8s/api.yaml").read_text()))
    for document in documents:
        if document["kind"] == "Deployment":
            pod = document["spec"]["template"]["spec"]
            pod["containers"][0]["image"] = validate_image(release["image"])
            if pull_secret:
                if not re.fullmatch(r"[a-z0-9][a-z0-9.-]*", pull_secret):
                    raise ValueError("Invalid image-pull Secret name")
                pod["imagePullSecrets"] = [{"name": pull_secret}]
    return documents


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--image")
    mode.add_argument("--render", type=Path)
    parser.add_argument("--pull-secret")
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    if arguments.image:
        result = create_release(
            arguments.image, json.loads(Path("models/metadata.json").read_text())
        )
        text = json.dumps(result, indent=2)
    else:
        import yaml

        result = render(json.loads(arguments.render.read_text()), arguments.pull_secret)
        text = yaml.safe_dump_all(result, sort_keys=False)
    arguments.output.write_text(text + "\n", encoding="utf-8")
