# Requirements traceability and underspecified decisions

The complete 54-page PDF was inspected, with implementation requirements concentrated in Chapter 3 (pages 34-54).

| PDF requirement | Implementation |
|---|---|
| Flutter Android/iOS client | `mobile/lib`, one codebase with login, dashboard, schedule completion, prediction and secure token storage |
| Python Flask REST/JSON backend | `backend/app/api.py` and application factory |
| MySQL and eight named entities | ORM models plus `backend/schema.sql`: Student, Course, Assignment, StudySchedule, Prediction, Recommendation, Notification, Administrator |
| Random Forest / scikit-learn | OULAD preprocessing, student-grouped training/validation split, persisted classifier and accuracy/precision/recall/F1/ROC-AUC evaluation in `services.py` |
| Intelligent adaptive scheduling | Priority score uses workload, difficulty, credits, deadlines/exams, available hours and morning preference; regenerates on relevant changes |
| Prediction-based recommendations | Every new prediction is bound to a student-owned registered course and has a linked course-specific risk recommendation |
| Progress dashboards | Web and mobile cards, sessions, tasks, upcoming events and the latest course-specific prediction |
| User-requested productivity extension | Separate Courses, Assignments, Planner, Focus and Performance views; live calendar; persisted Pomodoro focus sessions |
| Reminders | Persisted in-app reminders synchronized to timetable sessions occurring today or tomorrow, plus exactly one reminder for each pending assignment until completion |
| Secure authentication/access | Hashed passwords, expiring bearer tokens, ownership filters, role checks, validation and relational constraints |
| Responsive HTML5/CSS3/Bootstrap/JS | `web/`, served by Flask and consuming the same REST API |

## Explicitly underspecified by the PDF

- No training dataset, exact target definition, preprocessing recipe, hyperparameters or acceptance threshold is supplied. OULAD was selected as an established, anonymized open educational dataset. The implemented target is `successful` (Pass/Distinction) versus `at_risk` (Fail/Withdrawn), based only on assessment activity observable through day 60. This is a documented implementation decision rather than a claim that the PDF prescribed OULAD or this target.
- No scheduling formula, conflict rules, calendar time zone or notification delivery provider is defined. The implementation uses a documented deterministic priority score, at most one daily slot, normally two spaced sessions per target each week (three within three days of a deadline), UTC storage and in-app persisted notifications. It does not claim push/email delivery.
- “Confidence score” is not defined. The API retains the probability assigned to the selected class for evaluation compatibility, but the user interface avoids the ambiguous word “confidence” and displays both complementary outcome probabilities (chance of passing and chance of not passing). The course selection binds the submitted early-activity values to a registered course; the Miva course code is not itself an input feature. These probabilities are not externally calibrated for Miva Open University students.
- Diagrams are named but several PDF pages contain placeholders/empty figures. The implementable client-server/MVC boundaries and eight core entities were followed. `FocusSession` is a ninth, explicitly documented extension added in response to the user's later Pomodoro requirement.
- The Administrator role is mentioned for user management, dataset maintenance and oversight, but exact workflows are absent. Only administrator authentication and read-only student listing are exposed; destructive or dataset-upload endpoints were intentionally not invented.
- The prose mentions study goals and learning strategies, but the authoritative eight-entity schema provides no Goal entity or content catalog. These are represented through schedules/recommendation text rather than unsupported new tables.
- Attendance is “where available” and remains nullable in the academic profile, but is not used by the OULAD classifier because the released source tables do not provide a directly equivalent attendance measure.
- Session transport is not prescribed. Expiring signed bearer tokens were chosen for REST/mobile compatibility. HTTPS must be configured at deployment.
