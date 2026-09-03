import 'dart:async';

import 'package:flutter/material.dart';

import 'api.dart';

const lime = Color(0xffc8ff45);
const ink = Color(0xff071a13);

void main() => runApp(const StudyPlannerApp());

class StudyPlannerApp extends StatelessWidget {
  const StudyPlannerApp({super.key});

  @override
  Widget build(BuildContext context) => MaterialApp(
        debugShowCheckedModeBanner: false,
        title: 'StudySmart',
        theme: ThemeData(
          colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xff23664a)),
          scaffoldBackgroundColor: const Color(0xfff5f7f1),
          useMaterial3: true,
          inputDecorationTheme: const InputDecorationTheme(border: OutlineInputBorder()),
        ),
        home: LoginScreen(api: Api()),
      );
}

class BrandMark extends StatelessWidget {
  const BrandMark({super.key, this.size = 46});
  final double size;
  @override
  Widget build(BuildContext context) => Transform.rotate(
        angle: -.08,
        child: Container(
          width: size,
          height: size,
          decoration: BoxDecoration(color: lime, borderRadius: BorderRadius.circular(size * .3)),
          child: Icon(Icons.drag_handle_rounded, color: ink, size: size * .65),
        ),
      );
}

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key, required this.api});
  final Api api;
  @override
  State<LoginScreen> createState() => _LoginState();
}

class _LoginState extends State<LoginScreen> {
  final email = TextEditingController();
  final password = TextEditingController();
  final name = TextEditingController();
  final programme = TextEditingController();
  final level = TextEditingController();
  bool createAccount = false;
  bool loading = false;
  String? error;

  Future<void> submit() async {
    setState(() { loading = true; error = null; });
    try {
      if (createAccount) {
        await widget.api.register({
          'full_name': name.text.trim(),
          'email': email.text.trim(),
          'password': password.text,
          'programme': programme.text.trim(),
          'level': level.text.trim(),
        });
      } else {
        await widget.api.login(email.text, password.text);
      }
      if (mounted) Navigator.pushReplacement(context, MaterialPageRoute(builder: (_) => HomeShell(api: widget.api)));
    } catch (exception) {
      if (mounted) setState(() => error = exception.toString().replaceFirst('Exception: ', ''));
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        body: SafeArea(
          child: Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(24),
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 430),
                child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                  const Row(children: [BrandMark(), SizedBox(width: 14), Text('StudySmart', style: TextStyle(fontSize: 30, fontWeight: FontWeight.w800))]),
                  const SizedBox(height: 10),
                  Text(createAccount ? 'Create your academic workspace' : 'Welcome back. Continue your plan.'),
                  const SizedBox(height: 28),
                  if (createAccount) ...[
                    TextField(controller: name, decoration: const InputDecoration(labelText: 'Full name')),
                    const SizedBox(height: 12),
                    TextField(controller: programme, decoration: const InputDecoration(labelText: 'Programme')),
                    const SizedBox(height: 12),
                    TextField(controller: level, decoration: const InputDecoration(labelText: 'Level')),
                    const SizedBox(height: 12),
                  ],
                  TextField(controller: email, keyboardType: TextInputType.emailAddress, decoration: const InputDecoration(labelText: 'University email')),
                  const SizedBox(height: 12),
                  TextField(controller: password, obscureText: true, decoration: const InputDecoration(labelText: 'Password')),
                  if (error != null) Padding(padding: const EdgeInsets.only(top: 10), child: Text(error!, style: const TextStyle(color: Colors.red))),
                  const SizedBox(height: 18),
                  FilledButton(style: FilledButton.styleFrom(backgroundColor: ink, foregroundColor: Colors.white, padding: const EdgeInsets.all(18)), onPressed: loading ? null : submit, child: Text(loading ? 'Please wait…' : createAccount ? 'Create account' : 'Sign in')),
                  TextButton(onPressed: () => setState(() { createAccount = !createAccount; error = null; }), child: Text(createAccount ? 'Already registered? Sign in' : 'New student? Create an account')),
                ]),
              ),
            ),
          ),
        ),
      );
}

class HomeShell extends StatefulWidget {
  const HomeShell({super.key, required this.api});
  final Api api;
  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  int page = 0;
  bool loading = true;
  String? error;
  Map<String, dynamic> dashboard = {};
  List<dynamic> courses = [], assignments = [], schedules = [], predictions = [], notifications = [];
  Timer? timer;
  int secondsLeft = 25 * 60;
  bool timerRunning = false;
  DateTime? timerStarted;

  static const labels = ['Overview', 'Planner', 'Courses', 'Assignments', 'Focus', 'Performance'];
  static const icons = [Icons.grid_view_rounded, Icons.calendar_month_outlined, Icons.menu_book_outlined, Icons.assignment_turned_in_outlined, Icons.timer_outlined, Icons.insights_outlined];

  @override
  void initState() { super.initState(); load(); }
  @override
  void dispose() { timer?.cancel(); super.dispose(); }

  Future<void> load() async {
    try {
      final result = await Future.wait([
        widget.api.request('/dashboard'), widget.api.request('/courses'),
        widget.api.request('/assignments'), widget.api.request('/schedules'),
        widget.api.request('/predictions'), widget.api.request('/notifications'),
      ]);
      if (mounted) setState(() {
        dashboard = Map<String, dynamic>.from(result[0]); courses = result[1]; assignments = result[2];
        schedules = result[3]; predictions = result[4]; notifications = result[5]; loading = false; error = null;
      });
    } catch (exception) {
      if (mounted) setState(() { error = exception.toString().replaceFirst('Exception: ', ''); loading = false; });
    }
  }

  Future<void> action(Future<dynamic> operation, {String? success}) async {
    try {
      await operation; await load();
      if (mounted && success != null) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(success)));
    } catch (exception) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(exception.toString().replaceFirst('Exception: ', ''))));
    }
  }

  void selectPage(int value) => setState(() => page = value);

  @override
  Widget build(BuildContext context) {
    final wide = MediaQuery.sizeOf(context).width >= 850;
    final unread = notifications.where((n) => n['status'] == 'unread').length;
    final content = loading
        ? const Center(child: CircularProgressIndicator())
        : error != null
            ? Center(child: Column(mainAxisSize: MainAxisSize.min, children: [Text(error!), const SizedBox(height: 12), FilledButton(onPressed: load, child: const Text('Try again'))]))
            : RefreshIndicator(onRefresh: load, child: IndexedStack(index: page, children: [overview(), planner(), coursePage(), assignmentPage(), focusPage(), performance()]));
    return Scaffold(
      appBar: AppBar(
        title: Row(children: [const BrandMark(size: 34), const SizedBox(width: 10), Text(labels[page], style: const TextStyle(fontWeight: FontWeight.w700))]),
        actions: [
          IconButton(onPressed: showNotifications, icon: Badge(isLabelVisible: unread > 0, label: Text('$unread'), child: const Icon(Icons.notifications_none))),
          IconButton(onPressed: () async { await widget.api.logout(); if (mounted) Navigator.pushReplacement(context, MaterialPageRoute(builder: (_) => LoginScreen(api: widget.api))); }, icon: const Icon(Icons.logout)),
        ],
      ),
      body: Row(children: [
        if (wide) NavigationRail(selectedIndex: page, onDestinationSelected: selectPage, labelType: NavigationRailLabelType.all, destinations: List.generate(labels.length, (i) => NavigationRailDestination(icon: Icon(icons[i]), label: Text(labels[i])))),
        Expanded(child: content),
      ]),
      bottomNavigationBar: wide ? null : NavigationBar(height: 70, selectedIndex: page, onDestinationSelected: selectPage, destinations: List.generate(labels.length, (i) => NavigationDestination(icon: Icon(icons[i]), label: i == 3 ? 'Tasks' : labels[i]))),
    );
  }

  Widget scroll(List<Widget> children) => ListView(padding: const EdgeInsets.all(16), children: children);
  Widget heading(String title, String subtitle, {Widget? action}) => Padding(padding: const EdgeInsets.only(bottom: 18), child: Row(children: [Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text(title, style: const TextStyle(fontSize: 30, fontWeight: FontWeight.w800)), const SizedBox(height: 4), Text(subtitle)])), if (action != null) action]));

  Widget overview() {
    final prediction = dashboard['predicted_performance'];
    final progress = dashboard['course_progress'] as List? ?? [];
    return scroll([
      heading('Make today count', 'Your plan, deadlines and academic outlook at a glance.'),
      GridView.count(crossAxisCount: MediaQuery.sizeOf(context).width > 650 ? 4 : 2, shrinkWrap: true, physics: const NeverScrollableScrollPhysics(), mainAxisSpacing: 10, crossAxisSpacing: 10, childAspectRatio: 1.35, children: [
        Metric('Courses', '${dashboard['courses'] ?? 0}', Icons.menu_book_outlined),
        Metric('Pending', '${dashboard['pending_tasks'] ?? 0}', Icons.assignment_outlined),
        Metric('Study progress', '${dashboard['progress_percent'] ?? 0}%', Icons.insights),
        Metric('This week', '${dashboard['focus_minutes_week'] ?? 0} min', Icons.timer_outlined),
      ]),
      if (prediction != null) Padding(padding: const EdgeInsets.only(top: 12), child: InsightCard(prediction: prediction, onTap: () => selectPage(5))),
      const SizedBox(height: 20),
      Text('Course progress', style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.bold)),
      if (progress.isEmpty) const Padding(padding: EdgeInsets.only(top: 10), child: EmptyState('Add a course and assignments to start tracking progress.')),
      ...progress.map((item) => ProgressCard(item: item)),
    ]);
  }

  Widget planner() => scroll([
    heading('Your focus plan', 'Generated from course difficulty, credit load and approaching deadlines.', action: IconButton.filledTonal(onPressed: () => action(widget.api.request('/schedules', method: 'POST', body: {'days': 7}), success: 'Study plan regenerated'), icon: const Icon(Icons.refresh))),
    if (schedules.isEmpty) const EmptyState('No upcoming study sessions. Add a course or pending assignment.'),
    ...schedules.map((item) => Card(margin: const EdgeInsets.only(bottom: 10), child: CheckboxListTile(value: item['status'] == 'completed', title: Text(item['topic'] ?? 'Study session'), subtitle: Text('${dateLabel(item['study_date'])} · ${timeLabel(item['start_time'])} · ${item['duration']} min'), onChanged: (done) => action(widget.api.request('/schedules/${item['id']}', method: 'PATCH', body: {'status': done == true ? 'completed' : 'pending'})))),
  ]);

  Widget coursePage() => scroll([
    heading('Courses', 'Manage the modules you are studying.', action: FilledButton.icon(onPressed: addCourse, icon: const Icon(Icons.add), label: const Text('Add'))),
    if (courses.isEmpty) const EmptyState('No courses yet.'),
    ...courses.map((item) => Card(margin: const EdgeInsets.only(bottom: 10), child: ListTile(leading: const CircleAvatar(backgroundColor: lime, foregroundColor: ink, child: Icon(Icons.menu_book_outlined)), title: Text('${item['course_code']} · ${item['course_title']}', style: const TextStyle(fontWeight: FontWeight.w700)), subtitle: Text('${item['credit_unit']} units · ${item['semester']} semester · difficulty ${item['difficulty']}/5'), trailing: IconButton(icon: const Icon(Icons.delete_outline), onPressed: () => action(widget.api.request('/courses/${item['id']}', method: 'DELETE'), success: 'Course removed')))),
  ]);

  Widget assignmentPage() => scroll([
    heading('Assignments', 'Keep deadlines visible and mark completed work.', action: FilledButton.icon(onPressed: courses.isEmpty ? null : addAssignment, icon: const Icon(Icons.add), label: const Text('Add'))),
    if (assignments.isEmpty) const EmptyState('No assignments yet. Add a course first.'),
    ...assignments.map((item) => Card(margin: const EdgeInsets.only(bottom: 10), child: CheckboxListTile(value: item['status'] == 'completed', title: Text(item['title'], style: TextStyle(fontWeight: FontWeight.w700, decoration: item['status'] == 'completed' ? TextDecoration.lineThrough : null)), subtitle: Text('${courseCode(item['course_id'])} · due ${dateLabel(item['due_date'])} · ${item['weight']}%'), onChanged: (done) => action(widget.api.request('/assignments/${item['id']}', method: 'PATCH', body: {'status': done == true ? 'completed' : 'pending'}), success: done == true ? 'Assignment completed' : 'Assignment restored'))),
  ]);

  Widget focusPage() {
    final minutes = secondsLeft ~/ 60, seconds = secondsLeft % 60;
    return scroll([
      heading('Focus room', 'Use a Pomodoro session to turn your plan into progress.'),
      Card(color: ink, child: Padding(padding: const EdgeInsets.all(28), child: Column(children: [
        const BrandMark(size: 58), const SizedBox(height: 22),
        Text('${minutes.toString().padLeft(2, '0')}:${seconds.toString().padLeft(2, '0')}', style: const TextStyle(color: Colors.white, fontSize: 64, fontWeight: FontWeight.w800)),
        const Text('25-minute focus session', style: TextStyle(color: Colors.white70)), const SizedBox(height: 22),
        Wrap(spacing: 10, children: [FilledButton(style: FilledButton.styleFrom(backgroundColor: lime, foregroundColor: ink), onPressed: toggleTimer, child: Text(timerRunning ? 'Pause' : 'Start')), OutlinedButton(style: OutlinedButton.styleFrom(foregroundColor: Colors.white), onPressed: resetTimer, child: const Text('Reset'))]),
      ]))),
      const SizedBox(height: 16), const Text('Completed sessions are saved securely and included in progress tracking.'),
    ]);
  }

  Widget performance() {
    final latest = predictions.isEmpty ? null : predictions.first;
    return scroll([
      heading('Academic performance', 'A course-level early signal from the OULAD Random Forest classifier.', action: FilledButton.icon(onPressed: courses.isEmpty ? null : runAssessment, icon: const Icon(Icons.auto_awesome), label: const Text('Assess'))),
      if (latest == null) const EmptyState('Run an assessment after adding a course.') else InsightCard(prediction: latest),
      const SizedBox(height: 18), Text('Assessment history', style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.bold)),
      ...predictions.map((item) => Padding(padding: const EdgeInsets.only(top: 10), child: Card(child: ListTile(title: Text('${item['course_code'] ?? 'Course'} · ${item['predicted_outcome'] == 'successful' ? 'Likely to pass' : 'At risk'}', style: const TextStyle(fontWeight: FontWeight.w700)), subtitle: Text(probabilityText(item))))),
    ]);
  }

  String courseCode(dynamic id) => courses.firstWhere((c) => c['id'] == id, orElse: () => {'course_code': 'Course'})['course_code'];

  void toggleTimer() {
    if (timerRunning) { timer?.cancel(); setState(() => timerRunning = false); return; }
    timerStarted ??= DateTime.now(); setState(() => timerRunning = true);
    timer = Timer.periodic(const Duration(seconds: 1), (_) async {
      if (secondsLeft <= 1) {
        timer?.cancel();
        final started = timerStarted ?? DateTime.now().subtract(const Duration(minutes: 25));
        setState(() { secondsLeft = 0; timerRunning = false; });
        await action(widget.api.request('/focus-sessions', method: 'POST', body: {'duration_minutes': 25, 'started_at': started.toUtc().toIso8601String(), 'completed_at': DateTime.now().toUtc().toIso8601String(), 'mode': 'pomodoro'}), success: 'Focus session completed');
      } else if (mounted) { setState(() => secondsLeft--); }
    });
  }

  void resetTimer() { timer?.cancel(); setState(() { secondsLeft = 25 * 60; timerRunning = false; timerStarted = null; }); }

  Future<void> addCourse() async {
    final code = TextEditingController(), title = TextEditingController();
    final result = await showDialog<Map<String, dynamic>>(context: context, builder: (context) => SimpleFormDialog(title: 'Add a course', fields: [('Course code', code), ('Course title', title)], onSave: () => {'course_code': code.text, 'course_title': title.text, 'credit_unit': 3, 'semester': 'First', 'difficulty': 3}));
    if (result != null) await action(widget.api.request('/courses', method: 'POST', body: result), success: 'Course added');
  }

  Future<void> addAssignment() async {
    final title = TextEditingController(), due = TextEditingController(text: DateTime.now().add(const Duration(days: 7)).toIso8601String().substring(0, 10));
    int selected = courses.first['id'];
    final result = await showDialog<Map<String, dynamic>>(context: context, builder: (context) => StatefulBuilder(builder: (context, setModalState) => AlertDialog(title: const Text('Add an assignment'), content: Column(mainAxisSize: MainAxisSize.min, children: [DropdownButtonFormField<int>(value: selected, decoration: const InputDecoration(labelText: 'Course'), items: courses.map<DropdownMenuItem<int>>((c) => DropdownMenuItem(value: c['id'], child: Text(c['course_code']))).toList(), onChanged: (value) => setModalState(() => selected = value!)), const SizedBox(height: 12), TextField(controller: title, decoration: const InputDecoration(labelText: 'Title')), const SizedBox(height: 12), TextField(controller: due, decoration: const InputDecoration(labelText: 'Due date (YYYY-MM-DD)'))]), actions: [TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')), FilledButton(onPressed: () => Navigator.pop(context, {'course_id': selected, 'title': title.text, 'due_date': '${due.text}T23:59:00', 'weight': 10}), child: const Text('Save'))])));
    if (result != null) await action(widget.api.request('/assignments', method: 'POST', body: result), success: 'Assignment added');
  }

  Future<void> runAssessment() async {
    final payload = await showDialog<Map<String, dynamic>>(context: context, builder: (_) => PredictionDialog(courses: courses));
    if (payload != null) await action(widget.api.request('/predictions', method: 'POST', body: payload), success: 'Assessment completed');
  }

  Future<void> showNotifications() async {
    await load(); if (!mounted) return;
    showModalBottomSheet(context: context, isScrollControlled: true, builder: (context) => DraggableScrollableSheet(expand: false, initialChildSize: .65, builder: (_, controller) => ListView(controller: controller, padding: const EdgeInsets.all(20), children: [Text('Notifications', style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.bold)), const SizedBox(height: 12), if (notifications.isEmpty) const EmptyState('You are all caught up.'), ...notifications.map((item) => ListTile(leading: const CircleAvatar(backgroundColor: lime, child: Icon(Icons.notifications_none, color: ink)), title: Text(item['message']), subtitle: Text(dateLabel(item['date_sent'])), trailing: item['status'] == 'unread' ? const Icon(Icons.circle, color: Colors.redAccent, size: 10) : null, onTap: () async { await action(widget.api.request('/notifications/${item['id']}', method: 'PATCH', body: {'status': 'read'})); if (context.mounted) Navigator.pop(context); }))])));
  }
}

class SimpleFormDialog extends StatelessWidget {
  const SimpleFormDialog({super.key, required this.title, required this.fields, required this.onSave});
  final String title;
  final List<(String, TextEditingController)> fields;
  final Map<String, dynamic> Function() onSave;
  @override
  Widget build(BuildContext context) => AlertDialog(title: Text(title), content: Column(mainAxisSize: MainAxisSize.min, children: fields.map((field) => Padding(padding: const EdgeInsets.only(bottom: 12), child: TextField(controller: field.$2, decoration: InputDecoration(labelText: field.$1)))).toList()), actions: [TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')), FilledButton(onPressed: () => Navigator.pop(context, onSave()), child: const Text('Save'))]);
}

class PredictionDialog extends StatefulWidget {
  const PredictionDialog({super.key, required this.courses});
  final List courses;
  @override
  State<PredictionDialog> createState() => _PredictionDialogState();
}

class _PredictionDialogState extends State<PredictionDialog> {
  final formKey = GlobalKey<FormState>();
  late int courseId;
  final inputs = <String, TextEditingController>{
    'previous_attempts': TextEditingController(text: '0'),
    'assessments_due': TextEditingController(text: '3'),
    'assessments_submitted': TextEditingController(text: '3'),
    'mean_score': TextEditingController(text: '65'),
    'on_time_submissions': TextEditingController(text: '3'),
    'mean_submission_delay': TextEditingController(text: '0'),
  };
  @override
  void initState() { super.initState(); courseId = widget.courses.first['id']; }
  @override
  Widget build(BuildContext context) => AlertDialog(title: const Text('OULAD course assessment'), content: SizedBox(width: 440, child: SingleChildScrollView(child: Form(key: formKey, child: Column(children: [DropdownButtonFormField<int>(value: courseId, decoration: const InputDecoration(labelText: 'Course'), items: widget.courses.map<DropdownMenuItem<int>>((c) => DropdownMenuItem(value: c['id'], child: Text(c['course_code']))).toList(), onChanged: (value) => courseId = value!), const SizedBox(height: 8), ...inputs.entries.map((entry) => Padding(padding: const EdgeInsets.only(top: 8), child: TextFormField(controller: entry.value, keyboardType: const TextInputType.numberWithOptions(decimal: true, signed: true), decoration: InputDecoration(labelText: entry.key.replaceAll('_', ' ')), validator: (value) => double.tryParse(value ?? '') == null ? 'Enter a number' : null)))])))), actions: [TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')), FilledButton(onPressed: () { if (!formKey.currentState!.validate()) return; Navigator.pop(context, {'course_id': courseId, ...inputs.map((name, input) => MapEntry(name, double.parse(input.text)))}); }, child: const Text('Run assessment'))]);
}

class Metric extends StatelessWidget {
  const Metric(this.label, this.value, this.icon, {super.key});
  final String label, value;
  final IconData icon;
  @override
  Widget build(BuildContext context) => Card(child: Padding(padding: const EdgeInsets.all(14), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Icon(icon, color: const Color(0xff23664a)), const Spacer(), FittedBox(child: Text(value, style: const TextStyle(fontSize: 27, fontWeight: FontWeight.w800))), Text(label)])));
}

class InsightCard extends StatelessWidget {
  const InsightCard({super.key, required this.prediction, this.onTap});
  final Map prediction;
  final VoidCallback? onTap;
  @override
  Widget build(BuildContext context) {
    final success = prediction['predicted_outcome'] == 'successful';
    return Card(color: ink, child: ListTile(onTap: onTap, contentPadding: const EdgeInsets.all(18), leading: const BrandMark(), title: Text(success ? 'Likely to pass' : 'At risk', style: const TextStyle(color: Colors.white, fontSize: 24, fontWeight: FontWeight.w800)), subtitle: Text('${prediction['course_code'] ?? 'Course'}\n${probabilityText(prediction)}', style: const TextStyle(color: Colors.white70)), trailing: onTap == null ? null : const Icon(Icons.arrow_forward, color: lime)));
  }
}

class ProgressCard extends StatelessWidget {
  const ProgressCard({super.key, required this.item});
  final Map item;
  @override
  Widget build(BuildContext context) {
    final value = ((item['assessment_progress_percent'] ?? 0) as num).toDouble();
    return Card(margin: const EdgeInsets.only(top: 10), child: Padding(padding: const EdgeInsets.all(16), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Row(children: [Expanded(child: Text('${item['course_code']} · ${item['course_title']}', style: const TextStyle(fontWeight: FontWeight.w700))), Text('${value.toStringAsFixed(0)}%')]), const SizedBox(height: 10), LinearProgressIndicator(value: value / 100, minHeight: 8, borderRadius: BorderRadius.circular(8)), const SizedBox(height: 8), Text('${item['completed_assessments']} of ${item['total_assessments']} assessments · ${item['focus_minutes']} focus minutes')])));
  }
}

class EmptyState extends StatelessWidget {
  const EmptyState(this.message, {super.key});
  final String message;
  @override
  Widget build(BuildContext context) => Card(child: Padding(padding: const EdgeInsets.all(24), child: Center(child: Text(message, textAlign: TextAlign.center))));
}

String dateLabel(dynamic value) {
  if (value == null) return 'No date';
  final parsed = DateTime.tryParse(value.toString());
  return parsed == null ? value.toString() : '${parsed.day.toString().padLeft(2, '0')}/${parsed.month.toString().padLeft(2, '0')}/${parsed.year}';
}
String timeLabel(dynamic value) => value == null ? '' : value.toString().substring(0, value.toString().length >= 5 ? 5 : value.toString().length);
String probabilityText(Map item) {
  final pass = (((item['success_probability'] ?? 0) as num).toDouble() * 100).round();
  return '$pass% chance of passing · ${100 - pass}% chance of not passing';
}
