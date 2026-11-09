// The shell sizes the content box; ExamSplitView decides from that width
// whether to put the questions beside the passage. They are two numbers in
// two files that have to agree, and when they did not, the exam layout was
// simply unreachable: the box capped at 860px, the split needed 900, so every
// participant silently got the stacked fallback on every screen size.
//
// Nothing errored. The page just quietly wasn't the exam layout.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:moirai/widgets/study_shell_metrics.dart';

void main() {
  const laptops = [
    Size(1280, 800),
    Size(1440, 900),
    Size(1512, 982), // 14" MacBook Pro
    Size(1728, 1117), // 16" MacBook Pro
    Size(1920, 1080),
  ];

  group('the exam layout is actually reachable', () {
    for (final screen in laptops) {
      test('${screen.width.toInt()}x${screen.height.toInt()} clears the split '
          'breakpoint when wide', () {
        final w = StudyShellMetrics.boxWidth(screen, wide: true);
        expect(w, greaterThanOrEqualTo(StudyShellMetrics.splitBreakpoint),
            reason: 'box is ${w}px; the split needs '
                '${StudyShellMetrics.splitBreakpoint}px, so the questions '
                'would sit under the passage instead of beside it');
      });
    }

    test('a narrow step never reaches the split width', () {
      // Questionnaires should stay a comfortable single measure.
      for (final screen in laptops) {
        expect(StudyShellMetrics.boxWidth(screen), lessThan(900));
      }
    });
  });

  group('the box never exceeds the window', () {
    for (final screen in [...laptops, const Size(800, 600), const Size(390, 844)]) {
      test('${screen.width.toInt()}px wide', () {
        for (final wide in [true, false]) {
          expect(StudyShellMetrics.boxWidth(screen, wide: wide),
              lessThanOrEqualTo(screen.width),
              reason: 'a box wider than the screen overflows horizontally');
        }
      });
    }
  });

  test('very wide screens stop growing, to keep line length readable', () {
    expect(StudyShellMetrics.boxWidth(const Size(3840, 2160), wide: true),
        StudyShellMetrics.wideMax);
  });

  test('compact screens ignore wide and use nearly the whole width', () {
    const phone = Size(390, 844);
    expect(StudyShellMetrics.boxWidth(phone, wide: true),
        StudyShellMetrics.boxWidth(phone));
  });
}
