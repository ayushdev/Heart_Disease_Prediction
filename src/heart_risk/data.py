"""Verified acquisition, deterministic cleaning, and holdout isolation."""

import argparse
import csv
import hashlib
import io
import json
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd
from sklearn.model_selection import train_test_split

from heart_risk.schema import FEATURES, SCHEMA_VERSION, parse_row

SOURCE_URL = "https://archive.ics.uci.edu/static/public/45/heart+disease.zip"
RAW_PATH = Path("data/raw/processed.cleveland.data")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def download_raw(path: Path = RAW_PATH, force: bool = False) -> Path:
    checksum_path = path.with_suffix(".sha256")
    if path.exists() and not force:
        if not checksum_path.exists() or sha256(path) != checksum_path.read_text().strip():
            raise ValueError("Raw dataset checksum missing or mismatched; restore trusted snapshot")
        return path
    request = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "HeartRiskAssignment/1.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        archive = response.read(10_000_001)
    if len(archive) > 10_000_000:
        raise ValueError("Unexpectedly large UCI archive")
    with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
        raw = bundle.read("processed.cleveland.data")
    digest = hashlib.sha256(raw).hexdigest()
    if checksum_path.exists() and digest != checksum_path.read_text().strip():
        raise ValueError("Downloaded source differs from the pinned UCI snapshot")
    clean_data(raw.decode("ascii"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    checksum_path.write_text(digest + "\n", encoding="ascii")
    return path


def clean_data(text: str) -> pd.DataFrame:
    rows = []
    for line_number, values in enumerate(csv.reader(io.StringIO(text)), start=1):
        if not values:
            continue
        try:
            rows.append(parse_row(values))
        except (ValueError, TypeError) as error:
            raise ValueError(f"Invalid UCI row {line_number}: {error}") from error
    if not rows:
        raise ValueError("Dataset is empty")
    frame = pd.DataFrame(rows, columns=[*FEATURES, "target"]).drop_duplicates()
    if frame.duplicated(subset=FEATURES).any():
        raise ValueError("Identical features have conflicting targets; inspect source")
    return frame.reset_index(drop=True)


def create_split(frame: pd.DataFrame, seed: int, test_size: float) -> dict:
    train_indices, test_indices = train_test_split(
        frame.index.to_numpy(), test_size=test_size, random_state=seed, stratify=frame.target
    )
    return {
        "seed": seed,
        "test_size": test_size,
        "train_indices": sorted(train_indices.tolist()),
        "test_indices": sorted(test_indices.tolist()),
    }


def prepare(force: bool = False) -> dict:
    config = json.loads(Path("configs/training.json").read_text())
    raw = download_raw(force=force)
    frame = clean_data(raw.read_text(encoding="ascii"))
    if len(frame) != 303:
        raise ValueError(f"Expected canonical Cleveland 303 records; got {len(frame)}")
    cleaned = Path("data/processed/heart_clean.csv")
    cleaned.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(cleaned, index=False, lineterminator="\n")
    split = create_split(frame, config["seed"], config["test_size"])
    split["dataset_sha256"] = sha256(cleaned)
    write_json(Path("data/processed/split.json"), split)
    manifest = {
        "source": SOURCE_URL,
        "citation": "Janosi et al. (1989), https://doi.org/10.24432/C52P4X",
        "license": "CC BY 4.0",
        "schema": SCHEMA_VERSION,
        "raw_sha256": sha256(raw),
        "clean_sha256": sha256(cleaned),
        "rows": len(frame),
        "features": FEATURES,
        "missing": frame.isna().sum().to_dict(),
        "class_counts": frame.target.value_counts().sort_index().to_dict(),
        "duplicates_removed": len(raw.read_text().strip().splitlines()) - len(frame),
    }
    write_json(Path("data/manifest.json"), manifest)
    return manifest


def load_partitions() -> tuple[pd.DataFrame, pd.DataFrame]:
    path = Path("data/processed/heart_clean.csv")
    split = json.loads(Path("data/processed/split.json").read_text())
    config = json.loads(Path("configs/training.json").read_text())
    if sha256(path) != split["dataset_sha256"]:
        raise ValueError("Cleaned dataset checksum does not match split manifest")
    if (config["seed"], config["test_size"]) != (split["seed"], split["test_size"]):
        raise ValueError("Split settings changed; rerun data preparation")
    frame = pd.read_csv(path)
    train_ids, test_ids = split["train_indices"], split["test_indices"]
    if set(train_ids) & set(test_ids) or sorted(train_ids + test_ids) != list(range(len(frame))):
        raise ValueError("Split is overlapping, duplicated, or incomplete")
    return frame.iloc[train_ids].copy(), frame.iloc[test_ids].copy()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download-again", action="store_true")
    arguments = parser.parse_args()
    print(json.dumps(prepare(arguments.download_again), indent=2))
