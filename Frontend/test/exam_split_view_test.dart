// The exam layout is a protocol requirement, not decoration: questions on the
// LEFT, passage on the RIGHT, as in the computer-delivered IELTS test.
//
// The failure mode these guard against is specific and invisible in code
// review: the study UI is Persian and therefore RTL, and a plain Row in an
// RTL context lays its children out right-to-left. The layout would come out
// mirrored, look perfectly deliberate, and differ from what is written up.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:moirai/widgets/exam_split_view.dart';
import 'package:moirai/widgets/study_shell_metrics.dart';

void main() {
  const questions = Key('questions');
  const passage = Key('passage');

  /// Sets the real test surface size rather than wrapping in a SizedBox: a
  /// SizedBox wider than the 800x600 default surface overflows, and the panes
  /// then report clamped positions that make the assertions meaningless.
  Future<void> pumpAt(WidgetTester tester,
      {required double width, required TextDirection direction}) async {
    tester.view.physicalSize = Size(width, 900);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await tester.pumpWidget(
      Directionality(
        textDirection: direction,
        child: const ExamSplitView(
          questionsPane: ColoredBox(color: Colors.red, key: questions),
          passagePane: ColoredBox(color: Colors.blue, key: passage),
        ),
      ),
    );
  }

  testWidgets('questions sit LEFT of the passage on a wide screen',
      (tester) async {
    await pumpAt(tester, width: 1400, direction: TextDirection.ltr);

    final q = tester.getTopLeft(find.byKey(questions));
    final p = tester.getTopLeft(find.byKey(passage));
    expect(q.dx, lessThan(p.dx));
  });

  testWidgets('order survives an RTL app direction', (tester) async {
    // The whole reason this widget exists. Persian UI is RTL; without the
    // forced LTR the two panes would swap and nothing would look broken.
    await pumpAt(tester, width: 1400, direction: TextDirection.rtl);

    final q = tester.getTopLeft(find.byKey(questions));
    final p = tester.getTopLeft(find.byKey(passage));
    expect(q.dx, lessThan(p.dx),
        reason: 'RTL flipped the panes — questions must stay on the left');
  });

  testWidgets('panes stack on a narrow screen, passage first', (tester) async {
    await pumpAt(tester, width: 600, direction: TextDirection.rtl);

    final q = tester.getTopLeft(find.byKey(questions));
    final p = tester.getTopLeft(find.byKey(passage));
    expect(p.dy, lessThan(q.dy),
        reason: 'stacked layout should show the passage above the questions');
    expect((q.dx - p.dx).abs(), lessThan(1),
        reason: 'stacked panes should share a left edge, not sit side by side');
  });

  testWidgets('both panes are actually visible side by side', (tester) async {
    await pumpAt(tester, width: 1400, direction: TextDirection.ltr);

    final qw = tester.getSize(find.byKey(questions)).width;
    final pw = tester.getSize(find.byKey(passage)).width;
    // Neither pane may be squeezed to nothing; the reading task depends on
    // both being usable at once.
    expect(qw, greaterThan(300));
    expect(pw, greaterThan(300));
    expect(pw, greaterThan(qw), reason: 'the passage pane is the wider one');
  });

  group('the shell must be wide enough to reach the split', () {
    // The layout was correct and unreachable: the shell capped at 860px while
    // the split view needed 900, so the reading step rendered stacked at every
    // window size and nothing looked broken.
    test('a wide step clears the breakpoint on a normal laptop', () {
      const screen = Size(1440, 900);
      expect(StudyShellMetrics.boxWidth(screen, wide: true),
          greaterThanOrEqualTo(900));
    });

    test('the shell and the split view agree on the breakpoint', () {
      // They disagreed by 40px, which is the whole bug.
      expect(StudyShellMetrics.splitBreakpoint, 900);
    });

    test('other steps keep the narrow measure', () {
      const screen = Size(1440, 900);
      expect(StudyShellMetrics.boxWidth(screen), lessThan(900));
    });

    test('small windows still fall back to stacked, not a squeezed split', () {
      const screen = Size(820, 800);
      final w = StudyShellMetrics.boxWidth(screen, wide: true);
      expect(w, lessThanOrEqualTo(screen.width),
          reason: 'the box must never be wider than the window');
    });
  });
}
