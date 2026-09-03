from datetime import datetime, timedelta, timezone
from pathlib import Path
from app.services import train_model

def headers(token): return {"Authorization":f"Bearer {token}"}

def test_auth_and_profile(client,auth):
    assert client.get("/api/v1/profile",headers=headers(auth)).status_code==200
    wrong_password=client.post("/api/v1/auth/login",json={"email":"student@example.com","password":"wrong"})
    unknown_account=client.post("/api/v1/auth/login",json={"email":"nobody@example.com","password":"wrong"})
    assert wrong_password.status_code==401
    assert unknown_account.status_code==401
    assert wrong_password.get_json()["error"]=="Incorrect email or password."
    assert unknown_account.get_json()["error"]=="Incorrect email or password."

def test_web_registration_duplicate_and_relogin(client):
    page=client.get("/")
    assert page.status_code == 200
    assert b'data-page-content="courses"' in page.data
    assert b'data-page-content="planner"' in page.data
    assert b'data-page-content="focus"' in page.data
    account={"full_name":"Tobin Alali","email":"alali.tobin@miva.edu.ng","password":"Alali#123","level":"400","programme":"Software Engineering"}
    created=client.post("/api/v1/auth/register",json=account)
    assert created.status_code == 201 and created.get_json()["token"]
    assert client.post("/api/v1/auth/register",json=account).status_code == 409
    login=client.post("/api/v1/auth/login",json={"email":account["email"],"password":account["password"]})
    assert login.status_code == 200
    token=login.get_json()["token"]
    dashboard=client.get("/api/v1/dashboard",headers=headers(token))
    assert dashboard.status_code == 200 and dashboard.get_json()["courses"] == 0

def test_registration_validation(client):
    weak={"full_name":"Student","email":"weak@example.com","password":"short","level":"100","programme":"Computing"}
    assert client.post("/api/v1/auth/register",json=weak).status_code == 400
    missing={"email":"missing@example.com","password":"long-enough-password"}
    assert client.post("/api/v1/auth/register",json=missing).status_code == 400

def test_course_assignment_schedule(client,auth):
    h=headers(auth)
    c=client.post("/api/v1/courses",headers=h,json={"course_code":"SEN401","course_title":"Machine Learning","credit_unit":3,"semester":"First","difficulty":5}).get_json()
    due=(datetime.now(timezone.utc)+timedelta(days=4)).isoformat()
    assert client.post("/api/v1/assignments",headers=h,json={"course_id":c["id"],"title":"Model report","due_date":due,"weight":20}).status_code==201
    schedule=client.get("/api/v1/schedules",headers=h).get_json()
    assert len(schedule)==2 and all(item["topic"]=="Model report" for item in schedule)
    dates=[datetime.fromisoformat(item["study_date"]).date() for item in schedule]
    assert (dates[1]-dates[0]).days>=3

def test_schedule_rotates_and_spaces_multiple_assignments(client,auth):
    h=headers(auth)
    first=client.post("/api/v1/courses",headers=h,json={"course_code":"ROT401","course_title":"Rotation One","credit_unit":3,"semester":"First","difficulty":4}).get_json()
    second=client.post("/api/v1/courses",headers=h,json={"course_code":"ROT402","course_title":"Rotation Two","credit_unit":3,"semester":"First","difficulty":3}).get_json()
    due=(datetime.now(timezone.utc)+timedelta(days=10)).isoformat()
    first_assignment=client.post("/api/v1/assignments",headers=h,json={"course_id":first["id"],"title":"First report","due_date":due,"weight":25}).get_json()
    second_assignment=client.post("/api/v1/assignments",headers=h,json={"course_id":second["id"],"title":"Second report","due_date":due,"weight":20}).get_json()
    schedule=client.get("/api/v1/schedules",headers=h).get_json()
    assert len(schedule)==4
    for assignment_id in (first_assignment["id"],second_assignment["id"]):
        dates=[datetime.fromisoformat(item["study_date"]).date() for item in schedule if item["assignment_id"]==assignment_id]
        assert len(dates)==2 and (dates[1]-dates[0]).days>=2

def test_prediction(client,auth,app):
    course=client.post("/api/v1/courses",headers=headers(auth),json={"course_code":"CMS456","course_title":"Advanced Computing","credit_unit":3,"semester":"First","difficulty":4}).get_json()
    with app.app_context():
        records=[]
        for index in range(40):
            successful=index % 2 == 0
            records.append({
                "id_student":str(index),
                "previous_attempts":0 if successful else 1,
                "assessments_due":2,
                "assessments_submitted":2 if successful else index % 2,
                "completion_rate":1.0 if successful else 0.0,
                "mean_score":75 if successful else 25,
                "on_time_rate":1.0 if successful else 0.0,
                "mean_submission_delay":-2 if successful else 5,
                "target":"successful" if successful else "at_risk",
            })
        train_model(records)
    snapshot={
        "course_id":course["id"],
        "previous_attempts":0,"assessments_due":2,"assessments_submitted":2,
        "mean_score":78,"on_time_submissions":2,"mean_submission_delay":-1,
    }
    response=client.post("/api/v1/predictions",headers=headers(auth),json=snapshot)
    assert response.status_code==201
    result=response.get_json()
    assert result["prediction"]["predicted_outcome"] in {"successful","at_risk"}
    assert result["prediction"]["course_id"] == course["id"]
    assert result["prediction"]["course_code"] == "CMS456"
    assert result["prediction"]["course_title"] == "Advanced Computing"
    assert 0 <= result["prediction"]["success_probability"] <= 100
    assert result["model"]["dataset"] == "OULAD"
    dashboard=client.get("/api/v1/dashboard",headers=headers(auth)).get_json()
    assert dashboard["predicted_performance"]["course_code"] == "CMS456"
    assert "CMS456" in result["recommendation"]["text"]

def test_prediction_input_validation(client,auth):
    response=client.post("/api/v1/predictions",headers=headers(auth),json={})
    assert response.status_code==400
    assert response.get_json()["code"] == "course_required"
    assert "select a registered course" in response.get_json()["error"].lower()

def test_health_exposes_matching_client_version(client):
    response=client.get("/api/v1/health")
    assert response.status_code==200
    assert response.get_json()["app_version"] == "2026.09.03.1"
    assert response.headers["X-StudySmart-Version"] == "2026.09.03.1"
    page=client.get("/")
    assert page.headers["Cache-Control"].startswith("no-store")
    assert b'onclick="openPrediction(event)"' in page.data
    javascript=Path(client.application.static_folder,"js/app.js").read_text(encoding="utf-8")
    assert "function renderPredictionCourseOptions()" in javascript
    assert "renderFormOptions()" not in javascript

def test_notifications_are_generated_once_and_can_be_marked_read(client,auth):
    h=headers(auth)
    course=client.post("/api/v1/courses",headers=h,json={"course_code":"NTS401","course_title":"Notification Testing","credit_unit":3,"semester":"First"}).get_json()
    due=(datetime.now(timezone.utc)+timedelta(days=10)).isoformat()
    client.post("/api/v1/assignments",headers=h,json={"course_id":course["id"],"title":"Reminder report","due_date":due,"weight":10})
    first=client.get("/api/v1/notifications",headers=h)
    assert first.status_code==200
    assignment_items=[item for item in first.get_json() if item["type"].startswith("assignment-")]
    study_items=[item for item in first.get_json() if item["type"]=="study-session"]
    assert len(assignment_items)==1
    assert 1<=len(study_items)<=2
    assert "Reminder report" in assignment_items[0]["message"]
    assert "not completed yet" in assignment_items[0]["message"]
    client.post("/api/v1/schedules",headers=h,json={"days":7})
    second=client.get("/api/v1/notifications",headers=h).get_json()
    assert len([item for item in second if item["type"].startswith("assignment-")])==1
    assert len([item for item in second if item["type"]=="study-session"])==len(study_items)
    updated=client.patch(f"/api/v1/notifications/{assignment_items[0]['id']}",headers=h,json={"status":"read"})
    assert updated.status_code==200 and updated.get_json()["status"]=="read"
    invalid=client.patch(f"/api/v1/notifications/{assignment_items[0]['id']}",headers=h,json={"status":"deleted"})
    assert invalid.status_code==400
    assignment_id=client.get("/api/v1/assignments",headers=h).get_json()[0]["id"]
    client.patch(f"/api/v1/assignments/{assignment_id}",headers=h,json={"status":"completed"})
    after_completion=client.get("/api/v1/notifications",headers=h).get_json()
    assert not any(item["type"]==assignment_items[0]["type"] for item in after_completion)

def test_prediction_rejects_unowned_course(client,auth):
    other={"full_name":"Other Student","email":"other@example.com","password":"securepass","level":"400","programme":"Computing"}
    other_token=client.post("/api/v1/auth/register",json=other).get_json()["token"]
    other_course=client.post("/api/v1/courses",headers=headers(other_token),json={"course_code":"OTH101","course_title":"Other Course","credit_unit":3,"semester":"First"}).get_json()
    response=client.post("/api/v1/predictions",headers=headers(auth),json={
        "course_id":other_course["id"],"previous_attempts":0,"assessments_due":1,
        "assessments_submitted":1,"mean_score":70,"on_time_submissions":1,
        "mean_submission_delay":-1,
    })
    assert response.status_code==404
    assert response.get_json()["error"]=="Select one of your registered courses"

def test_user_cannot_read_another_users_course(client,auth):
    response=client.patch("/api/v1/courses/999",headers=headers(auth),json={"course_title":"x"})
    assert response.status_code==404

def test_completion_visibility_and_focus_session_progress(client,auth):
    h=headers(auth)
    course=client.post("/api/v1/courses",headers=h,json={"course_code":"CSC406","course_title":"Human Computer Interaction","credit_unit":2,"semester":"First","difficulty":3}).get_json()
    due=(datetime.now(timezone.utc)+timedelta(days=5)).isoformat()
    assignment=client.post("/api/v1/assignments",headers=h,json={"course_id":course["id"],"title":"Interface report","due_date":due,"weight":20}).get_json()
    schedule=client.get("/api/v1/schedules",headers=h).get_json()
    assert len(schedule)==2

    completed=client.patch(f"/api/v1/schedules/{schedule[0]['id']}",headers=h,json={"status":"completed"})
    assert completed.status_code==200
    assert len(client.get("/api/v1/schedules",headers=h).get_json())==1
    history=client.get("/api/v1/schedules?include_completed=true",headers=h).get_json()
    assert len(history)==2 and sum(item["status"]=="completed" for item in history)==1

    regenerated=client.post("/api/v1/schedules",headers=h,json={"days":7}).get_json()
    assert not any(item["study_date"]==schedule[0]["study_date"] and item["assignment_id"]==assignment["id"] for item in regenerated)

    focus_target=regenerated[0]
    started=(datetime.now(timezone.utc)-timedelta(minutes=focus_target["duration"])).isoformat()
    focused=client.post("/api/v1/focus-sessions",headers=h,json={
        "duration_minutes":focus_target["duration"],"started_at":started,
        "course_id":course["id"],"assignment_id":assignment["id"],
        "schedule_id":focus_target["id"],"mode":"pomodoro",
    })
    assert focused.status_code==201 and focused.get_json()["schedule_completed"] is True
    assert len(client.get("/api/v1/focus-sessions",headers=h).get_json())==1
    assert client.get("/api/v1/dashboard",headers=h).get_json()["focus_minutes_today"]==focus_target["duration"]

    closed=client.patch(f"/api/v1/assignments/{assignment['id']}",headers=h,json={"status":"completed"})
    assert closed.status_code==200 and closed.get_json()["status"]=="completed"
    assert closed.get_json()["completed_at"] is not None
    assert client.get("/api/v1/schedules",headers=h).get_json()==[]
    progress=client.get("/api/v1/dashboard",headers=h).get_json()["course_progress"][0]
    assert progress["course_id"]==course["id"]
    assert progress["assessment_progress_percent"]==20
    assert progress["completed_assessment_weight"]==20
    assert progress["completed_assessments"]==1 and progress["total_assessments"]==1
    assert progress["latest_completed_title"]=="Interface report"
