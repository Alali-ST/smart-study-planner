from datetime import datetime, timedelta, time, timezone
from pathlib import Path
import json

import joblib
import numpy as np
from flask import current_app
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import GroupShuffleSplit

from .extensions import db
from .models import Assignment, Course, Notification, Prediction, Recommendation, StudySchedule

FEATURES = [
    "previous_attempts", "assessments_due", "assessments_submitted",
    "completion_rate", "mean_score", "on_time_rate", "mean_submission_delay",
]
MODEL_VERSION = "oulad-rf-classifier-v1-day60"


def train_model(records, model_path=None):
    """Train an OULAD early-warning classifier with a student-grouped split."""
    if len(records) < 10:
        raise ValueError("At least 10 prepared OULAD rows are required")
    X = np.asarray([[float(row[name]) for name in FEATURES] for row in records], dtype=float)
    y = np.asarray([1 if row["target"] == "successful" else 0 for row in records], dtype=int)
    groups = np.asarray([row.get("id_student", str(index)) for index, row in enumerate(records)])
    split = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
    train_indices, test_indices = next(split.split(X, y, groups))
    X_train, X_test = X[train_indices], X[test_indices]
    y_train, y_test = y[train_indices], y[test_indices]
    model = RandomForestClassifier(
        n_estimators=300, random_state=42, min_samples_leaf=3,
        class_weight="balanced", n_jobs=-1,
    )
    model.fit(X_train, y_train)
    predicted = model.predict(X_test)
    success_probability = model.predict_proba(X_test)[:, list(model.classes_).index(1)]
    metrics = {
        "accuracy": float(accuracy_score(y_test, predicted)),
        "precision": float(precision_score(y_test, predicted, zero_division=0)),
        "recall": float(recall_score(y_test, predicted, zero_division=0)),
        "f1": float(f1_score(y_test, predicted, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_test, success_probability)) if len(set(y_test)) == 2 else None,
        "confusion_matrix": confusion_matrix(y_test, predicted, labels=[0, 1]).tolist(),
        "train_rows": int(len(train_indices)),
        "test_rows": int(len(test_indices)),
        "feature_importance": {name: float(value) for name, value in zip(FEATURES, model.feature_importances_)},
    }
    path = Path(model_path or current_app.config["MODEL_PATH"])
    path.parent.mkdir(parents=True, exist_ok=True)
    bundle = {
        "model": model, "features": FEATURES, "metrics": metrics,
        "model_version": MODEL_VERSION, "dataset": "OULAD",
        "observation_window_days": 60,
        "target": "successful (Pass/Distinction) versus at_risk (Fail/Withdrawn)",
    }
    joblib.dump(bundle, path)
    path.with_suffix(".metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    return metrics


def load_model():
    path = Path(current_app.config["MODEL_PATH"])
    if not path.exists():
        raise ValueError("The OULAD model is not prepared. Run the StudySmart launcher again.")
    bundle = joblib.load(path)
    if bundle.get("features") != FEATURES or bundle.get("model_version") != MODEL_VERSION:
        raise ValueError("The installed model is outdated. Run the StudySmart launcher to retrain it.")
    return bundle


def prediction_features(payload):
    """Validate the student's first-60-day academic activity snapshot."""
    required = (
        "previous_attempts", "assessments_due", "assessments_submitted",
        "mean_score", "on_time_submissions", "mean_submission_delay",
    )
    missing = [name for name in required if payload.get(name) in (None, "")]
    if missing:
        raise ValueError("Missing prediction fields: " + ", ".join(missing))
    try:
        previous_attempts = int(payload["previous_attempts"])
        due = int(payload["assessments_due"])
        submitted = int(payload["assessments_submitted"])
        mean_score = float(payload["mean_score"])
        on_time = int(payload["on_time_submissions"])
        delay = float(payload["mean_submission_delay"])
    except (TypeError, ValueError) as error:
        raise ValueError("Prediction inputs must be numeric") from error
    if previous_attempts < 0:
        raise ValueError("Previous attempts cannot be negative")
    if due < 1:
        raise ValueError("At least one assessment must have been due")
    if not 0 <= submitted <= due:
        raise ValueError("Submitted assessments must be between zero and assessments due")
    if not 0 <= on_time <= submitted:
        raise ValueError("On-time submissions cannot exceed submitted assessments")
    if not 0 <= mean_score <= 100:
        raise ValueError("Average assessment score must be between 0 and 100")
    return {
        "previous_attempts": previous_attempts,
        "assessments_due": due,
        "assessments_submitted": submitted,
        "completion_rate": submitted / due,
        "mean_score": mean_score if submitted else 0.0,
        "on_time_rate": on_time / submitted if submitted else 0.0,
        "mean_submission_delay": delay if submitted else 0.0,
    }


def predict_and_recommend(student, course, payload):
    """Predict the selected course's outcome from that course's early activity."""
    bundle = load_model()
    features = prediction_features(payload)
    row = np.asarray([[features[name] for name in FEATURES]], dtype=float)
    probabilities = bundle["model"].predict_proba(row)[0]
    success_probability = float(dict(zip(bundle["model"].classes_, probabilities)).get(1, 0.0))
    outcome = "successful" if success_probability >= 0.5 else "at_risk"
    confidence = max(success_probability, 1 - success_probability) * 100
    risk = "high" if success_probability < 0.40 else "medium" if success_probability < 0.65 else "low"
    prediction = Prediction(
        student_id=student.id,
        course_id=course.id,
        predicted_grade=round(success_probability * 100, 2),
        predicted_outcome=outcome,
        success_probability=round(success_probability * 100, 2),
        confidence_score=round(confidence, 2),
        risk_level=risk,
        model_version=bundle["model_version"],
        observation_window_days=bundle["observation_window_days"],
        input_snapshot=json.dumps(features, sort_keys=True),
    )
    db.session.add(prediction)
    db.session.flush()
    suggestions = []
    if features["completion_rate"] < 0.75:
        suggestions.append("complete outstanding assessments")
    if features["mean_score"] < 50:
        suggestions.append("schedule focused review of weaker topics")
    if features["on_time_rate"] < 0.75:
        suggestions.append("start assignments earlier to improve on-time submission")
    if not suggestions:
        suggestions.append("maintain your current assessment and study routine")
    prefix = (
        f"For {course.course_code}, your first-60-day pattern is associated with elevated risk of not passing; "
        if outcome == "at_risk" else
        f"For {course.course_code}, your first-60-day pattern is associated with passing outcomes; "
    )
    recommendation = Recommendation(
        student_id=student.id, prediction_id=prediction.id,
        recommendation_type="oulad-early-warning",
        recommendation_text=prefix + ", ".join(suggestions) + ".",
        priority_level=risk,
    )
    db.session.add(recommendation)
    db.session.commit()
    return prediction, recommendation, features, bundle


def generate_schedule(student, days=7):
    """Create a spaced, priority-based plan without repeating one target every day."""
    days = min(max(int(days), 1), 31)
    now = datetime.now(timezone.utc)
    local_now = datetime.now().astimezone()
    start = time(18, 0) if student.study_preference != "morning" else time(7, 0)
    first_offset = 1 if local_now.time().replace(tzinfo=None) >= start else 0
    assignments = Assignment.query.filter_by(student_id=student.id, status="pending").all()
    courses = {course.id: course for course in Course.query.filter_by(student_id=student.id).all()}
    targets = []
    for assignment in assignments:
        course = courses.get(assignment.course_id)
        deadline = _aware(assignment.due_date).astimezone(local_now.tzinfo)
        days_until_due = (deadline.date() - local_now.date()).days
        remaining = max(1, days_until_due)
        priority = (assignment.weight or 10) / remaining + (course.difficulty if course else 3) + (course.credit_unit if course else 1)
        latest_offset = min(days - 1, days_until_due) if days_until_due >= first_offset else min(days - 1, first_offset + 2)
        available_days = max(0, latest_offset - first_offset + 1)
        weekly_quota = 2 * max(1, (available_days + 6) // 7)
        quota = min(available_days, weekly_quota + (1 if days_until_due <= 3 else 0))
        if quota:
            targets.append((priority, assignment, course, latest_offset, quota))
    for course in courses.values():
        if course.examination_date and _aware(course.examination_date) > now:
            exam = _aware(course.examination_date).astimezone(local_now.tzinfo)
            days_until_exam = (exam.date() - local_now.date()).days
            remaining = max(1, days_until_exam)
            latest_offset = min(days - 1, days_until_exam) if days_until_exam >= first_offset else min(days - 1, first_offset + 2)
            available_days = max(0, latest_offset - first_offset + 1)
            weekly_quota = 2 * max(1, (available_days + 6) // 7)
            quota = min(available_days, weekly_quota + (1 if days_until_exam <= 3 else 0))
            if quota:
                targets.append((course.difficulty + course.credit_unit + 10 / remaining, None, course, latest_offset, quota))
    targets.sort(key=lambda item: item[0], reverse=True)
    completed_items = StudySchedule.query.filter(
        StudySchedule.student_id == student.id,
        StudySchedule.study_date >= now.date(),
        StudySchedule.status == "completed",
    ).all()
    completed_dates = {item.study_date for item in completed_items}
    completed_counts = {}
    for item in completed_items:
        key = (item.assignment_id, item.course_id, item.topic)
        completed_counts[key] = completed_counts.get(key, 0) + 1
    StudySchedule.query.filter(
        StudySchedule.student_id == student.id,
        StudySchedule.study_date >= now.date(),
        StudySchedule.status == "pending",
    ).delete(synchronize_session=False)
    if not targets:
        db.session.commit()
        return []
    created, slot = [], max(30, int(student.available_study_hours * 60))
    occupied_dates = set(completed_dates)
    for _, assignment, course, latest_offset, quota in targets:
        topic = assignment.title if assignment else f"Review {course.course_code}"
        target_key = (assignment.id if assignment else None, course.id if course else None, topic)
        remaining_quota = max(0, quota - completed_counts.get(target_key, 0))
        for desired_offset in _spaced_offsets(first_offset, latest_offset, remaining_quota):
            available_offsets = sorted(
                range(first_offset, latest_offset + 1),
                key=lambda offset: (abs(offset - desired_offset), offset),
            )
            chosen_offset = next(
                (offset for offset in available_offsets if now.date() + timedelta(days=offset) not in occupied_dates),
                None,
            )
            if chosen_offset is None:
                continue
            study_date = now.date() + timedelta(days=chosen_offset)
            occupied_dates.add(study_date)
            end_dt = datetime.combine(study_date, start) + timedelta(minutes=slot)
            item = StudySchedule(
                student_id=student.id, course_id=course.id if course else None,
                assignment_id=assignment.id if assignment else None,
                study_date=study_date, start_time=start,
                end_time=end_dt.time(), duration=slot,
                topic=topic,
            )
            db.session.add(item)
            created.append(item)
    created.sort(key=lambda item: (item.study_date, item.start_time))
    db.session.commit()
    return created


def _aware(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def _spaced_offsets(first_offset, last_offset, count):
    """Return evenly spaced integer day offsets, including both ends when possible."""
    if count <= 0 or last_offset < first_offset:
        return []
    available = last_offset - first_offset + 1
    if count >= available:
        return list(range(first_offset, last_offset + 1))
    if count == 1:
        return [first_offset]
    return sorted({
        first_offset + round(index * (available - 1) / (count - 1))
        for index in range(count)
    })


def sync_study_session_notifications(student, reminder_days=1):
    """Keep only timely in-app reminders for pending sessions today or tomorrow."""
    today = datetime.now().astimezone().date()
    cutoff = today + timedelta(days=reminder_days)
    sessions = StudySchedule.query.filter(
        StudySchedule.student_id == student.id,
        StudySchedule.status == "pending",
        StudySchedule.study_date >= today,
        StudySchedule.study_date <= cutoff,
    ).order_by(StudySchedule.study_date, StudySchedule.start_time).all()
    desired = {
        f"Study session: {item.topic} on {item.study_date} at {item.start_time.strftime('%H:%M')}"
        for item in sessions
    }
    existing = Notification.query.filter_by(
        student_id=student.id, notification_type="study-session"
    ).order_by(Notification.date_sent.desc()).all()
    retained = set()
    changed = False
    for notification in existing:
        if notification.message not in desired or notification.message in retained:
            db.session.delete(notification)
            changed = True
        else:
            retained.add(notification.message)
    for message in sorted(desired - retained):
        db.session.add(Notification(
            student_id=student.id,
            message=message,
            notification_type="study-session",
        ))
        changed = True
    if changed:
        db.session.commit()
    return len(desired)


def sync_assignment_notifications(student):
    """Keep exactly one current in-app reminder for every pending assignment."""
    now = datetime.now(timezone.utc)
    local_timezone = datetime.now().astimezone().tzinfo
    courses = {course.id: course for course in Course.query.filter_by(student_id=student.id).all()}
    desired = {}
    assignments = Assignment.query.filter_by(student_id=student.id, status="pending").all()
    for assignment in assignments:
        due = _aware(assignment.due_date).astimezone(local_timezone)
        course_code = courses.get(assignment.course_id).course_code if assignment.course_id in courses else "Course"
        due_text = due.strftime("%d %b %Y at %H:%M")
        if due < now:
            message = f"{course_code}: {assignment.title} is overdue and not completed. It was due {due_text}."
        else:
            message = f"{course_code}: {assignment.title} is not completed yet. Due {due_text}."
        desired[f"assignment-{assignment.id}"] = message
    existing = Notification.query.filter(
        Notification.student_id == student.id,
        Notification.notification_type.like("assignment-%"),
    ).order_by(Notification.date_sent.desc()).all()
    retained = set()
    changed = False
    for notification in existing:
        expected_message = desired.get(notification.notification_type)
        if not expected_message or notification.notification_type in retained:
            db.session.delete(notification)
            changed = True
            continue
        retained.add(notification.notification_type)
        if notification.message != expected_message:
            notification.message = expected_message
            notification.status = "unread"
            notification.date_sent = now
            changed = True
    for notification_type, message in desired.items():
        if notification_type not in retained:
            db.session.add(Notification(
                student_id=student.id,
                message=message,
                notification_type=notification_type,
            ))
            changed = True
    if changed:
        db.session.commit()
    return len(desired)
