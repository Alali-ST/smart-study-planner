import csv

from app.ml.oulad import prepare_oulad


def write_csv(path, fieldnames, rows):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_prepare_oulad_respects_day_60_observation_window(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    write_csv(
        raw / "assessments.csv",
        ["code_module", "code_presentation", "id_assessment", "assessment_type", "date"],
        [{"code_module": "AAA", "code_presentation": "2014J", "id_assessment": "1", "assessment_type": "TMA", "date": "30"}],
    )
    write_csv(
        raw / "studentAssessment.csv",
        ["id_assessment", "id_student", "date_submitted", "score"],
        [
            {"id_assessment": "1", "id_student": "10", "date_submitted": "28", "score": "80"},
            {"id_assessment": "1", "id_student": "20", "date_submitted": "70", "score": "90"},
        ],
    )
    write_csv(
        raw / "studentInfo.csv",
        ["code_module", "code_presentation", "id_student", "num_of_prev_attempts", "final_result"],
        [
            {"code_module": "AAA", "code_presentation": "2014J", "id_student": "10", "num_of_prev_attempts": "0", "final_result": "Pass"},
            {"code_module": "AAA", "code_presentation": "2014J", "id_student": "20", "num_of_prev_attempts": "1", "final_result": "Fail"},
        ],
    )

    output = tmp_path / "training.csv"
    metadata = prepare_oulad(raw, output, cutoff_day=60)
    with output.open(newline="", encoding="utf-8") as stream:
        records = list(csv.DictReader(stream))

    assert metadata["rows"] == 2
    assert records[0]["assessments_submitted"] == "1"
    assert records[0]["mean_submission_delay"] == "-2.0"
    assert records[0]["target"] == "successful"
    assert records[1]["assessments_submitted"] == "0"
    assert records[1]["mean_score"] == "0.0"
    assert records[1]["target"] == "at_risk"
