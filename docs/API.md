# REST API (`/api/v1`)

All protected requests use `Authorization: Bearer <token>` and JSON.

| Method | Route | Purpose |
|---|---|---|
| POST | `/auth/register`, `/auth/login` | Student authentication |
| GET, PATCH | `/profile` | View/update academic profile and study preferences |
| GET, POST | `/courses` | List/add registered courses |
| PATCH, DELETE | `/courses/{id}` | Update/remove an owned course |
| GET, POST | `/assignments` | List/add assignments |
| PATCH | `/assignments/{id}` | Update deadline or completion |
| GET, POST | `/schedules` | List upcoming sessions/regenerate adaptive timetable (`include_completed=true` adds history) |
| PATCH | `/schedules/{id}` | Mark a study session complete |
| GET, POST | `/focus-sessions` | List/record completed Pomodoro intervals and linked timetable progress |
| GET, POST | `/predictions` | Prediction history/run OULAD Random Forest early-warning inference |
| GET | `/recommendations` | Personalized recommendations |
| GET | `/notifications` | Idempotent reminders for timetable sessions today/tomorrow and one current reminder for every pending assignment |
| PATCH | `/notifications/{id}` | Mark a reminder `read` or `unread` |
| GET | `/dashboard` | Progress, events, tasks, per-course assessment progress and latest prediction |
| POST | `/admin/login` | Administrator authentication |
| GET | `/admin/students` | Administrator user management view |

The API returns conventional `200/201/204`, `400`, `401`, `403`, `404`, `409` and `422` responses. Database ownership filters prevent horizontal access to another student's records.

Completing a timetable session hides it from the default upcoming response but retains it when `include_completed=true`. Completing an assignment clears that assignment's future pending study sessions and rebuilds the remaining plan. A completed focus interval linked to a timetable entry automatically completes that entry only when cumulative focused minutes meet its planned duration.

`dashboard.course_progress` reports each course separately. `assessment_progress_percent` is the sum of the weights of assignments marked `completed`, capped at 100%. It is intentionally not calculated from OULAD prediction probability, scores or focus time, and therefore must be interpreted as recorded assessment-workload completion rather than a grade. Supporting fields include completed and total assessment counts, focused minutes, completed study sessions, the latest completed assessment and the next pending assessment. Assignment responses include `completed_at`, which is recorded when an assignment becomes completed and cleared if it is reopened.

## Prediction request

`POST /predictions` requires the selected StudySmart course and that course's assessment activity observed through day 60:

```json
{
  "course_id": 4,
  "previous_attempts": 0,
  "assessments_due": 3,
  "assessments_submitted": 3,
  "mean_score": 65,
  "on_time_submissions": 3,
  "mean_submission_delay": -1
}
```

`course_id` must identify a course owned by the authenticated student. The identifier binds the entered activity and the resulting prediction to that particular course; the local course code itself is not used as a Random Forest feature because Miva course codes do not correspond to OULAD module codes. `mean_submission_delay` is measured in days; a negative value means early submission. The response contains the selected course ID/code/title, `predicted_outcome` (`successful` or `at_risk`), `success_probability`, `confidence_score`, `risk_level`, model version, observation window, validated feature snapshot and course-specific recommendation. Here, `successful` means the OULAD Pass/Distinction class and `at_risk` means the historical Fail/Withdrawn class. This is a course-level early-warning classification, not a guaranteed final result.
