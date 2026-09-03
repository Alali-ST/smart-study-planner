"""Download and transform OULAD into a leakage-safe early-warning dataset."""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
import tempfile
import urllib.request
import zipfile
from collections import defaultdict
from pathlib import Path

OULAD_URL = (
    "https://archive.ics.uci.edu/static/public/349/"
    "open%2Buniversity%2Blearning%2Banalytics%2Bdataset.zip"
)
OULAD_SHA256 = "f2ed1902616c1fe8d2824d872c0b7d2d72be435bf0124d077044fe4be2c6d3e4"
REQUIRED_FILES = ("studentInfo.csv", "assessments.csv", "studentAssessment.csv")
DATASET_CITATION = (
    "Kuzilek, J., Hlosta, M., & Zdrahal, Z. (2017). Open University "
    "Learning Analytics Dataset. Scientific Data, 4, 170171. "
    "https://doi.org/10.1038/sdata.2017.171"
)


def download_oulad(output_dir: str | Path, url: str = OULAD_URL) -> dict:
    """Download the official UCI mirror and extract only the tables we use."""
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    if all((destination / name).exists() for name in REQUIRED_FILES):
        return {"status": "already-present", "files": list(REQUIRED_FILES)}

    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as temporary:
        archive_path = Path(temporary.name)
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "StudySmart-OULAD/1.0"})
        digest = hashlib.sha256()
        with urllib.request.urlopen(request, timeout=90) as response, archive_path.open("wb") as stream:
            while chunk := response.read(1024 * 1024):
                stream.write(chunk)
                digest.update(chunk)
        checksum = digest.hexdigest()
        if checksum != OULAD_SHA256:
            raise ValueError(f"OULAD checksum mismatch: expected {OULAD_SHA256}, got {checksum}")
        with zipfile.ZipFile(archive_path) as archive:
            names = {Path(name).name: name for name in archive.namelist()}
            missing = sorted(set(REQUIRED_FILES) - set(names))
            if missing:
                raise ValueError(f"OULAD archive is missing: {', '.join(missing)}")
            for filename in REQUIRED_FILES:
                with archive.open(names[filename]) as source, (destination / filename).open("wb") as target:
                    shutil.copyfileobj(source, target)
    finally:
        archive_path.unlink(missing_ok=True)

    metadata = {
        "source": url,
        "sha256": OULAD_SHA256,
        "license": "CC BY 4.0",
        "citation": DATASET_CITATION,
        "files": list(REQUIRED_FILES),
    }
    (destination / "SOURCE.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return {"status": "downloaded", **metadata}


def prepare_oulad(raw_dir: str | Path, output_csv: str | Path, cutoff_day: int = 60) -> dict:
    """Create one early-warning row per student/module/presentation."""
    if cutoff_day < 1:
        raise ValueError("cutoff_day must be positive")
    raw = Path(raw_dir)
    for filename in REQUIRED_FILES:
        if not (raw / filename).exists():
            raise FileNotFoundError(f"Missing OULAD table: {raw / filename}")

    early_assessments: dict[str, tuple[str, str, int]] = {}
    due_by_presentation: dict[tuple[str, str], set[str]] = defaultdict(set)
    with (raw / "assessments.csv").open(newline="", encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            if row["assessment_type"] == "Exam" or row["date"] in {"", "?"}:
                continue
            due_day = int(float(row["date"]))
            if due_day <= cutoff_day:
                key = (row["code_module"], row["code_presentation"])
                assessment_id = row["id_assessment"]
                early_assessments[assessment_id] = (*key, due_day)
                due_by_presentation[key].add(assessment_id)

    submissions: dict[tuple[str, str, str], list[tuple[float, int]]] = defaultdict(list)
    with (raw / "studentAssessment.csv").open(newline="", encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            assessment = early_assessments.get(row["id_assessment"])
            if assessment is None or row["date_submitted"] in {"", "?"} or row["score"] in {"", "?"}:
                continue
            module, presentation, due_day = assessment
            submitted_day = int(float(row["date_submitted"]))
            if submitted_day <= cutoff_day:
                submissions[(module, presentation, row["id_student"])].append(
                    (float(row["score"]), submitted_day - due_day)
                )

    output = Path(output_csv)
    output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "id_student", "code_module", "code_presentation", "previous_attempts",
        "assessments_due", "assessments_submitted", "completion_rate",
        "mean_score", "on_time_rate", "mean_submission_delay", "target",
    ]
    counts = {"successful": 0, "at_risk": 0, "excluded_no_early_assessment": 0}
    with (raw / "studentInfo.csv").open(newline="", encoding="utf-8-sig") as source, output.open(
        "w", newline="", encoding="utf-8"
    ) as target:
        writer = csv.DictWriter(target, fieldnames=fieldnames)
        writer.writeheader()
        for row in csv.DictReader(source):
            presentation_key = (row["code_module"], row["code_presentation"])
            due_count = len(due_by_presentation.get(presentation_key, ()))
            if due_count == 0:
                counts["excluded_no_early_assessment"] += 1
                continue
            observed = submissions.get((*presentation_key, row["id_student"]), [])
            submitted_count = len(observed)
            scores = [score for score, _ in observed]
            delays = [delay for _, delay in observed]
            outcome = "successful" if row["final_result"] in {"Pass", "Distinction"} else "at_risk"
            counts[outcome] += 1
            writer.writerow({
                "id_student": row["id_student"],
                "code_module": row["code_module"],
                "code_presentation": row["code_presentation"],
                "previous_attempts": int(row["num_of_prev_attempts"] or 0),
                "assessments_due": due_count,
                "assessments_submitted": submitted_count,
                "completion_rate": round(submitted_count / due_count, 6),
                "mean_score": round(sum(scores) / submitted_count, 6) if scores else 0.0,
                "on_time_rate": round(sum(delay <= 0 for delay in delays) / submitted_count, 6) if delays else 0.0,
                "mean_submission_delay": round(sum(delays) / submitted_count, 6) if delays else 0.0,
                "target": outcome,
            })

    metadata = {
        "dataset": "OULAD",
        "cutoff_day": cutoff_day,
        "rows": counts["successful"] + counts["at_risk"],
        "class_counts": {"successful": counts["successful"], "at_risk": counts["at_risk"]},
        "excluded_no_early_assessment": counts["excluded_no_early_assessment"],
        "features_observed_through_day": cutoff_day,
        "target_source": "studentInfo.final_result",
        "citation": DATASET_CITATION,
    }
    output.with_suffix(".metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata
