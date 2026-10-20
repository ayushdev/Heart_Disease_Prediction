"""Training-partition visualizations; holdout values do not guide modelling."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

from heart_risk.data import load_partitions, write_json
from heart_risk.schema import NUMERIC

FIGURES = Path("reports/figures")
PALETTE = ["#167d8d", "#cf5c55"]


def style() -> None:
    sns.set_theme(style="whitegrid", palette=PALETTE, font_scale=1.05)
    FIGURES.mkdir(parents=True, exist_ok=True)


def save(figure, name: str) -> None:
    figure.savefig(FIGURES / name, dpi=170, bbox_inches="tight", facecolor="white")
    plt.close(figure)


def run() -> None:
    training, _ = load_partitions()
    style()
    figure, axes = plt.subplots(2, 3, figsize=(12, 7))
    units = [
        "Age (years)",
        "Resting BP (mm Hg)",
        "Cholesterol (mg/dl)",
        "Maximum heart rate (bpm)",
        "ST depression (oldpeak)",
    ]
    for axis, column, label in zip(axes.flat, NUMERIC, units, strict=False):
        sns.histplot(data=training, x=column, hue="target", bins=15, ax=axis, element="step")
        axis.set_xlabel(label)
    axes.flat[-1].axis("off")
    figure.suptitle("Cleveland training partition | distributions by recorded disease presence")
    figure.tight_layout()
    save(figure, "distributions.png")

    figure, axis = plt.subplots(figsize=(6, 4))
    sns.countplot(data=training, x="target", hue="target", palette=PALETTE, legend=False, ax=axis)
    axis.set(title="Training class balance", xlabel="Recorded disease presence", ylabel="Records")
    for container in axis.containers:
        axis.bar_label(container)
    save(figure, "class_balance.png")

    figure, axis = plt.subplots(figsize=(8, 6))
    sns.heatmap(
        training[[*NUMERIC, "target"]].corr(),
        annot=True,
        fmt=".2f",
        cmap="vlag",
        vmin=-1,
        vmax=1,
        center=0,
        ax=axis,
    )
    axis.set_title("Training Pearson correlations | numeric features only")
    save(figure, "correlations.png")

    figure, axis = plt.subplots(figsize=(8, 3.5))
    training.isna().sum().plot.bar(color=PALETTE[0], ax=axis)
    axis.set(title="Training missing values | imputation is fitted inside CV", ylabel="Records")
    save(figure, "missingness.png")

    figure, axis = plt.subplots(figsize=(7, 4))
    sns.countplot(data=training, x="cp", hue="target", ax=axis)
    axis.set(title="Chest-pain categories | training partition", xlabel="Original UCI cp code")
    save(figure, "chest_pain.png")
    write_json(
        Path("reports/eda_summary.json"),
        {
            "population": "training only",
            "rows": len(training),
            "missing": training.isna().sum().to_dict(),
            "class_counts": training.target.value_counts().sort_index().to_dict(),
        },
    )


if __name__ == "__main__":
    run()
