const API = '/api/v1';
const CLIENT_VERSION = '2026.09.03.4';

if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => navigator.serviceWorker.register('/sw.js').catch(() => {}));
}
let mode = 'login';
let token = localStorage.getItem('study_token');
let profile = null;
let dashboardData = {};
let courses = [];
let assignments = [];
let schedules = [];
let focusSessions = [];
let predictions = [];
let recommendations = [];
let notifications = [];
let assignmentFilter = 'pending';
let calendarDate = new Date(new Date().getFullYear(), new Date().getMonth(), 1);
let selectedDate = dateKey(new Date());
let audioContext = null;
const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

async function call(path, options = {}) {
  const isAuthenticationRequest = ['/auth/login', '/auth/register', '/admin/login'].includes(path);
  const hadSession = Boolean(token);
  options.headers = { ...(options.headers || {}), 'Content-Type': 'application/json' };
  if (hadSession && !isAuthenticationRequest) options.headers.Authorization = `Bearer ${token}`;
  let response;
  try {
    response = await fetch(API + path, options);
  } catch (_) {
    throw Error('StudySmart could not reach its server. Close this page and launch START_STUDYSMART.bat from the project folder.');
  }
  const serverVersion = response.headers.get('X-StudySmart-Version');
  if (serverVersion && serverVersion !== CLIENT_VERSION) {
    window.location.reload();
    throw Error('StudySmart was updated. The page is refreshing so the latest form can load.');
  }
  if (response.status === 401 && hadSession && !isAuthenticationRequest) {
    logout();
    throw Error('Your session expired. Please sign in again.');
  }
  let data = null;
  if (response.status !== 204) {
    try { data = await response.json(); } catch (_) { data = null; }
  }
  if (!response.ok) throw Error(data?.error || 'Something went wrong. Please try again.');
  return data;
}

function toast(message) {
  const element = $('#toast');
  $('.toast-body', element).textContent = message;
  if (window.bootstrap) bootstrap.Toast.getOrCreateInstance(element, { delay: 3400 }).show();
  else {
    element.classList.add('show');
    setTimeout(() => element.classList.remove('show'), 3400);
  }
}

function setMode(nextMode) {
  mode = nextMode;
  const registering = mode === 'register';
  $('#registerFields').hidden = !registering;
  $$('#registerFields input').forEach(input => {
    input.required = registering;
    input.disabled = !registering;
  });
  $('.segmented').classList.toggle('register', registering);
  $('#authTitle').textContent = registering ? 'Build your study workspace' : 'Sign in to your workspace';
  $('#authSubtitle').textContent = registering
    ? 'Tell us the essentials. You can refine your study profile later.'
    : 'Continue building momentum, one focused session at a time.';
  $('.primary-action span').textContent = registering ? 'Create my workspace' : 'Enter workspace';
  $$('[data-mode]').forEach(button => {
    const active = button.dataset.mode === mode;
    button.classList.toggle('active', active);
    button.setAttribute('aria-selected', String(active));
  });
  const password = $('#authForm [name="password"]');
  password.autocomplete = registering ? 'new-password' : 'current-password';
  $('#authError').textContent = '';
}

$$('[data-mode]').forEach(button => button.addEventListener('click', () => setMode(button.dataset.mode)));
$('#showPassword').addEventListener('click', event => {
  const input = $('#authForm [name="password"]');
  const show = input.type === 'password';
  input.type = show ? 'text' : 'password';
  event.currentTarget.textContent = show ? 'Hide' : 'Show';
});

$('#authForm').addEventListener('submit', async event => {
  event.preventDefault();
  const form = event.currentTarget;
  if (location.protocol === 'file:') {
    $('#launchWarning').hidden = false;
    $('#authError').textContent = 'The app must run through its launcher before accounts can be created or signed in.';
    return;
  }
  if (!form.reportValidity()) return;
  const button = $('.primary-action', form);
  const label = $('span', button);
  const original = label.textContent;
  button.disabled = true;
  label.textContent = mode === 'register' ? 'Creating workspace…' : 'Opening workspace…';
  $('#authError').textContent = '';
  try {
    const result = await call(`/auth/${mode}`, { method: 'POST', body: JSON.stringify(formJSON(form)) });
    token = result.token;
    localStorage.setItem('study_token', token);
    await showApp();
  } catch (error) {
    $('#authError').textContent = error.message;
  } finally {
    button.disabled = false;
    label.textContent = original;
  }
});

async function showApp({ silent = false } = {}) {
  try {
    profile = await call('/profile');
    await refreshData();
    $('#auth').hidden = true;
    $('#app').hidden = false;
    const firstName = profile.full_name.trim().split(/\s+/)[0];
    const initials = profile.full_name.trim().split(/\s+/).slice(0, 2).map(part => part[0]).join('').toUpperCase();
    $('#studentName').textContent = firstName;
    $('#topbarName').textContent = profile.full_name;
    $('#topbarProgramme').textContent = profile.programme || 'University student';
    $('#userInitials').textContent = initials || 'ST';
    renderWeek();
    navigate(validPage(location.hash.replace('#/', '')) ? location.hash.replace('#/', '') : 'overview', false);
    window.scrollTo({ top: 0, behavior: 'instant' });
  } catch (error) {
    logout();
    if (!silent) throw error;
  }
}

async function refreshData() {
  const values = await Promise.all([
    call('/dashboard'), call('/courses'), call('/assignments'),
    call('/schedules?include_completed=true'), call('/focus-sessions'),
    call('/predictions'), call('/recommendations'), call('/notifications'),
  ]);
  [dashboardData, courses, assignments, schedules, focusSessions, predictions, recommendations, notifications] = values;
  renderAll();
}

function renderAll() {
  renderDashboard();
  renderOverviewSchedule();
  renderCourseProgress();
  renderCourses();
  renderAssignments();
  renderCalendar();
  renderAgenda();
  renderFocusContext();
  renderFocusStats();
  renderPerformance();
  renderNotifications();
}

function renderNotifications() {
  const unread = notifications.filter(item => item.status === 'unread');
  const badge = $('#notificationBadge');
  badge.hidden = unread.length === 0;
  badge.textContent = unread.length > 9 ? '9+' : String(unread.length);
  $('#notificationButton').setAttribute('aria-label', unread.length ? `Notifications, ${unread.length} unread` : 'Notifications, none unread');
  $('#markAllNotifications').hidden = unread.length === 0;
  const list = $('#notificationList');
  if (!notifications.length) {
    list.innerHTML = `<div class="notification-empty"><span><svg><use href="#i-bell"/></svg></span><strong>You're all caught up</strong><p>Assignment deadlines and generated study sessions will appear here.</p></div>`;
    return;
  }
  list.innerHTML = notifications.slice(0, 30).map(item => {
    const assignment = item.type.startsWith('assignment');
    const icon = assignment ? 'task' : 'calendar';
    const label = assignment && item.message.toLowerCase().includes('overdue') ? 'Overdue assignment' : assignment ? 'Pending assignment' : 'Study session';
    return `<button type="button" class="notification-item ${item.status === 'unread' ? 'unread' : ''}" data-notification-id="${item.id}"><span class="notification-icon"><svg><use href="#i-${icon}"/></svg></span><span><small>${label}</small><strong>${escapeHtml(item.message)}</strong><time>${formatDateTime(item.date_sent)}</time></span>${item.status === 'unread' ? '<i aria-label="Unread"></i>' : ''}</button>`;
  }).join('');
}

function setNotificationPanel(open) {
  $('#notificationPanel').hidden = !open;
  $('#notificationButton').setAttribute('aria-expanded', String(open));
}

async function markNotificationRead(id) {
  const item = notifications.find(notification => notification.id === id);
  if (!item || item.status === 'read') return;
  try {
    const updated = await call(`/notifications/${id}`, { method: 'PATCH', body: JSON.stringify({ status: 'read' }) });
    notifications = notifications.map(notification => notification.id === id ? updated : notification);
    renderNotifications();
  } catch (error) { toast(error.message); }
}

function renderDashboard() {
  $('#courseCount').textContent = dashboardData.courses || 0;
  $('#taskCount').textContent = dashboardData.pending_tasks || 0;
  const progress = Math.max(0, Math.min(100, Number(dashboardData.progress_percent) || 0));
  $('#progress').textContent = `${progress}%`;
  $('#progressRing').style.setProperty('--progress', progress);
  renderPrediction(dashboardData.predicted_performance);
}

function renderCourseProgress() {
  const container = $('#courseProgressGrid');
  const items = dashboardData.course_progress || [];
  if (!items.length) {
    container.innerHTML = emptyPanel('book', 'Add a course and its assessments to begin tracking course progress.');
    return;
  }
  container.innerHTML = items.map(item => {
    const percent = Math.max(0, Math.min(100, Number(item.assessment_progress_percent) || 0));
    const completedWeight = Number(item.completed_assessment_weight) || 0;
    const assessmentText = item.total_assessments
      ? `${item.completed_assessments} of ${item.total_assessments} assessment${item.total_assessments === 1 ? '' : 's'} completed`
      : 'No assessments recorded yet';
    const milestone = item.latest_completed_title
      ? `<div class="progress-milestone"><span><svg><use href="#i-check"/></svg></span><div><small>LATEST PROGRESS</small><strong>${escapeHtml(item.latest_completed_title)}</strong></div></div>`
      : `<div class="progress-milestone pending"><span><svg><use href="#i-task"/></svg></span><div><small>NEXT STEP</small><strong>Complete your first assessment</strong></div></div>`;
    const next = item.next_assignment_title
      ? `Next: ${escapeHtml(item.next_assignment_title)} · ${formatDate(item.next_assignment_due)}`
      : item.total_assessments ? 'All recorded assessments are complete' : 'Add an assignment to define progress';
    return `<article class="course-progress-item">
      <div class="course-progress-head"><span class="course-code">${escapeHtml(item.course_code)}</span><strong>${percent}%</strong></div>
      <h3>${escapeHtml(item.course_title)}</h3><p>${assessmentText}</p>
      <div class="course-progress-bar" role="progressbar" aria-label="${escapeHtml(item.course_code)} assessment progress" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${percent}"><i style="width:${percent}%"></i></div>
      <div class="course-progress-facts"><span><b>${completedWeight}%</b> assessment weight</span><span><b>${item.focus_minutes || 0}</b> focused minutes</span><span><b>${item.completed_study_sessions || 0}</b> study sessions</span></div>
      ${milestone}<div class="course-progress-next">${next}</div>
    </article>`;
  }).join('');
}

function outcomeLikelihood(prediction) {
  if (!prediction) return { pass: 0, notPass: 0, primary: 0, text: 'Awaiting assessment' };
  const pass = Math.max(0, Math.min(100, Math.round(Number(prediction.success_probability) || 0)));
  const notPass = 100 - pass;
  const passing = prediction.predicted_outcome === 'successful';
  return {
    pass,
    notPass,
    primary: passing ? pass : notPass,
    text: passing
      ? `${pass}% chance of passing · ${notPass}% chance of not passing`
      : `${notPass}% chance of not passing · ${pass}% chance of passing`,
  };
}

function setPredictionElements(prefix, prediction) {
  const outcome = prediction?.predicted_outcome;
  $(`#${prefix}Outcome`).textContent = outcome ? (outcome === 'successful' ? 'Likely to pass' : 'At risk') : '—';
  const courseLabel = $(`#${prefix}CourseLabel`);
  if (courseLabel) courseLabel.textContent = prediction?.course_code
    ? `${prediction.course_code} · ${prediction.course_title}`
    : prediction ? 'Legacy general assessment' : 'Select a course to assess';
  const likelihood = outcomeLikelihood(prediction);
  $(`#${prefix}ConfidenceBar`).style.width = `${likelihood.primary}%`;
  $(`#${prefix}ConfidenceText`).textContent = likelihood.text;
  const badge = $(`#${prefix}RiskBadge`);
  badge.textContent = prediction ? `${prediction.risk_level} risk` : 'OULAD · RF';
  badge.className = `metric-trend light${prediction ? ` risk-${prediction.risk_level}` : ''}`;
}

function renderPrediction(prediction) {
  const map = {
    outcome: 'outcome', confidenceBar: 'confidenceBar', confidenceText: 'confidenceText', riskBadge: 'riskBadge',
  };
  const outcome = prediction?.predicted_outcome;
  $(`#${map.outcome}`).textContent = outcome ? (outcome === 'successful' ? 'Likely to pass' : 'At risk') : '—';
  $('#predictionCourseLabel').textContent = prediction?.course_code
    ? `${prediction.course_code} · ${prediction.course_title}`
    : prediction ? 'Legacy general assessment' : 'Select a course to assess';
  const likelihood = outcomeLikelihood(prediction);
  $(`#${map.confidenceBar}`).style.width = `${likelihood.primary}%`;
  $(`#${map.confidenceText}`).textContent = likelihood.text;
  const badge = $(`#${map.riskBadge}`);
  badge.textContent = prediction ? `${prediction.risk_level} risk` : 'OULAD · RF';
  badge.className = `metric-trend light${prediction ? ` risk-${prediction.risk_level}` : ''}`;
  setPredictionElements('performance', prediction);
}

function renderOverviewSchedule() {
  const pending = schedules.filter(item => item.status === 'pending').sort(scheduleSort).slice(0, 5);
  if (!pending.length) {
    $('#schedule').innerHTML = emptyPanel('calendar', 'No upcoming sessions.<br>Add a course and assignment to build your plan.');
    return;
  }
  $('#schedule').innerHTML = pending.map((item, index) => {
    const date = parseDateOnly(item.study_date);
    return `<article class="study-row" style="animation-delay:${Math.min(index * 45, 220)}ms">
      <div class="date-chip">${date.toLocaleDateString(undefined, { weekday: 'short' })}<b>${date.getDate()}</b></div>
      <div><div class="topic">${escapeHtml(item.topic)}</div><div class="meta"><span>${formatTime(item.start_time)}</span><span>${item.duration} min focus</span><span>${courseCode(item.course_id)}</span></div></div>
      <button class="done-button" data-start-focus="${item.id}"><svg><use href="#i-clock"/></svg>Focus</button>
    </article>`;
  }).join('');
}

function renderPredictionCourseOptions() {
  const predictionCourse = $('#predictionCourse');
  if (!predictionCourse) return;
  const selected = predictionCourse.value;
  predictionCourse.innerHTML = '<option value="">Select a registered course</option>' + courses.map(item => `<option value="${item.id}">${escapeHtml(item.course_code)} — ${escapeHtml(item.course_title)}</option>`).join('');
  if (courses.some(item => String(item.id) === selected)) predictionCourse.value = selected;
}

function renderCourses() {
  $('#coursePageCount').textContent = `${courses.length} course${courses.length === 1 ? '' : 's'}`;
  const options = '<option value="">Select course</option>' + courses.map(item => `<option value="${item.id}">${escapeHtml(item.course_code)} — ${escapeHtml(item.course_title)}</option>`).join('');
  $('#courseSelectPage').innerHTML = options;
  if ($('#courseSelect')) $('#courseSelect').innerHTML = options;
  renderPredictionCourseOptions();
  if (!courses.length) {
    $('#courseGrid').innerHTML = emptyPanel('book', 'No courses yet.<br>Add your first course using the form.');
    return;
  }
  $('#courseGrid').innerHTML = courses.map(course => {
    const pending = assignments.filter(item => item.course_id === course.id && item.status === 'pending').length;
    const tracked = (dashboardData.course_progress || []).find(item => item.course_id === course.id);
    const progress = Math.max(0, Math.min(100, Number(tracked?.assessment_progress_percent) || 0));
    const difficulty = Array.from({ length: 5 }, (_, index) => `<i class="${index < Number(course.difficulty || 3) ? 'active' : ''}"></i>`).join('');
    return `<article class="course-item">
      <span class="course-code">${escapeHtml(course.course_code)}</span>
      <h3>${escapeHtml(course.course_title)}</h3>
      <div class="course-meta"><span>${course.credit_unit} units</span><span>${escapeHtml(course.semester)}</span>${course.examination_date ? `<span>Exam ${formatDate(course.examination_date)}</span>` : ''}</div>
      <div class="difficulty-dots" title="Difficulty ${course.difficulty || 3} of 5">${difficulty}</div>
      <div class="course-card-progress"><span>Assessment progress <b>${progress}%</b></span><div><i style="width:${progress}%"></i></div></div>
      <div class="course-foot"><span>${pending} active assignment${pending === 1 ? '' : 's'}</span><button class="text-button danger" data-delete-course="${course.id}">Remove</button></div>
    </article>`;
  }).join('');
}

function renderAssignments() {
  $$('.filter-tabs [data-assignment-filter]').forEach(button => button.classList.toggle('active', button.dataset.assignmentFilter === assignmentFilter));
  let items = [...assignments].sort((a, b) => new Date(a.due_date) - new Date(b.due_date));
  if (assignmentFilter !== 'all') items = items.filter(item => item.status === assignmentFilter);
  if (!items.length) {
    $('#assignmentList').innerHTML = emptyPanel('task', assignmentFilter === 'completed' ? 'No completed assignments yet.' : 'No active assignments.<br>Add a deadline using the form.');
    return;
  }
  $('#assignmentList').innerHTML = items.map(item => {
    const due = new Date(item.due_date);
    const overdue = item.status === 'pending' && due < new Date();
    return `<article class="assignment-item ${item.status === 'completed' ? 'completed' : ''}">
      <div class="assignment-date">${due.toLocaleDateString(undefined, { month: 'short' })}<strong>${due.getDate()}</strong></div>
      <div><h3>${escapeHtml(item.title)}</h3><p class="${overdue ? 'overdue' : ''}">${courseCode(item.course_id)} · ${item.weight || 0}% · ${overdue ? 'Overdue' : item.status === 'completed' ? 'Completed' : dueText(due)}</p></div>
      <div class="assignment-actions"><button class="small-action ${item.status === 'pending' ? 'complete' : ''}" data-assignment-status="${item.id},${item.status === 'pending' ? 'completed' : 'pending'}">${item.status === 'pending' ? '✓ Complete' : 'Reopen'}</button></div>
    </article>`;
  }).join('');
}

function renderWeek() {
  const today = new Date();
  const monday = new Date(today);
  monday.setDate(today.getDate() - ((today.getDay() + 6) % 7));
  $('#weekStrip').innerHTML = Array.from({ length: 7 }, (_, index) => {
    const day = new Date(monday);
    day.setDate(monday.getDate() + index);
    const isToday = dateKey(day) === dateKey(today);
    return `<div class="week-day${isToday ? ' today' : ''}"><span>${day.toLocaleDateString(undefined, { weekday: 'short' })}</span><strong>${day.getDate()}</strong></div>`;
  }).join('');
}

function calendarEvents() {
  const events = [];
  const includeCompleted = $('#showCompletedSessions')?.checked || false;
  schedules.filter(item => includeCompleted || item.status !== 'completed').forEach(item => events.push({ type: 'study', date: item.study_date, title: item.topic, item, completed: item.status === 'completed' }));
  assignments.filter(item => includeCompleted || item.status !== 'completed').forEach(item => events.push({ type: 'deadline', date: item.due_date.slice(0, 10), title: item.title, item, completed: item.status === 'completed' }));
  courses.filter(item => item.examination_date).forEach(item => events.push({ type: 'exam', date: item.examination_date.slice(0, 10), title: `${item.course_code} examination`, item, completed: false }));
  return events;
}

function renderCalendar() {
  $('#calendarTitle').textContent = calendarDate.toLocaleDateString(undefined, { month: 'long', year: 'numeric' });
  const first = new Date(calendarDate.getFullYear(), calendarDate.getMonth(), 1);
  const offset = (first.getDay() + 6) % 7;
  const gridStart = new Date(first);
  gridStart.setDate(first.getDate() - offset);
  const events = calendarEvents();
  $('#calendarGrid').innerHTML = Array.from({ length: 42 }, (_, index) => {
    const day = new Date(gridStart);
    day.setDate(gridStart.getDate() + index);
    const key = dateKey(day);
    const dayEvents = events.filter(event => event.date === key);
    const eventMarkup = dayEvents.slice(0, 3).map(event => `<div class="calendar-event ${event.type}${event.completed ? ' completed' : ''}">${escapeHtml(event.title)}</div>`).join('');
    return `<button class="calendar-day${day.getMonth() !== calendarDate.getMonth() ? ' outside' : ''}${key === dateKey(new Date()) ? ' today' : ''}${key === selectedDate ? ' selected' : ''}${dayEvents.length ? ' has-events' : ''}" data-calendar-date="${key}"><span class="calendar-number">${day.getDate()}</span><div class="calendar-events">${eventMarkup}${dayEvents.length > 3 ? `<span class="calendar-more">+${dayEvents.length - 3} more</span>` : ''}</div></button>`;
  }).join('');
}

function renderAgenda() {
  const date = parseDateOnly(selectedDate);
  $('#agendaTitle').textContent = date.toLocaleDateString(undefined, { weekday: 'long', day: 'numeric', month: 'long' });
  const events = calendarEvents().filter(event => event.date === selectedDate);
  if (!events.length) {
    $('#dayAgenda').innerHTML = emptyPanel('calendar', 'Nothing planned for this day.');
    return;
  }
  $('#dayAgenda').innerHTML = events.map(event => {
    let detail = '';
    let actions = '';
    if (event.type === 'study') {
      detail = `${formatTime(event.item.start_time)} · ${event.item.duration} minutes · ${courseCode(event.item.course_id)}${event.completed ? ' · Completed' : ''}`;
      if (!event.completed) actions = `<button class="small-action" data-start-focus="${event.item.id}">Start focus</button><button class="small-action complete" data-complete-schedule="${event.item.id}">Complete</button>`;
    } else if (event.type === 'deadline') {
      detail = `${courseCode(event.item.course_id)} · Assignment deadline${event.completed ? ' · Completed' : ''}`;
      if (!event.completed) actions = `<button class="small-action complete" data-assignment-status="${event.item.id},completed">Complete assignment</button>`;
    } else detail = 'Course examination';
    return `<article class="agenda-row"><span class="agenda-color ${event.type}"></span><div><h3>${escapeHtml(event.title)}</h3><p>${escapeHtml(detail)}</p></div><div class="agenda-actions">${actions}</div></article>`;
  }).join('');
}

function renderFocusContext() {
  const courseSelect = $('#focusCourse');
  const assignmentSelect = $('#focusAssignment');
  const selectedCourse = String(timerState.course_id || '');
  const selectedAssignment = String(timerState.assignment_id || '');
  courseSelect.innerHTML = '<option value="">General study</option>' + courses.map(item => `<option value="${item.id}">${escapeHtml(item.course_code)} — ${escapeHtml(item.course_title)}</option>`).join('');
  courseSelect.value = selectedCourse;
  const relevant = assignments.filter(item => item.status === 'pending' && (!selectedCourse || String(item.course_id) === selectedCourse));
  assignmentSelect.innerHTML = '<option value="">No assignment</option>' + relevant.map(item => `<option value="${item.id}">${escapeHtml(item.title)}</option>`).join('');
  assignmentSelect.value = relevant.some(item => String(item.id) === selectedAssignment) ? selectedAssignment : '';
  if (!assignmentSelect.value) timerState.assignment_id = null;
  const linked = schedules.find(item => item.id === Number(timerState.schedule_id));
  $('#timerLinkNotice').hidden = !linked;
  if (linked) $('#timerLinkNotice').textContent = `Linked plan: ${linked.topic} · ${linked.duration} minutes required. Completed Pomodoros accumulate toward this session.`;
}

function renderFocusStats() {
  $('#focusToday').textContent = dashboardData.focus_minutes_today || 0;
  $('#focusWeek').textContent = dashboardData.focus_minutes_week || 0;
  if (!focusSessions.length) {
    $('#focusHistory').innerHTML = emptyPanel('clock', 'Your completed Pomodoros will appear here.');
    return;
  }
  $('#focusHistory').innerHTML = focusSessions.slice(0, 8).map(item => {
    const course = courses.find(course => course.id === item.course_id);
    const assignment = assignments.find(task => task.id === item.assignment_id);
    return `<article class="focus-history-row"><span class="focus-history-icon"><svg><use href="#i-clock"/></svg></span><div><strong>${escapeHtml(assignment?.title || course?.course_title || 'General study')}</strong><small>${formatDateTime(item.completed_at)}${course ? ` · ${course.course_code}` : ''}</small></div><b>${item.duration_minutes} min</b></article>`;
  }).join('');
}

function renderPerformance() {
  const latest = predictions.find(item => item.course_id) || dashboardData.predicted_performance;
  setPredictionElements('performance', latest);
  const linkedRecommendation = latest ? recommendations.find(item => item.prediction_id === latest.id) : null;
  $('#performanceRecommendation').textContent = linkedRecommendation?.text || 'Select a registered course and run an assessment to receive a personalized recommendation.';
  if (!predictions.length) {
    $('#predictionHistory').innerHTML = emptyPanel('chart', 'No assessments yet. Run your first OULAD early-risk check.');
    return;
  }
  $('#predictionHistory').innerHTML = predictions.slice(0, 9).map(item => {
    const course = item.course_code ? `${item.course_code} · ${item.course_title}` : 'Legacy general assessment';
    const likelihood = outcomeLikelihood(item);
    return `<article class="prediction-history-item"><span class="prediction-course-code">${escapeHtml(course)}</span><span>${formatDateTime(item.prediction_date)}</span><strong>${item.predicted_outcome === 'successful' ? 'Likely to pass' : 'At risk of not passing'}</strong><small>${likelihood.text}</small><span class="status-pill ${item.risk_level}">${item.risk_level} risk</span></article>`;
  }).join('');
}

function navigate(page, updateHash = true) {
  if (!validPage(page)) page = 'overview';
  $$('.app-page').forEach(section => section.classList.toggle('active', section.dataset.pageContent === page));
  $$('[data-page]').forEach(button => button.classList.toggle('active', button.dataset.page === page));
  const contexts = { overview: 'Your planner is up to date', courses: 'Course catalogue', assignments: 'Deadline centre', planner: 'Live academic calendar', focus: 'Distraction-free focus room', performance: 'Academic early-warning analysis' };
  $('#pageContext').textContent = contexts[page];
  $('#app').classList.remove('menu-open');
  if (updateHash) history.replaceState(null, '', `#/${page}`);
  window.scrollTo({ top: 0, behavior: 'smooth' });
  if (page === 'planner') { renderCalendar(); renderAgenda(); }
}

function validPage(page) { return ['overview', 'courses', 'assignments', 'planner', 'focus', 'performance'].includes(page); }
$$('[data-page]').forEach(button => button.addEventListener('click', () => navigate(button.dataset.page)));

function formJSON(form) {
  const data = Object.fromEntries(new FormData(form));
  Object.keys(data).forEach(key => { if (data[key] === '') delete data[key]; });
  return data;
}

function wireForm(selector, path, message, destination) {
  $(selector).addEventListener('submit', async event => {
    event.preventDefault();
    const form = event.currentTarget;
    if (!form.reportValidity()) return;
    const button = $('button[type="submit"]', form);
    button.disabled = true;
    try {
      await call(path, { method: 'POST', body: JSON.stringify(formJSON(form)) });
      form.reset();
      await refreshData();
      navigate(destination);
      toast(message);
    } catch (error) { toast(error.message); }
    finally { button.disabled = false; }
  });
}

wireForm('#courseFormPage', '/courses', 'Course saved and added to your catalogue.', 'courses');
wireForm('#taskFormPage', '/assignments', 'Assignment saved and added to your deadline centre.', 'assignments');

async function regenerate(button) {
  button.disabled = true;
  button.classList.add('spinning');
  try {
    await call('/schedules', { method: 'POST', body: JSON.stringify({ days: 14 }) });
    await refreshData();
    toast('Your next fourteen days have been rebalanced without duplicating completed sessions.');
  } catch (error) { toast(error.message); }
  finally { button.disabled = false; button.classList.remove('spinning'); }
}
$('#regenerate').addEventListener('click', event => regenerate(event.currentTarget));
$('#regeneratePlanner').addEventListener('click', event => regenerate(event.currentTarget));

$$('[data-assignment-filter]').forEach(button => button.addEventListener('click', () => {
  assignmentFilter = button.dataset.assignmentFilter;
  renderAssignments();
}));

$('#calendarPrev').addEventListener('click', () => { calendarDate = new Date(calendarDate.getFullYear(), calendarDate.getMonth() - 1, 1); renderCalendar(); });
$('#calendarNext').addEventListener('click', () => { calendarDate = new Date(calendarDate.getFullYear(), calendarDate.getMonth() + 1, 1); renderCalendar(); });
$('#calendarToday').addEventListener('click', () => { const now = new Date(); calendarDate = new Date(now.getFullYear(), now.getMonth(), 1); selectedDate = dateKey(now); renderCalendar(); renderAgenda(); });
$('#showCompletedSessions').addEventListener('change', () => { renderCalendar(); renderAgenda(); });

document.addEventListener('click', async event => {
  const calendarButton = event.target.closest('[data-calendar-date]');
  if (calendarButton) { selectedDate = calendarButton.dataset.calendarDate; renderCalendar(); renderAgenda(); return; }
  const startButton = event.target.closest('[data-start-focus]');
  if (startButton) { startScheduleFocus(Number(startButton.dataset.startFocus)); return; }
  const completeButton = event.target.closest('[data-complete-schedule]');
  if (completeButton) { await completeSchedule(Number(completeButton.dataset.completeSchedule)); return; }
  const statusButton = event.target.closest('[data-assignment-status]');
  if (statusButton) {
    const [id, status] = statusButton.dataset.assignmentStatus.split(',');
    await setAssignmentStatus(Number(id), status);
    return;
  }
  const deleteButton = event.target.closest('[data-delete-course]');
  if (deleteButton) await deleteCourse(Number(deleteButton.dataset.deleteCourse));
});

async function completeSchedule(id) {
  try {
    await call(`/schedules/${id}`, { method: 'PATCH', body: JSON.stringify({ status: 'completed' }) });
    await refreshData();
    toast('Study session completed and moved to history.');
  } catch (error) { toast(error.message); }
}

async function setAssignmentStatus(id, status) {
  try {
    await call(`/assignments/${id}`, { method: 'PATCH', body: JSON.stringify({ status }) });
    await refreshData();
    toast(status === 'completed' ? 'Assignment completed. Its future study sessions were cleared.' : 'Assignment reopened and returned to your active plan.');
  } catch (error) { toast(error.message); }
}

async function deleteCourse(id) {
  const course = courses.find(item => item.id === id);
  if (!course || !confirm(`Remove ${course.course_code} and its assignments from StudySmart?`)) return;
  try {
    await call(`/courses/${id}`, { method: 'DELETE' });
    await refreshData();
    toast('Course removed.');
  } catch (error) { toast(error.message); }
}

// Pomodoro timer. A deadline timestamp keeps the timer accurate across refreshes.
const defaultTimer = { mode: 'focus', focusMinutes: 25, breakMinutes: 5, remaining: 1500, running: false, deadline: null, startedAt: null, course_id: null, assignment_id: null, schedule_id: null, completedCycles: 0 };
let timerState = loadTimer();
function loadTimer() {
  try {
    const stored = JSON.parse(localStorage.getItem('study_timer_state'));
    return stored && ['focus', 'break'].includes(stored.mode) ? { ...defaultTimer, ...stored } : { ...defaultTimer };
  } catch (_) { return { ...defaultTimer }; }
}
function saveTimer() { localStorage.setItem('study_timer_state', JSON.stringify(timerState)); }
function intervalSeconds() { return (timerState.mode === 'focus' ? timerState.focusMinutes : timerState.breakMinutes) * 60; }

function updateTimerUI() {
  const minutes = Math.floor(timerState.remaining / 60);
  const seconds = timerState.remaining % 60;
  $('#timerDisplay').textContent = `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
  $('#timerMode').textContent = timerState.mode === 'focus' ? 'FOCUS SESSION' : 'REST & RESET';
  $('#timerCycleText').textContent = timerState.running ? (timerState.mode === 'focus' ? 'Deep work in progress' : 'Break in progress') : `${timerState.completedCycles} focus cycle${timerState.completedCycles === 1 ? '' : 's'} completed`;
  $('#timerStart').textContent = timerState.running ? 'Pause' : timerState.remaining < intervalSeconds() ? 'Resume' : timerState.mode === 'focus' ? 'Start focus' : 'Start break';
  const progress = 1 - timerState.remaining / Math.max(intervalSeconds(), 1);
  $('#timerRing').style.setProperty('--timer-angle', `${Math.max(0, Math.min(1, progress)) * 360}deg`);
  document.title = timerState.running ? `${$('#timerDisplay').textContent} · ${timerState.mode === 'focus' ? 'Focus' : 'Break'} — StudySmart` : 'StudySmart — Intelligent Study Planner';
}

async function timerTick() {
  if (!timerState.running || !timerState.deadline) return;
  timerState.remaining = Math.max(0, Math.ceil((timerState.deadline - Date.now()) / 1000));
  updateTimerUI();
  if (timerState.remaining === 0) await finishTimer();
}

async function finishTimer() {
  const completedMode = timerState.mode;
  timerState.running = false;
  timerState.deadline = null;
  if (completedMode === 'focus') {
    try {
      const result = await call('/focus-sessions', { method: 'POST', body: JSON.stringify({
        duration_minutes: timerState.focusMinutes,
        started_at: timerState.startedAt || new Date(Date.now() - timerState.focusMinutes * 60000).toISOString(),
        completed_at: new Date().toISOString(), course_id: timerState.course_id,
        assignment_id: timerState.assignment_id, schedule_id: timerState.schedule_id,
        mode: 'pomodoro',
      }) });
      timerState.completedCycles += 1;
      if (result.schedule_completed) {
        timerState.schedule_id = null;
        toast('Pomodoro complete — the linked timetable session is now complete.');
      } else toast('Pomodoro complete — focused minutes recorded.');
      await refreshData();
    } catch (error) { toast(`Timer finished, but the session could not be saved: ${error.message}`); }
    timerState.mode = 'break';
    timerState.remaining = timerState.breakMinutes * 60;
    timerState.startedAt = null;
  } else {
    timerState.mode = 'focus';
    timerState.remaining = timerState.focusMinutes * 60;
    toast('Break complete. Ready for another focus cycle.');
  }
  saveTimer();
  renderFocusContext();
  updateTimerUI();
  finishAlert(completedMode === 'focus' ? 'Focus session complete' : 'Break complete');
}

function finishAlert(message) {
  try {
    audioContext ||= new (window.AudioContext || window.webkitAudioContext)();
    const oscillator = audioContext.createOscillator();
    const gain = audioContext.createGain();
    oscillator.connect(gain); gain.connect(audioContext.destination);
    oscillator.frequency.value = 660; gain.gain.value = 0.08;
    oscillator.start(); oscillator.stop(audioContext.currentTime + 0.18);
  } catch (_) { /* Sound is optional. */ }
  if ('Notification' in window && Notification.permission === 'granted') new Notification('StudySmart', { body: message });
}

$('#timerStart').addEventListener('click', () => {
  audioContext ||= 'AudioContext' in window ? new AudioContext() : null;
  if (timerState.running) {
    timerState.remaining = Math.max(0, Math.ceil((timerState.deadline - Date.now()) / 1000));
    timerState.running = false; timerState.deadline = null;
  } else {
    timerState.running = true;
    timerState.deadline = Date.now() + timerState.remaining * 1000;
    if (timerState.mode === 'focus' && !timerState.startedAt) timerState.startedAt = new Date().toISOString();
  }
  saveTimer(); updateTimerUI();
});

$('#timerReset').addEventListener('click', () => {
  timerState.running = false; timerState.deadline = null; timerState.startedAt = null; timerState.remaining = intervalSeconds();
  saveTimer(); updateTimerUI();
});

$('#timerSkip').addEventListener('click', () => {
  timerState.running = false; timerState.deadline = null; timerState.startedAt = null;
  timerState.mode = timerState.mode === 'focus' ? 'break' : 'focus';
  timerState.remaining = intervalSeconds();
  saveTimer(); updateTimerUI();
  toast(timerState.mode === 'focus' ? 'Break skipped. Focus timer is ready.' : 'Focus interval skipped and was not recorded.');
});

$$('[data-preset]').forEach(button => button.addEventListener('click', () => {
  $$('.timer-presets button').forEach(item => item.classList.toggle('active', item === button));
  const custom = button.dataset.preset === 'custom';
  $('#customTimerSettings').hidden = !custom;
  if (!custom) {
    const [focus, rest] = button.dataset.preset.split(',').map(Number);
    applyTimerDurations(focus, rest);
  }
}));

$('#applyCustomTimer').addEventListener('click', () => {
  const focus = Number($('#customFocusMinutes').value);
  const rest = Number($('#customBreakMinutes').value);
  if (!Number.isInteger(focus) || focus < 1 || focus > 180 || !Number.isInteger(rest) || rest < 1 || rest > 60) return toast('Choose 1–180 focus minutes and 1–60 break minutes.');
  applyTimerDurations(focus, rest);
  toast('Custom timer applied.');
});

function applyTimerDurations(focus, rest) {
  timerState.focusMinutes = focus; timerState.breakMinutes = rest; timerState.running = false; timerState.deadline = null; timerState.startedAt = null; timerState.remaining = intervalSeconds();
  saveTimer(); updateTimerUI();
}

$('#focusCourse').addEventListener('change', event => { timerState.course_id = Number(event.target.value) || null; timerState.assignment_id = null; timerState.schedule_id = null; saveTimer(); renderFocusContext(); });
$('#focusAssignment').addEventListener('change', event => { timerState.assignment_id = Number(event.target.value) || null; timerState.schedule_id = null; saveTimer(); });

function startScheduleFocus(id) {
  const item = schedules.find(schedule => schedule.id === id);
  if (!item) return;
  timerState.mode = 'focus'; timerState.running = false; timerState.deadline = null; timerState.startedAt = null;
  timerState.focusMinutes = Math.min(25, Math.max(1, item.duration));
  timerState.remaining = timerState.focusMinutes * 60;
  timerState.course_id = item.course_id; timerState.assignment_id = item.assignment_id; timerState.schedule_id = item.id;
  saveTimer(); renderFocusContext(); updateTimerUI(); navigate('focus');
}

$('#enableAlerts').addEventListener('click', async () => {
  if (!('Notification' in window)) return toast('This browser does not support finish notifications.');
  const permission = await Notification.requestPermission();
  toast(permission === 'granted' ? 'Finish alerts enabled.' : 'Notifications were not enabled. The timer will still sound.');
});

setInterval(timerTick, 250);
if (timerState.running && timerState.deadline && timerState.deadline <= Date.now()) setTimeout(finishTimer, 0);
updateTimerUI();

function closePredictionDialog() {
  const dialog = $('#predictionDialog');
  if (dialog.open) dialog.close();
}

function openPrediction(event) {
  if (event) event.preventDefault();
  if (!courses.length) {
    toast('Add at least one course before running a course prediction.');
    navigate('courses');
    return;
  }
  renderPredictionCourseOptions();
  const select = $('#predictionCourse');
  const latestCoursePrediction = predictions.find(item => item.course_id);
  if (!select.value) select.value = String(latestCoursePrediction?.course_id || courses[0].id);
  const dialog = $('#predictionDialog');
  if (!dialog.open) dialog.showModal();
  dialog.scrollTop = 0;
}
window.openPrediction = openPrediction;
$('#closePrediction').addEventListener('click', closePredictionDialog);
$('#cancelPrediction').addEventListener('click', closePredictionDialog);
$('#predictionDialog').addEventListener('click', event => { if (event.target === event.currentTarget) event.currentTarget.close(); });
$('#predictionForm').addEventListener('submit', async event => {
  event.preventDefault();
  const form = event.currentTarget;
  if (!form.reportValidity()) return;
  const payload = formJSON(form);
  if (!payload.course_id) {
    const select = $('#predictionCourse');
    $('#predictionDialog').scrollTop = 0;
    select.focus();
    toast('Select a registered course before running the assessment.');
    return;
  }
  const button = $('button[type="submit"]', form);
  const label = $('span', button);
  const original = label.textContent;
  button.disabled = true; label.textContent = 'Analysing OULAD pattern…';
  try {
    const result = await call('/predictions', { method: 'POST', body: JSON.stringify(payload) });
    dashboardData.predicted_performance = result.prediction;
    predictions = [result.prediction, ...predictions.filter(item => item.id !== result.prediction.id)];
    recommendations = [result.recommendation, ...recommendations.filter(item => item.id !== result.recommendation.id)];
    $('#recommendationText').textContent = result.recommendation.text;
    $('#recommendation').hidden = false;
    renderPrediction(result.prediction);
    renderPerformance();
    closePredictionDialog();
    navigate('overview');
    toast(`${result.prediction.course_code} course outlook updated.`);
    await refreshData();
  } catch (error) { toast(error.message); }
  finally { button.disabled = false; label.textContent = original; }
});

$('#dismissRecommendation').addEventListener('click', () => { $('#recommendation').hidden = true; });
$('#notificationButton').addEventListener('click', event => {
  event.stopPropagation();
  setNotificationPanel($('#notificationPanel').hidden);
});
$('#notificationPanel').addEventListener('click', async event => {
  event.stopPropagation();
  const item = event.target.closest('[data-notification-id]');
  if (item) await markNotificationRead(Number(item.dataset.notificationId));
});
$('#markAllNotifications').addEventListener('click', async event => {
  event.stopPropagation();
  const unread = notifications.filter(item => item.status === 'unread');
  if (!unread.length) return;
  event.currentTarget.disabled = true;
  try {
    const updated = await Promise.all(unread.map(item => call(`/notifications/${item.id}`, { method: 'PATCH', body: JSON.stringify({ status: 'read' }) })));
    const byId = new Map(updated.map(item => [item.id, item]));
    notifications = notifications.map(item => byId.get(item.id) || item);
    renderNotifications();
    toast('All notifications marked as read.');
  } catch (error) { toast(error.message); }
  finally { event.currentTarget.disabled = false; }
});
$('#menuButton').addEventListener('click', () => $('#app').classList.toggle('menu-open'));
document.addEventListener('click', event => {
  if (!event.target.closest('.notification-wrap')) setNotificationPanel(false);
  if (window.innerWidth <= 840 && $('#app').classList.contains('menu-open') && !event.target.closest('.sidebar') && !event.target.closest('#menuButton')) $('#app').classList.remove('menu-open');
});
document.addEventListener('keydown', event => { if (event.key === 'Escape') setNotificationPanel(false); });

function logout() {
  token = null;
  localStorage.removeItem('study_token');
  $('#app').hidden = true;
  $('#app').classList.remove('menu-open');
  setNotificationPanel(false);
  $('#auth').hidden = false;
}
$('#logout').addEventListener('click', logout);

function courseCode(id) { return courses.find(item => item.id === id)?.course_code || 'General study'; }
function scheduleSort(a, b) { return `${a.study_date}T${a.start_time}`.localeCompare(`${b.study_date}T${b.start_time}`); }
function parseDateOnly(value) { const [year, month, day] = String(value).slice(0, 10).split('-').map(Number); return new Date(year, month - 1, day); }
function dateKey(date) { return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`; }
function formatTime(value) { return String(value || '').slice(0, 5); }
function formatDate(value) { return new Date(value).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' }); }
function formatDateTime(value) { return new Date(value).toLocaleString(undefined, { day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit' }); }
function dueText(date) { const days = Math.ceil((date - new Date()) / 86400000); return days <= 0 ? 'Due today' : `Due in ${days} day${days === 1 ? '' : 's'}`; }
function escapeHtml(value) { const div = document.createElement('div'); div.textContent = String(value ?? ''); return div.innerHTML; }
function emptyPanel(icon, message) { return `<div class="empty-panel"><div><span><svg><use href="#i-${icon}"/></svg></span><p>${message}</p></div></div>`; }

if (location.protocol === 'file:') {
  $('#launchWarning').hidden = false;
  localStorage.removeItem('study_token');
  token = null;
} else if (token) showApp({ silent: true });
