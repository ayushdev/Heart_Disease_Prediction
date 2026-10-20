"""Render an exactly ten-page report; final mode requires genuine completion evidence."""

import argparse
import json
import urllib.parse
from pathlib import Path
from xml.sax.saxutils import escape

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pypdf import PdfReader
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    Image,
    KeepInFrame,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def read_json(path: str) -> dict | list:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def missing_evidence(evidence: dict) -> list[str]:
    missing = []
    if not evidence.get("author", "").strip():
        missing.append("author name and student ID")
    repository = urllib.parse.urlsplit(evidence["repository_url"])
    if (
        repository.scheme != "https"
        or repository.hostname != "github.com"
        or len(repository.path.strip("/").split("/")) != 2
    ):
        missing.append("actual GitHub repository URL")
    if not (
        (evidence["video_path"] and Path(evidence["video_path"]).is_file())
        or evidence["video_url"].startswith("https://")
    ):
        missing.append("actual demo recording or accessible video URL")
    for capture in evidence["captures"]:
        if not Path(capture["path"]).is_file():
            missing.append(capture["path"])
    for name, path in evidence["checks"].items():
        if not Path(path).is_file():
            missing.append(f"{name} execution evidence")
        else:
            result = read_json(path)
            if name == "release":
                if not result.get("ci_url") or "@sha256:" not in result.get("image", ""):
                    missing.append("verified release digest and CI URL")
            elif result.get("status") != "passed":
                missing.append(f"passing {name} evidence")
    return missing


def architecture() -> None:
    target = Path("reports/figures/architecture.png")
    target.parent.mkdir(parents=True, exist_ok=True)
    figure, axis = plt.subplots(figsize=(11, 4.8))
    axis.set(xlim=(0, 11), ylim=(0, 5))
    axis.axis("off")
    nodes = {
        "UCI + hashes": (1.2, 4),
        "Clean + split": (4, 4),
        "CV + MLflow": (7, 4),
        "Tested model": (9.6, 4),
        "CI + Docker": (9.6, 2.3),
        "GHCR digest": (7, 2.3),
        "Kubernetes API": (4, 2.3),
        "JSON client": (1.2, 2.3),
        "Pod metrics": (4, 0.6),
        "Prometheus": (7, 0.6),
        "Grafana": (9.6, 0.6),
    }
    for label, (horizontal, vertical) in nodes.items():
        axis.text(
            horizontal,
            vertical,
            label,
            ha="center",
            va="center",
            fontsize=10,
            bbox={"boxstyle": "round,pad=0.45", "facecolor": "#edf5f5", "edgecolor": "#167d8d"},
        )
    edges = [
        ("UCI + hashes", "Clean + split"),
        ("Clean + split", "CV + MLflow"),
        ("CV + MLflow", "Tested model"),
        ("Tested model", "CI + Docker"),
        ("CI + Docker", "GHCR digest"),
        ("GHCR digest", "Kubernetes API"),
        ("JSON client", "Kubernetes API"),
        ("Kubernetes API", "Pod metrics"),
        ("Pod metrics", "Prometheus"),
        ("Prometheus", "Grafana"),
    ]
    for start, end in edges:
        axis.annotate(
            "",
            xy=nodes[end],
            xytext=nodes[start],
            arrowprops={"arrowstyle": "->", "color": "#546269", "shrinkA": 48, "shrinkB": 48},
        )
    figure.tight_layout()
    figure.savefig(target, dpi=170, bbox_inches="tight", facecolor="white")
    plt.close(figure)


def build(final: bool = False) -> Path:
    evidence = read_json("screenshots/evidence.json")
    missing = missing_evidence(evidence)
    if final and missing:
        raise ValueError("Final report blocked by missing evidence: " + "; ".join(missing))
    results = read_json("reports/results.json")
    pages = read_json("docs/report_content.json")
    if len(pages) != 10:
        raise ValueError("Report narrative must contain exactly ten pages")
    architecture()
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="ReportBody",
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            spaceAfter=10,
            textColor=colors.HexColor("#273237"),
        )
    )
    styles.add(
        ParagraphStyle(
            name="ReportTitle",
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=26,
            spaceAfter=9,
            textColor=colors.HexColor("#146b78"),
        )
    )
    styles.add(
        ParagraphStyle(
            name="ReportCaption",
            fontSize=8,
            leading=11,
            spaceAfter=7,
            textColor=colors.HexColor("#526269"),
        )
    )
    body = styles["ReportBody"]
    output = Path(
        "MLOps_Assignment_2025AE05258.pdf" if final else "assignment_report_DRAFT.pdf"
    )
    document = SimpleDocTemplate(
        str(output),
        pagesize=A4,
        leftMargin=42,
        rightMargin=42,
        topMargin=56,
        bottomMargin=42,
        title="Heart Risk MLOps Assignment",
        author=evidence["author"],
    )
    width = A4[0] - 84

    def paragraph(text):
        return Paragraph(escape(str(text)), body)

    def table(rows):
        grid = Table(
            [[paragraph(cell) for cell in row] for row in rows],
            colWidths=[width / len(rows[0])] * len(rows[0]),
            hAlign="LEFT",
        )
        grid.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e1eff0")),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#c5d4d7")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 7),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        return grid

    story = []
    for index, page in enumerate(pages):
        content = [
            Paragraph(escape(page["title"]), styles["ReportTitle"]),
            Paragraph(escape(page["subtitle"]), styles["ReportCaption"]),
            Spacer(1, 9),
        ]
        if index == 0:
            content.append(paragraph("Author: " + (evidence["author"].strip() or "PENDING")))
            repository_href = escape(evidence["repository_url"], {'"': "&quot;"})
            repository_link = (
                f'Repository: <link href="{repository_href}" color="#146b78">'
                "<u>GitHub Heart Disease Prediction</u></link>"
            )
            content.append(
                Paragraph(repository_link, body)
            )
            video_target = evidence["video_url"] or evidence["video_path"]
            video_href = escape(video_target.replace("\\", "/"), {'"': "&quot;"})
            video_label = "Open MLOps_Recording.mp4" if evidence["video_path"] else "Open video"
            video_link = (
                f'Video: <link href="{video_href}" color="#146b78">'
                f"<u>{escape(video_label)}</u></link> "
                "(keep the video beside this PDF for offline access)"
            )
            content.append(
                Paragraph(video_link, body)
            )
        content.extend(paragraph(text) for text in page["paragraphs"])
        if page.get("table") == "headline":
            chosen = results["models"][results["champion"]]
            content.append(
                table(
                    [
                        ["Selected model", "CV ROC-AUC", "Holdout recall"],
                        [
                            results["champion"],
                            f"{chosen['cv']['roc_auc']['mean']:.3f}",
                            f"{chosen['holdout']['recall']:.3f}",
                        ],
                    ]
                )
            )
        elif page.get("table") == "models":
            rows = [["Metric", "Logistic Regression", "Random Forest"]]
            for metric in ("accuracy", "precision", "recall", "f1", "roc_auc"):
                rows.append(
                    ["Holdout " + metric]
                    + [f"{result['holdout'][metric]:.3f}" for result in results["models"].values()]
                )
            rows.append(
                ["CV ROC-AUC mean (SD)"]
                + [
                    f"{result['cv']['roc_auc']['mean']:.3f} ({result['cv']['roc_auc']['std']:.3f})"
                    for result in results["models"].values()
                ]
            )
            content.append(table(rows))
        elif page.get("table") == "evidence":
            content.append(paragraph("Repository: " + (evidence["repository_url"] or "PENDING")))
            content.append(
                paragraph(
                    "Video: " + (evidence["video_url"] or evidence["video_path"] or "PENDING")
                )
            )
            content.append(
                paragraph(
                    "Local API: http://localhost:8000/docs; deployed access: "
                    "http://localhost:8080/docs after successful Kubernetes verification."
                )
            )
            content.append(
                Paragraph(
                    escape("Outstanding: " + ("; ".join(missing) or "None")),
                    styles["ReportCaption"],
                )
            )
        if page.get("figure"):
            path = Path(page["figure"])
            if path.exists():
                image_width, image_height = ImageReader(str(path)).getSize()
                scale = min(width / image_width, 225 / image_height)
                content.extend(
                    [
                        Spacer(1, 6),
                        Image(str(path), width=image_width * scale, height=image_height * scale),
                    ]
                )
            else:
                content.append(paragraph("EVIDENCE PENDING: " + page["figure"]))
            content.append(Paragraph(escape(page["caption"]), styles["ReportCaption"]))
        story.append(KeepInFrame(width, A4[1] - 110, content, mode="error"))
        if index != 9:
            story.append(PageBreak())

    def decorate(canvas, doc):
        canvas.setFillColor(colors.HexColor("#146b78"))
        canvas.rect(0, A4[1] - 31, A4[0], 31, fill=1, stroke=0)
        canvas.setFillColor(colors.white)
        canvas.setFont("Helvetica-Bold", 9)
        label = "AIMLCZG523 | HEART RISK MLOPS"
        if not final:
            label += " | DRAFT: EXECUTION EVIDENCE INCOMPLETE"
        canvas.drawString(42, A4[1] - 20, label)
        canvas.setFillColor(colors.HexColor("#526269"))
        canvas.setFont("Helvetica", 8)
        canvas.drawString(42, 23, "Educational classification study | Not for clinical diagnosis")
        canvas.drawRightString(A4[0] - 42, 23, f"{doc.page} / 10")

    document.build(story, onFirstPage=decorate, onLaterPages=decorate)
    if len(PdfReader(output).pages) != 10:
        raise ValueError("Generated PDF is not exactly ten pages")
    print(f"Created {output} (10 pages). Outstanding evidence items: {len(missing)}")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--final", action="store_true")
    build(parser.parse_args().final)
