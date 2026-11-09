import 'dart:ui' show Size;

/// Box dimensions for the study shell.
///
/// Separate from StudyScaffold, and dependency-free, so it can be unit tested:
/// study_scaffold.dart pulls in ApiService and therefore dart:html, which does
/// not exist in the VM test environment.
///
/// This is not styling trivia. The content box caps at 860px by default, and
/// ExamSplitView needs 900px before it will place the questions beside the
/// passage. Those two numbers lived in different files and disagreed, so the
/// reading step rendered stacked at every window size — a correct layout that
/// was simply never reachable. Keeping the rule here, with the breakpoint
/// asserted in a test, is what stops that recurring.
class StudyShellMetrics {
  /// Below this the shell drops its margins and uses nearly the whole screen.
  static const double compactBelow = 700;

  /// The width ExamSplitView needs before it places the questions beside the
  /// passage. Declared here so the shell and the split view cannot drift apart
  /// again — they disagreed by 40px and the exam layout was unreachable.
  static const double splitBreakpoint = 900;

  /// Wide steps stop growing here; beyond it the passage line length gets
  /// uncomfortable to read.
  static const double wideMax = 1600;

  static bool isCompact(Size screen) => screen.width < compactBelow;

  static double boxWidth(Size screen, {bool wide = false}) {
    if (isCompact(screen)) return screen.width * 0.94;
    // Take the window less a margin, capped — never clamped UP, which would
    // make the box wider than the screen and overflow. On a window too narrow
    // to clear splitBreakpoint the box simply stays small and the split view
    // stacks, which is the correct outcome rather than a squeezed two-column.
    if (wide) {
      final available = screen.width - 64;
      return available > wideMax ? wideMax : available;
    }
    return (screen.width * 0.72).clamp(560.0, 860.0);
  }

  static double boxHeight(Size screen, {bool wide = false}) {
    if (wide) return (screen.height * 0.86).clamp(460.0, 1000.0);
    return (screen.height * 0.72).clamp(420.0, 720.0);
  }
}
