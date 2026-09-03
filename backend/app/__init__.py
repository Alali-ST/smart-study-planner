import os
import csv
import click
from datetime import timedelta
from flask import Flask, jsonify, request
from flask_cors import CORS
from sqlalchemy import inspect, text
from .extensions import db, jwt, migrate


def create_app(test_config=None):
    database_url = os.getenv("DATABASE_URL") or "sqlite:///smart_study_planner.db"
    if database_url.startswith("mysql://"):
        database_url = "mysql+pymysql://" + database_url[len("mysql://"):]
    instance_path = os.getenv("STUDYSMART_INSTANCE_PATH") or (
        "/tmp/studysmart-instance" if os.getenv("VERCEL") else None
    )
    app = Flask(
        __name__, static_folder="../../web", static_url_path="",
        instance_path=instance_path,
    )
    app.config.from_mapping(
        APP_VERSION="2026.09.03.3",
        SECRET_KEY=os.getenv("SECRET_KEY") or "development-only",
        JWT_SECRET_KEY=os.getenv("JWT_SECRET_KEY") or "development-jwt-only",
        JWT_ACCESS_TOKEN_EXPIRES=timedelta(hours=int(os.getenv("SESSION_HOURS") or "8")),
        SQLALCHEMY_DATABASE_URI=database_url,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        MODEL_PATH=os.getenv("MODEL_PATH", "instance/oulad_random_forest.joblib"),
    )
    if test_config:
        app.config.update(test_config)
    db.init_app(app)
    jwt.init_app(app)
    migrate.init_app(app, db)
    CORS(app, resources={r"/api/*": {"origins": (os.getenv("CORS_ORIGINS") or "*").split(",")}})

    from .api import api
    app.register_blueprint(api, url_prefix="/api/v1")

    @app.after_request
    def prevent_stale_client(response):
        """Keep an open local browser tab from mixing old UI code with a new API."""
        response.headers["X-StudySmart-Version"] = app.config["APP_VERSION"]
        if request.path == "/" or request.path.endswith((".js", ".css")):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

    @app.get("/")
    def web_app():
        return app.send_static_file("index.html")

    @app.errorhandler(404)
    def not_found(_):
        return jsonify(error="Resource not found"), 404

    @app.errorhandler(422)
    def invalid(_):
        return jsonify(error="Invalid request data"), 422

    @app.cli.command("init-db")
    def init_db():
        """Create the Chapter 3 tables and user-requested focus extension."""
        db.create_all()
        _upgrade_prediction_table()
        click.echo("Database initialized")

    def _upgrade_prediction_table():
        """Add newer fields without deleting existing local student data."""
        inspector = inspect(db.engine)
        with db.engine.begin() as connection:
            if "prediction" in inspector.get_table_names():
                existing = {column["name"].lower() for column in inspector.get_columns("prediction")}
                additions = {
                    "courseid": "CourseID INTEGER",
                    "predictedoutcome": "PredictedOutcome VARCHAR(30)",
                    "successprobability": "SuccessProbability FLOAT",
                    "modelversion": "ModelVersion VARCHAR(80)",
                    "observationwindowdays": "ObservationWindowDays INTEGER DEFAULT 60",
                    "inputsnapshot": "InputSnapshot TEXT",
                }
                for key, definition in additions.items():
                    if key not in existing:
                        connection.execute(text(f"ALTER TABLE prediction ADD COLUMN {definition}"))
            if "assignment" in inspector.get_table_names():
                assignment_columns = {column["name"].lower() for column in inspector.get_columns("assignment")}
                if "completedat" not in assignment_columns:
                    connection.execute(text("ALTER TABLE assignment ADD COLUMN CompletedAt DATETIME"))

    @app.cli.command("download-oulad")
    @click.option("--output-dir", default="data/oulad/raw", show_default=True)
    def download_oulad_command(output_dir):
        """Download and checksum the official OULAD release."""
        from .ml.oulad import download_oulad
        result = download_oulad(output_dir)
        click.echo(f"OULAD {result['status']}: {', '.join(result['files'])}")

    @app.cli.command("prepare-oulad")
    @click.option("--raw-dir", default="data/oulad/raw", show_default=True)
    @click.option("--output", default="data/oulad/processed/training_data.csv", show_default=True)
    @click.option("--cutoff-day", default=60, show_default=True, type=int)
    def prepare_oulad_command(raw_dir, output, cutoff_day):
        """Build the leakage-safe early-warning training table."""
        from .ml.oulad import prepare_oulad
        result = prepare_oulad(raw_dir, output, cutoff_day)
        click.echo(
            f"Prepared {result['rows']} rows: "
            f"{result['class_counts']['successful']} successful, "
            f"{result['class_counts']['at_risk']} at risk"
        )

    @app.cli.command("train-model")
    @click.option("--dataset", required=True, type=click.Path(exists=True))
    def train_model_command(dataset):
        """Train/evaluate the OULAD Random Forest classifier."""
        from .services import train_model
        with open(dataset, newline="", encoding="utf-8") as f:
            metrics = train_model(list(csv.DictReader(f)))
        click.echo(
            f"Accuracy={metrics['accuracy']:.3f}; F1={metrics['f1']:.3f}; "
            f"ROC-AUC={metrics['roc_auc']:.3f}"
        )

    @app.cli.command("seed-demo")
    @click.option("--admin-password", envvar="DEMO_ADMIN_PASSWORD", required=True)
    def seed_demo(admin_password):
        """Add a local demonstration student, course, assignment and administrator."""
        from datetime import datetime, timedelta, timezone
        from .models import Administrator, Assignment, Course, Student
        s = Student.query.filter_by(email="student@example.com").first()
        if not s:
            s = Student(full_name="Demo Student", email="student@example.com", level="400", programme="Software Engineering", study_preference="evening", available_study_hours=2, previous_grade=68, attendance_rate=82, study_habit_score=7)
            s.set_password("StudyDemo123!"); db.session.add(s); db.session.flush()
            c = Course(student_id=s.id, course_code="SEN401", course_title="Machine Learning", credit_unit=3, semester="First", difficulty=5, examination_date=datetime.now(timezone.utc)+timedelta(days=30)); db.session.add(c); db.session.flush()
            db.session.add(Assignment(student_id=s.id, course_id=c.id, title="Random Forest evaluation", due_date=datetime.now(timezone.utc)+timedelta(days=7), weight=20))
        a = Administrator.query.filter_by(username="admin").first()
        if not a:
            a = Administrator(full_name="System Administrator", username="admin"); a.set_password(admin_password); db.session.add(a)
        db.session.commit(); click.echo("Demo records created; student password: StudyDemo123!")

    return app
