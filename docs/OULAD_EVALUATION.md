# OULAD Random Forest evaluation

## Experiment

- Dataset: 30,059 prepared OULAD student/module/presentation records
- Observation window: first 60 presentation days
- Target: `successful` = Pass/Distinction; `at_risk` = Fail/Withdrawn
- Split: one reproducible 80/20 `GroupShuffleSplit`, grouped by anonymized `id_student`
- Training rows: 24,038
- Test rows: 6,021
- Classifier: `RandomForestClassifier(n_estimators=300, random_state=42, min_samples_leaf=3, class_weight="balanced", n_jobs=-1)`

Grouping by student is important: when a student appears in multiple module presentations, all of that student's rows remain on one side of the split. This prevents the model from being evaluated on a student it already encountered during training.

## Held-out results

| Metric | Result |
|---|---:|
| Accuracy | 0.7861 |
| Precision (successful class) | 0.7289 |
| Recall (successful class) | 0.8480 |
| F1 (successful class) | 0.7840 |
| ROC-AUC | 0.8647 |

Confusion matrix, with rows = actual `[at_risk, successful]` and columns = predicted `[at_risk, successful]`:

```text
[[2396, 869],
 [ 419, 2337]]
```

## Feature importance

| Feature | Importance |
|---|---:|
| Mean score | 0.3960 |
| Completion rate | 0.2246 |
| Mean submission delay | 0.1451 |
| On-time rate | 0.1109 |
| Assessments submitted | 0.0930 |
| Previous attempts | 0.0163 |
| Assessments due | 0.0141 |

Random Forest importance describes how the fitted model used these fields; it does not establish that any feature causes success or failure.

## Limitations

This is a single held-out split from historical Open University data. The probability values were not calibrated against Miva Open University students, and the model has not undergone external validation, fairness analysis or prospective testing. A prediction should be used to offer planning support, never as an automatic academic decision. The training command writes complete machine-readable metrics beside the generated model as `oulad_random_forest.metrics.json`.
