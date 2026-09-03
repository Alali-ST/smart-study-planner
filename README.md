# Intelligent Machine Learning-Based Smart Study Planner

Implementation of the system specified in Chapter 3 of `Alali_Tobin_Chapter_1_FYP.pdf`: a client-server application with a Python/Flask REST backend, MySQL relational database, scikit-learn Random Forest model, responsive Bootstrap web client, and Flutter Android/iOS client.

## Included modules

- Student registration/login, expiring access tokens, hashed passwords, profile maintenance and student-scoped records.
- Course and assignment management, including difficulty, examination dates, deadlines, assessment weights and completion state.
- Adaptive timetable generation based on available hours, preference, course difficulty/credit load and deadline proximity. Each active target normally receives two spaced sessions per week, with a third permitted when its deadline is within three days. Competing targets rotate across free days, assignments are not scheduled after a future deadline, and pending slots are regenerated after academic information changes.
- Six distinct responsive views: Overview, Courses, Assignments, live Planner calendar, Focus room and Performance.
- Persistent Pomodoro timer with 25/5, 50/10 and custom intervals, optional finish alerts, course/assignment linking, focus history and automatic timetable progress.
- Course-specific OULAD-trained Random Forest early-warning classification. The student selects a registered course and supplies that course's first-60-day assessment activity; the system estimates `successful` (Pass/Distinction) or `at_risk` (Fail/Withdrawn) with probability, confidence and risk level.
- Prediction-driven recommendations, an interactive in-app notification bell, timely timetable-session reminders and exactly one persistent reminder for every pending assignment regardless of deadline distance. The assignment reminder appears immediately after the assignment is added, includes its due date, updates if its details change and disappears when it is completed. The bell keeps study-session reminders only for today and tomorrow instead of listing the full future timetable. Unread reminders can be opened and marked read individually or together. The Overview and Courses pages include per-course assessment progress based on the weights of assignments marked completed, together with completed-assessment counts, focus minutes, completed study sessions and the latest milestone. This is workload completion, not a predicted grade or evidence of subject mastery.
- Administrator login and student listing for the limited administrator role described by the PDF.
- MySQL schema, non-destructive local schema upgrade, ORM models/migration support, official-data preparation commands, backend tests and a Flutter widget test.
- A premium responsive web experience with an editorial sign-in screen, true application-page navigation, adaptive desktop sidebar/mobile dock, animated metrics, accessible motion fallbacks and touch-friendly forms.

## Repository structure

```text
backend/  Flask MVC-style API, domain models, services, SQL, ML and tests
web/      Responsive HTML5/CSS3/Bootstrap/JavaScript client served by Flask
mobile/   Flutter client with secure token storage and REST integration
docs/     API and requirements traceability notes
```

## Backend and web setup

### Quick start on Windows

Double-click `START_STUDYSMART.bat`. On the first launch it creates an isolated Python environment, installs the required components, initializes or upgrades the local database, trains the Random Forest model from the included structured OULAD records, starts Flask and opens `http://127.0.0.1:5000` automatically. Existing student accounts and records are preserved.

Do not open `web/index.html` directly. A `file://` page cannot communicate with the Flask REST API, which causes browser fetch failures.

### Manual/MySQL setup

1. Create a MySQL database and user, then run `backend/schema.sql`, or configure the URL and let SQLAlchemy create the schema with `flask init-db`. The one-click launcher uses the local SQLite development fallback when `DATABASE_URL` is not configured.
2. From `backend`, use Python 3.11-3.14, create a virtual environment and install `requirements.txt`.
3. Copy `.env.example` to `.env`, set strong secrets and the MySQL `DATABASE_URL`, then expose the variables to the process.
4. Run `flask --app run.py init-db`.
5. Train the model: `flask --app run.py train-model --dataset data/oulad/processed/training_data.csv`.
6. To reproduce the dataset from the official archive, run `flask --app run.py download-oulad`, then `flask --app run.py prepare-oulad --cutoff-day 60`, and retrain using step 5.
7. Optionally seed a demonstration account with `flask --app run.py seed-demo --admin-password <strong-password>`.
8. Start with `python run.py`, then open `http://localhost:5000`.

The included `data/oulad/processed/training_data.csv` contains 30,059 anonymized, derived student-module records from the Open University Learning Analytics Dataset (OULAD), licensed CC BY 4.0. The preprocessing excludes exams, uses only assessments due and submissions observed by day 60, and keeps student identities out of the feature set. See `backend/data/oulad/README.md` for attribution, fields, limitations and reproduction details.

The real OULAD held-out student-group split produced accuracy 0.786, precision 0.729, recall 0.848, F1 0.784 and ROC-AUC 0.865. These are evaluation results for this prepared OULAD split, not guaranteed performance for another university. See `docs/OULAD_EVALUATION.md`. Run backend tests from `backend` with `pytest`.

### Browser update protection

StudySmart version-checks its web client against the running Flask service and disables caching for the local HTML, CSS and JavaScript files. This prevents an already-open older assessment form from submitting to a newer API without the required course selection. If a browser tab predates this protection, refresh it once; the prediction window will then show **1. Choose the registered course you want to assess** above the OULAD activity fields.

## Flutter setup

The Flutter client now contains the complete student workflow: registration/sign-in, Overview, Planner, Courses, Assignments, Pomodoro Focus, Notifications and OULAD Performance. Follow `mobile/README.md`; the API address is supplied at build time with `--dart-define=API_URL=...`, so source code does not need editing between emulator and production builds.

## GitHub and Vercel

The root `app.py`, `requirements.txt`, `.python-version` and `vercel.json` make the Flask web/API application deployable on Vercel. Production requires a persistent external MySQL `DATABASE_URL` plus strong secret environment variables. See `docs/DEPLOYMENT.md` for the short publishing checklist. The web application also includes the StudySmart tab icon and installable mobile-web metadata.

## Production security

The implementation hashes passwords, validates ownership on protected resources, expires access tokens, uses ORM parameterization, input constraints and role checks. In production, terminate TLS at a trusted reverse proxy, disable Flask debug mode, restrict CORS, rotate strong secrets, add rate limiting/monitoring, back up MySQL, and store Flutter tokens in platform secure storage (already used by the scaffold). HTTPS is a deployment property and is not simulated by the development server.
