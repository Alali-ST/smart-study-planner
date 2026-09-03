from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash
from .extensions import db


def now():
    return datetime.now(timezone.utc)


class Student(db.Model):
    __tablename__ = "student"
    id = db.Column("StudentID", db.Integer, primary_key=True)
    full_name = db.Column("FullName", db.String(120), nullable=False)
    email = db.Column("Email", db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column("Password", db.String(255), nullable=False)
    level = db.Column("Level", db.String(40), nullable=False)
    programme = db.Column("Programme", db.String(120), nullable=False)
    study_preference = db.Column("StudyPreference", db.String(80), default="balanced")
    available_study_hours = db.Column(db.Float, default=2.0)
    previous_grade = db.Column(db.Float, default=50.0)
    attendance_rate = db.Column(db.Float, nullable=True)
    study_habit_score = db.Column(db.Float, default=5.0)
    date_created = db.Column("DateCreated", db.DateTime(timezone=True), default=now)
    courses = db.relationship("Course", cascade="all, delete-orphan", backref="student")

    def set_password(self, password): self.password_hash = generate_password_hash(password)
    def check_password(self, password): return check_password_hash(self.password_hash, password)


class Course(db.Model):
    __tablename__ = "course"
    id = db.Column("CourseID", db.Integer, primary_key=True)
    student_id = db.Column("StudentID", db.Integer, db.ForeignKey("student.StudentID", ondelete="CASCADE"), nullable=False)
    course_code = db.Column("CourseCode", db.String(20), nullable=False)
    course_title = db.Column("CourseTitle", db.String(160), nullable=False)
    credit_unit = db.Column("CreditUnit", db.Integer, nullable=False)
    semester = db.Column("Semester", db.String(30), nullable=False)
    description = db.Column(db.Text)
    difficulty = db.Column(db.Integer, default=3)
    examination_date = db.Column(db.DateTime(timezone=True), nullable=True)
    __table_args__ = (db.UniqueConstraint("StudentID", "CourseCode", name="uq_student_course"),)


class Assignment(db.Model):
    __tablename__ = "assignment"
    id = db.Column("AssignmentID", db.Integer, primary_key=True)
    course_id = db.Column("CourseID", db.Integer, db.ForeignKey("course.CourseID", ondelete="CASCADE"), nullable=False)
    student_id = db.Column("StudentID", db.Integer, db.ForeignKey("student.StudentID", ondelete="CASCADE"), nullable=False)
    title = db.Column("Title", db.String(160), nullable=False)
    description = db.Column("Description", db.Text)
    due_date = db.Column("DueDate", db.DateTime(timezone=True), nullable=False)
    weight = db.Column("Weight", db.Float, default=10.0)
    status = db.Column("Status", db.String(20), default="pending")
    completed_at = db.Column("CompletedAt", db.DateTime(timezone=True), nullable=True)
    course = db.relationship("Course", backref=db.backref("assignments", cascade="all, delete-orphan"))


class StudySchedule(db.Model):
    __tablename__ = "study_schedule"
    id = db.Column("ScheduleID", db.Integer, primary_key=True)
    student_id = db.Column("StudentID", db.Integer, db.ForeignKey("student.StudentID", ondelete="CASCADE"), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey("course.CourseID", ondelete="CASCADE"), nullable=True)
    assignment_id = db.Column(db.Integer, db.ForeignKey("assignment.AssignmentID", ondelete="SET NULL"), nullable=True)
    study_date = db.Column("StudyDate", db.Date, nullable=False)
    start_time = db.Column("StartTime", db.Time, nullable=False)
    end_time = db.Column("EndTime", db.Time, nullable=False)
    duration = db.Column("Duration", db.Integer, nullable=False)
    topic = db.Column("Topic", db.String(200), nullable=False)
    status = db.Column("Status", db.String(20), default="pending")


class FocusSession(db.Model):
    """A completed Pomodoro/focus interval recorded by the student."""
    __tablename__ = "focus_session"
    id = db.Column("FocusSessionID", db.Integer, primary_key=True)
    student_id = db.Column("StudentID", db.Integer, db.ForeignKey("student.StudentID", ondelete="CASCADE"), nullable=False)
    course_id = db.Column("CourseID", db.Integer, db.ForeignKey("course.CourseID", ondelete="SET NULL"), nullable=True)
    assignment_id = db.Column("AssignmentID", db.Integer, db.ForeignKey("assignment.AssignmentID", ondelete="SET NULL"), nullable=True)
    schedule_id = db.Column("ScheduleID", db.Integer, db.ForeignKey("study_schedule.ScheduleID", ondelete="SET NULL"), nullable=True)
    duration_minutes = db.Column("DurationMinutes", db.Integer, nullable=False)
    started_at = db.Column("StartedAt", db.DateTime(timezone=True), nullable=False)
    completed_at = db.Column("CompletedAt", db.DateTime(timezone=True), default=now, nullable=False)
    mode = db.Column("Mode", db.String(30), default="pomodoro")
    status = db.Column("Status", db.String(20), default="completed")


class Prediction(db.Model):
    __tablename__ = "prediction"
    id = db.Column("PredictionID", db.Integer, primary_key=True)
    student_id = db.Column("StudentID", db.Integer, db.ForeignKey("student.StudentID", ondelete="CASCADE"), nullable=False)
    # Nullable only so existing general predictions can be retained during the
    # local database upgrade. Every new prediction is course-specific.
    course_id = db.Column("CourseID", db.Integer, db.ForeignKey("course.CourseID", ondelete="SET NULL"), nullable=True)
    course = db.relationship("Course")
    predicted_grade = db.Column("PredictedGrade", db.Float, nullable=False)
    predicted_outcome = db.Column("PredictedOutcome", db.String(30), nullable=True)
    success_probability = db.Column("SuccessProbability", db.Float, nullable=True)
    confidence_score = db.Column("ConfidenceScore", db.Float, nullable=False)
    risk_level = db.Column(db.String(20), nullable=False)
    model_version = db.Column("ModelVersion", db.String(80), nullable=True)
    observation_window_days = db.Column("ObservationWindowDays", db.Integer, default=60)
    input_snapshot = db.Column("InputSnapshot", db.Text, nullable=True)
    prediction_date = db.Column("PredictionDate", db.DateTime(timezone=True), default=now)


class Recommendation(db.Model):
    __tablename__ = "recommendation"
    id = db.Column("RecommendationID", db.Integer, primary_key=True)
    student_id = db.Column("StudentID", db.Integer, db.ForeignKey("student.StudentID", ondelete="CASCADE"), nullable=False)
    prediction_id = db.Column("PredictionID", db.Integer, db.ForeignKey("prediction.PredictionID", ondelete="CASCADE"), nullable=False)
    recommendation_type = db.Column(db.String(40), default="study-priority")
    recommendation_text = db.Column("RecommendationText", db.Text, nullable=False)
    priority_level = db.Column("PriorityLevel", db.String(20), nullable=False)


class Notification(db.Model):
    __tablename__ = "notification"
    id = db.Column("NotificationID", db.Integer, primary_key=True)
    student_id = db.Column("StudentID", db.Integer, db.ForeignKey("student.StudentID", ondelete="CASCADE"), nullable=False)
    message = db.Column("Message", db.String(255), nullable=False)
    notification_type = db.Column("NotificationType", db.String(30), nullable=False)
    status = db.Column("Status", db.String(20), default="unread")
    date_sent = db.Column("DateSent", db.DateTime(timezone=True), default=now)


class Administrator(db.Model):
    __tablename__ = "administrator"
    id = db.Column("AdminID", db.Integer, primary_key=True)
    full_name = db.Column("FullName", db.String(120), nullable=False)
    username = db.Column("Username", db.String(80), unique=True, nullable=False)
    password_hash = db.Column("Password", db.String(255), nullable=False)
    role = db.Column("Role", db.String(30), default="administrator")
    def set_password(self, password): self.password_hash = generate_password_hash(password)
    def check_password(self, password): return check_password_hash(self.password_hash, password)
