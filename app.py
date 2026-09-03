"""Vercel/WSGI entry point for StudySmart."""
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
os.environ.setdefault(
    "MODEL_PATH",
    str(PROJECT_ROOT / "backend" / "instance" / "oulad_random_forest.joblib"),
)

from backend.app import create_app
from backend.app.extensions import db

app = create_app()

# A fresh hosted MySQL database can be initialized without a separate shell.
# create_all is idempotent and does not remove existing student records.
if os.getenv("DATABASE_URL") or os.getenv("TIDB_HOST") or os.getenv("VERCEL"):
    with app.app_context():
        db.create_all()
