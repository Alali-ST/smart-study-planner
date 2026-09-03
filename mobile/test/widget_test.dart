import 'package:flutter_test/flutter_test.dart';
import 'package:smart_study_planner/main.dart';
void main(){testWidgets('shows login interface',(tester)async{await tester.pumpWidget(const StudyPlannerApp());expect(find.text('StudySmart'),findsOneWidget);expect(find.text('Sign in'),findsOneWidget);});}

