# OULAD training data

StudySmart uses the Open University Learning Analytics Dataset (OULAD), an anonymized open educational dataset released under CC BY 4.0.

## Source and attribution

- Kuzilek, J., Hlosta, M., & Zdrahal, Z. (2017). *Open University Learning Analytics Dataset*. Scientific Data, 4, 170171. <https://doi.org/10.1038/sdata.2017.171>
- Dataset record: <https://doi.org/10.6084/m9.figshare.5081998.v1>
- Official UCI mirror used by the reproducible downloader: <https://doi.org/10.24432/C5KK69>
- License: Creative Commons Attribution 4.0 (CC BY 4.0)

The downloader validates the official archive with SHA-256 `f2ed1902616c1fe8d2824d872c0b7d2d72be435bf0124d077044fe4be2c6d3e4` and extracts only `studentInfo.csv`, `assessments.csv` and `studentAssessment.csv`.

## Prepared table

`processed/training_data.csv` has one row per student/module/presentation and was generated with `cutoff_day=60`. It contains 30,059 records: 13,871 `successful` and 16,188 `at_risk`.

| Field | Meaning |
|---|---|
| `id_student` | Anonymized grouping key, used only to prevent a student's rows crossing train/test splits |
| `code_module`, `code_presentation` | OULAD context fields; retained for audit, not model features |
| `previous_attempts` | Previous attempts at the module |
| `assessments_due` | Non-exam assessments due by day 60 |
| `assessments_submitted` | Those assessments submitted by day 60 |
| `completion_rate` | Submitted divided by due |
| `mean_score` | Mean observed assessment score, or zero if none submitted |
| `on_time_rate` | Fraction submitted on or before the due date |
| `mean_submission_delay` | Mean submitted-day minus due-day; negative is early |
| `target` | `successful` for Pass/Distinction; `at_risk` for Fail/Withdrawn |

The model never uses `id_student`, module code or presentation code as predictive features. Exams are excluded because their outcomes are unavailable during an early-warning window. Submissions made after day 60 are also excluded to prevent future information leaking into training.

## Reproduction

From `backend`:

```powershell
flask --app run.py download-oulad
flask --app run.py prepare-oulad --cutoff-day 60
flask --app run.py train-model --dataset data/oulad/processed/training_data.csv
```

Raw source tables are intentionally excluded from the packaged project because they can be downloaded and verified reproducibly. The derived table is included so the one-click launcher works offline after Python dependencies are installed.

## Interpretation limits

This model detects patterns associated with the historical OULAD outcomes. It does not prove causation, predict an exact grade, or establish performance for Miva Open University students. A local deployment should be evaluated with appropriately consented institutional data before its outputs inform consequential decisions. Results should support students and advisers, not penalize or automatically rank students.
