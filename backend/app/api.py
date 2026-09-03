from datetime import datetime, timedelta, timezone
from functools import wraps
import json
from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import create_access_token, get_jwt, get_jwt_identity, jwt_required
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from .extensions import db
from .models import Administrator, Assignment, Course, FocusSession, Notification, Prediction, Recommendation, Student, StudySchedule
from .services import generate_schedule, predict_and_recommend, sync_assignment_notifications, sync_study_session_notifications

api = Blueprint("api", __name__)

def body(required=()):
    data = request.get_json(silent=True) or {}
    missing = [k for k in required if data.get(k) in (None, "")]
    if missing: raise ValueError("Missing fields: " + ", ".join(missing))
    return data

def student(): return db.session.get(Student, int(get_jwt_identity()))
def iso(v): return v.isoformat() if v else None
def admin_required(fn):
    @wraps(fn)
    @jwt_required()
    def wrapped(*args, **kwargs):
        if get_jwt().get("role") != "administrator": return jsonify(error="Administrator access required"), 403
        return fn(*args, **kwargs)
    return wrapped

@api.errorhandler(ValueError)
def bad_data(e): return jsonify(error=str(e)), 400

@api.errorhandler(IntegrityError)
def conflict(_):
    db.session.rollback()
    return jsonify(error="That record already exists or conflicts with existing academic data"), 409

@api.get("/health")
def health(): return jsonify(status="ok", app_version=current_app.config["APP_VERSION"])

@api.post("/auth/register")
def register():
    d = body(("full_name", "email", "password", "level", "programme"))
    if len(d["password"]) < 8: raise ValueError("Password must contain at least 8 characters")
    if Student.query.filter(func.lower(Student.email) == d["email"].lower()).first(): return jsonify(error="Email already registered"), 409
    s = Student(full_name=d["full_name"], email=d["email"].lower(), level=d["level"], programme=d["programme"], study_preference=d.get("study_preference", "balanced"), available_study_hours=float(d.get("available_study_hours", 2)), previous_grade=float(d.get("previous_grade", 50)), attendance_rate=d.get("attendance_rate"), study_habit_score=float(d.get("study_habit_score", 5)))
    s.set_password(d["password"]); db.session.add(s); db.session.commit()
    return jsonify(token=create_access_token(str(s.id), additional_claims={"role":"student"}), user=student_json(s)), 201

@api.post("/auth/login")
def login():
    d = body(("email", "password")); s = Student.query.filter(func.lower(Student.email) == d["email"].lower()).first()
    if not s or not s.check_password(d["password"]): return jsonify(error="Incorrect email or password."), 401
    return jsonify(token=create_access_token(str(s.id), additional_claims={"role":"student"}), user=student_json(s))

@api.get("/profile")
@jwt_required()
def profile(): return jsonify(student_json(student()))

@api.patch("/profile")
@jwt_required()
def update_profile():
    s=student(); d=body()
    for key in ("full_name","level","programme","study_preference","available_study_hours","previous_grade","attendance_rate","study_habit_score"):
        if key in d: setattr(s,key,d[key])
    db.session.commit(); return jsonify(student_json(s))

@api.route("/courses", methods=["GET","POST"])
@jwt_required()
def courses():
    s=student()
    if request.method == "GET": return jsonify([course_json(x) for x in Course.query.filter_by(student_id=s.id).all()])
    d=body(("course_code","course_title","credit_unit","semester")); c=Course(student_id=s.id, course_code=d["course_code"].upper(), course_title=d["course_title"], credit_unit=int(d["credit_unit"]), semester=d["semester"], description=d.get("description"), difficulty=int(d.get("difficulty",3)), examination_date=parse_dt(d.get("examination_date")))
    db.session.add(c); db.session.commit(); generate_schedule(s); return jsonify(course_json(c)),201

@api.route("/courses/<int:item_id>", methods=["PATCH","DELETE"])
@jwt_required()
def course_item(item_id):
    s=student(); c=Course.query.filter_by(id=item_id,student_id=s.id).first_or_404()
    if request.method=="DELETE":
        Prediction.query.filter_by(student_id=s.id,course_id=c.id).update({Prediction.course_id:None},synchronize_session=False)
        db.session.delete(c); db.session.commit(); return "",204
    d=body()
    for k in ("course_code","course_title","credit_unit","semester","description","difficulty"):
        if k in d: setattr(c,k,d[k])
    if "examination_date" in d: c.examination_date=parse_dt(d["examination_date"])
    db.session.commit(); generate_schedule(student()); return jsonify(course_json(c))

@api.route("/assignments", methods=["GET","POST"])
@jwt_required()
def assignments():
    s=student()
    if request.method=="GET": return jsonify([assignment_json(x) for x in Assignment.query.filter_by(student_id=s.id).all()])
    d=body(("course_id","title","due_date")); course=Course.query.filter_by(id=int(d["course_id"]),student_id=s.id).first_or_404()
    a=Assignment(course_id=course.id,student_id=s.id,title=d["title"],description=d.get("description"),due_date=parse_dt(d["due_date"]),weight=float(d.get("weight",10)),status=d.get("status","pending")); db.session.add(a); db.session.commit(); generate_schedule(s); return jsonify(assignment_json(a)),201

@api.patch("/assignments/<int:item_id>")
@jwt_required()
def assignment_item(item_id):
    a=Assignment.query.filter_by(id=item_id,student_id=student().id).first_or_404(); d=body(); previous_status=a.status
    for k in ("title","description","weight","status"):
        if k in d: setattr(a,k,d[k])
    if "due_date" in d:a.due_date=parse_dt(d["due_date"])
    if a.status not in {"pending", "completed"}: raise ValueError("Assignment status must be pending or completed")
    if a.status == "completed":
        if previous_status != "completed" or not a.completed_at: a.completed_at=datetime.now(timezone.utc)
        StudySchedule.query.filter_by(student_id=a.student_id, assignment_id=a.id, status="pending").delete(synchronize_session=False)
    elif "status" in d:
        a.completed_at=None
    db.session.commit(); generate_schedule(student()); return jsonify(assignment_json(a))

@api.route("/schedules",methods=["GET","POST"])
@jwt_required()
def schedules():
    s=student()
    if request.method=="POST": return jsonify([schedule_json(x) for x in generate_schedule(s,int((request.get_json(silent=True) or {}).get("days",7)))])
    query=StudySchedule.query.filter_by(student_id=s.id)
    if request.args.get("include_completed", "false").lower() not in {"1", "true", "yes"}:
        query=query.filter_by(status="pending")
    return jsonify([schedule_json(x) for x in query.order_by(StudySchedule.study_date, StudySchedule.start_time).all()])

@api.patch("/schedules/<int:item_id>")
@jwt_required()
def schedule_item(item_id):
    x=StudySchedule.query.filter_by(id=item_id,student_id=student().id).first_or_404(); d=body(); x.status=d.get("status",x.status); db.session.commit(); return jsonify(schedule_json(x))

@api.route("/focus-sessions", methods=["GET", "POST"])
@jwt_required()
def focus_sessions():
    s=student()
    if request.method == "GET":
        limit=min(max(int(request.args.get("limit", 50)), 1), 200)
        items=FocusSession.query.filter_by(student_id=s.id).order_by(FocusSession.completed_at.desc()).limit(limit).all()
        return jsonify([focus_session_json(x) for x in items])
    d=body(("duration_minutes", "started_at"))
    duration=int(d["duration_minutes"])
    if not 1 <= duration <= 180: raise ValueError("Focus duration must be between 1 and 180 minutes")
    course=None
    assignment=None
    schedule=None
    if d.get("course_id") not in (None, ""):
        course=Course.query.filter_by(id=int(d["course_id"]), student_id=s.id).first_or_404()
    if d.get("assignment_id") not in (None, ""):
        assignment=Assignment.query.filter_by(id=int(d["assignment_id"]), student_id=s.id).first_or_404()
    if d.get("schedule_id") not in (None, ""):
        schedule=StudySchedule.query.filter_by(id=int(d["schedule_id"]), student_id=s.id).first_or_404()
        course=course or (db.session.get(Course, schedule.course_id) if schedule.course_id else None)
        assignment=assignment or (db.session.get(Assignment, schedule.assignment_id) if schedule.assignment_id else None)
    item=FocusSession(
        student_id=s.id, course_id=course.id if course else None,
        assignment_id=assignment.id if assignment else None,
        schedule_id=schedule.id if schedule else None,
        duration_minutes=duration, started_at=parse_dt(d["started_at"]),
        completed_at=parse_dt(d.get("completed_at")) or datetime.now(timezone.utc),
        mode=str(d.get("mode", "pomodoro"))[:30], status="completed",
    )
    db.session.add(item); db.session.flush()
    schedule_completed=False
    if schedule and schedule.status != "completed":
        focused=db.session.query(func.sum(FocusSession.duration_minutes)).filter_by(
            student_id=s.id, schedule_id=schedule.id, status="completed"
        ).scalar() or 0
        if focused >= schedule.duration:
            schedule.status="completed"; schedule_completed=True
    db.session.commit()
    return jsonify(session=focus_session_json(item), schedule_completed=schedule_completed), 201

@api.post("/predictions")
@jwt_required()
def predict():
    s=student(); d=request.get_json(silent=True) or {}
    if d.get("course_id") in (None, ""):
        return jsonify(
            error="Please refresh StudySmart, then select a registered course before running the assessment.",
            code="course_required",
        ),400
    try: course_id=int(d["course_id"])
    except (TypeError, ValueError) as error: raise ValueError("Course must be a valid registered course") from error
    course=Course.query.filter_by(id=course_id,student_id=s.id).first()
    if not course: return jsonify(error="Select one of your registered courses"),404
    p,r,f,bundle=predict_and_recommend(s, course, d)
    return jsonify(
        prediction=prediction_json(p), recommendation=recommendation_json(r), features=f,
        model={
            "dataset": bundle["dataset"],
            "version": bundle["model_version"],
            "observation_window_days": bundle["observation_window_days"],
        },
    ),201

@api.get("/predictions")
@jwt_required()
def predictions(): return jsonify([prediction_json(x) for x in Prediction.query.filter_by(student_id=student().id).order_by(Prediction.prediction_date.desc()).all()])

@api.get("/recommendations")
@jwt_required()
def recommendations(): return jsonify([recommendation_json(x) for x in Recommendation.query.filter_by(student_id=student().id).all()])

@api.get("/notifications")
@jwt_required()
def notifications():
    s=student(); sync_study_session_notifications(s); sync_assignment_notifications(s)
    return jsonify([notification_json(x) for x in Notification.query.filter_by(student_id=s.id).order_by(Notification.date_sent.desc()).all()])

@api.patch("/notifications/<int:item_id>")
@jwt_required()
def notification_item(item_id):
    n=Notification.query.filter_by(id=item_id,student_id=student().id).first_or_404()
    status=(request.get_json(silent=True) or {}).get("status","read")
    if status not in {"read","unread"}: raise ValueError("Notification status must be read or unread")
    n.status=status; db.session.commit(); return jsonify(notification_json(n))

@api.get("/dashboard")
@jwt_required()
def dashboard():
    sid=student().id; courses=Course.query.filter_by(student_id=sid).all(); schedules=StudySchedule.query.filter_by(student_id=sid).all(); assignments=Assignment.query.filter_by(student_id=sid).all(); latest=Prediction.query.filter(Prediction.student_id==sid,Prediction.course_id.isnot(None)).order_by(Prediction.prediction_date.desc()).first()
    today=datetime.now().astimezone().date(); week_start=today-timedelta(days=today.weekday())
    focus=FocusSession.query.filter_by(student_id=sid,status="completed").all()
    focus_today=sum(x.duration_minutes for x in focus if _local_date(x.completed_at)==today)
    focus_week=sum(x.duration_minutes for x in focus if _local_date(x.completed_at)>=week_start)
    upcoming=sorted((x for x in schedules if x.status=="pending"), key=lambda x:(x.study_date,x.start_time))
    course_progress=[course_progress_json(course,assignments,schedules,focus) for course in courses]
    return jsonify(courses=len(courses),completed_sessions=sum(x.status=="completed" for x in schedules),pending_tasks=sum(x.status=="pending" for x in assignments),upcoming_events=[schedule_json(x) for x in upcoming[:5]],predicted_performance=prediction_json(latest) if latest else None,progress_percent=round(100*sum(x.status=="completed" for x in schedules)/len(schedules),1) if schedules else 0,focus_minutes_today=focus_today,focus_minutes_week=focus_week,course_progress=course_progress)

@api.post("/admin/login")
def admin_login():
    d=body(("username","password")); a=Administrator.query.filter_by(username=d["username"]).first()
    if not a or not a.check_password(d["password"]): return jsonify(error="Invalid credentials"),401
    return jsonify(token=create_access_token(str(a.id),additional_claims={"role":"administrator"}))

@api.get("/admin/students")
@admin_required
def admin_students(): return jsonify([student_json(x) for x in Student.query.all()])

def parse_dt(value): return datetime.fromisoformat(value.replace("Z","+00:00")) if value else None
def student_json(x): return {"id":x.id,"full_name":x.full_name,"email":x.email,"level":x.level,"programme":x.programme,"study_preference":x.study_preference,"available_study_hours":x.available_study_hours,"previous_grade":x.previous_grade,"attendance_rate":x.attendance_rate,"study_habit_score":x.study_habit_score}
def course_json(x): return {"id":x.id,"course_code":x.course_code,"course_title":x.course_title,"credit_unit":x.credit_unit,"semester":x.semester,"difficulty":x.difficulty,"examination_date":iso(x.examination_date)}
def assignment_json(x): return {"id":x.id,"course_id":x.course_id,"title":x.title,"description":x.description,"due_date":iso(x.due_date),"weight":x.weight,"status":x.status,"completed_at":iso(x.completed_at)}

def course_progress_json(course, assignments, schedules, focus_sessions):
    course_assignments=[item for item in assignments if item.course_id==course.id]
    completed=[item for item in course_assignments if item.status=="completed"]
    pending=[item for item in course_assignments if item.status=="pending"]
    completed_weight=sum(max(0,float(item.weight or 0)) for item in completed)
    recorded_weight=sum(max(0,float(item.weight or 0)) for item in course_assignments)
    course_schedules=[item for item in schedules if item.course_id==course.id]
    course_focus=[item for item in focus_sessions if item.course_id==course.id and item.status=="completed"]
    latest=max(completed,key=lambda item:item.completed_at or item.due_date) if completed else None
    upcoming=min(pending,key=lambda item:item.due_date) if pending else None
    return {
        "course_id":course.id,"course_code":course.course_code,"course_title":course.course_title,
        "assessment_progress_percent":round(min(100,completed_weight),1),
        "completed_assessment_weight":round(completed_weight,1),"recorded_assessment_weight":round(recorded_weight,1),
        "completed_assessments":len(completed),"total_assessments":len(course_assignments),
        "completed_study_sessions":sum(item.status=="completed" for item in course_schedules),
        "focus_minutes":sum(item.duration_minutes for item in course_focus),
        "latest_completed_title":latest.title if latest else None,"latest_completed_at":iso(latest.completed_at) if latest else None,
        "next_assignment_title":upcoming.title if upcoming else None,"next_assignment_due":iso(upcoming.due_date) if upcoming else None,
    }
def schedule_json(x): return {"id":x.id,"course_id":x.course_id,"assignment_id":x.assignment_id,"study_date":iso(x.study_date),"start_time":iso(x.start_time),"end_time":iso(x.end_time),"duration":x.duration,"topic":x.topic,"status":x.status}
def prediction_json(x):
    if not x: return None
    snapshot = None
    if x.input_snapshot:
        try: snapshot = json.loads(x.input_snapshot)
        except (TypeError, ValueError): snapshot = None
    return {
        "id":x.id,
        "course_id":x.course_id,
        "course_code":x.course.course_code if x.course else None,
        "course_title":x.course.course_title if x.course else None,
        "predicted_outcome":x.predicted_outcome,
        "success_probability":x.success_probability,
        "confidence_score":x.confidence_score,
        "risk_level":x.risk_level,
        "model_version":x.model_version,
        "observation_window_days":x.observation_window_days,
        "input_snapshot":snapshot,
        "prediction_date":iso(x.prediction_date),
    }
def recommendation_json(x): return {"id":x.id,"prediction_id":x.prediction_id,"recommendation_type":x.recommendation_type,"text":x.recommendation_text,"priority_level":x.priority_level}
def notification_json(x): return {"id":x.id,"message":x.message,"type":x.notification_type,"status":x.status,"date_sent":iso(x.date_sent)}
def focus_session_json(x): return {"id":x.id,"course_id":x.course_id,"assignment_id":x.assignment_id,"schedule_id":x.schedule_id,"duration_minutes":x.duration_minutes,"started_at":iso(x.started_at),"completed_at":iso(x.completed_at),"mode":x.mode,"status":x.status}
def _local_date(value):
    if not value: return datetime.min.date()
    if value.tzinfo is None: value=value.replace(tzinfo=timezone.utc)
    return value.astimezone().date()
