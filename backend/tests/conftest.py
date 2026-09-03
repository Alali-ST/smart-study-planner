import pytest
from app import create_app
from app.extensions import db

@pytest.fixture()
def app(tmp_path):
    app=create_app({"TESTING":True,"SQLALCHEMY_DATABASE_URI":"sqlite://","JWT_SECRET_KEY":"test-secret-key-with-at-least-32-bytes","MODEL_PATH":str(tmp_path/"model.joblib")})
    with app.app_context(): db.create_all(); yield app; db.drop_all()

@pytest.fixture()
def client(app): return app.test_client()

@pytest.fixture()
def auth(client):
    data={"full_name":"Test Student","email":"student@example.com","password":"securepass","level":"400","programme":"Software Engineering","previous_grade":65,"available_study_hours":3}
    return client.post("/api/v1/auth/register",json=data).get_json()["token"]
