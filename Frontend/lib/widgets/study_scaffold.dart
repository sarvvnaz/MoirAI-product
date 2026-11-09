import '../l10n/app_language.dart';
import 'package:flutter/material.dart';
import '../data/study_steps.dart';
import '../services/api_service.dart';
import '../theme/app_colors.dart';
import 'study_shell_metrics.dart';

/// The shared shell for every step of the study:
///  - full navy background
///  - stepper circles above (mint = done/current, dim = pending)
///  - a centered light content box whose size stays constant across steps
///    (but adapts to the screen size)
///
/// Pages provide their own content and buttons inside [child].
class StudyScaffold extends StatelessWidget {
  final StudyStep currentStep;
  final Widget child;

  /// Optional bar pinned to the bottom of the box (e.g. Next button row).
  final Widget? bottomBar;

  /// Let this step use the full window instead of the narrow centred box.
  ///
  /// The reading session needs it: the exam layout puts the questions beside
  /// the passage, and the default box caps at 860px, which leaves two columns
  /// too thin to read either. Every other step is a form or a short
  /// questionnaire, where a narrow measure is easier to read, so the default
  /// stays as it was.
  final bool wide;

  const StudyScaffold({
    super.key,
    required this.currentStep,
    required this.child,
    this.bottomBar,
    this.wide = false,
  });

  @override
  Widget build(BuildContext context) {
    final size = MediaQuery.of(context).size;
    final bool compact = StudyShellMetrics.isCompact(size);

    // Constant box size per step; adaptive to screen. A wide step takes the
    // window instead, less a small margin. See StudyShellMetrics.
    final double boxWidth = StudyShellMetrics.boxWidth(size, wide: wide);
    final double boxHeight = StudyShellMetrics.boxHeight(size, wide: wide);

    return Directionality(
      textDirection: AppLanguage.of(context).direction,
      child: Scaffold(
        backgroundColor: AppColors.navy,
        body: SafeArea(
          child: Center(
            child: SingleChildScrollView(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  const SizedBox(height: 16),
                  Padding(padding: const EdgeInsets.symmetric(horizontal: 20),
                    child: Align(alignment: AlignmentDirectional.centerEnd,
                      child: TextButton.icon(
                        style: TextButton.styleFrom(foregroundColor: AppColors.lavender),
                        onPressed: AppLanguage.instance.toggle,
                        icon: const Icon(Icons.language, size: 18),
                        label: Text(AppLanguage.instance.isEnglish ? 'فارسی' : 'English'),
                      ),
                    ),
                  ),
                  _Stepper(currentStep: currentStep, compact: compact),
                  const SizedBox(height: 20),
                  Container(
                    width: boxWidth,
                    height: boxHeight,
                    decoration: BoxDecoration(
                      color: AppColors.lavender,
                      borderRadius: BorderRadius.circular(24),
                      boxShadow: [
                        BoxShadow(
                          color: Colors.black.withOpacity(0.25),
                          blurRadius: 24,
                          offset: const Offset(0, 10),
                        ),
                      ],
                    ),
                    clipBehavior: Clip.antiAlias,
                    child: Column(
                      children: [
                        Expanded(child: child),
                        if (bottomBar != null)
                          Container(
                            padding: const EdgeInsets.symmetric(
                                horizontal: 20, vertical: 12),
                            decoration: BoxDecoration(
                              color: Colors.white,
                              border: Border(
                                top: BorderSide(
                                    color: AppColors.navy.withOpacity(0.08)),
                              ),
                            ),
                            child: bottomBar!,
                          ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 24),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// The horizontal progress circles above the content box.
class _Stepper extends StatelessWidget {
  final StudyStep currentStep;
  final bool compact;

  const _Stepper({required this.currentStep, required this.compact});

  @override
  Widget build(BuildContext context) {
    // Arm-aware: the control arm never reaches the chat step.
    final steps = visibleStepsFor(ApiService.cachedStudyGroup);
    final currentIndex = steps.indexOf(currentStep);
    final double circle = compact ? 26 : 34;

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          for (int i = 0; i < steps.length; i++) ...[
            if (i > 0)
              Container(
                width: compact ? 12 : 26,
                height: 3,
                decoration: BoxDecoration(
                  color: i <= currentIndex
                      ? AppColors.mint
                      : Colors.white.withOpacity(0.25),
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
            _StepCircle(
              label: studyStepLabels[steps[i]]!,
              size: circle,
              state: i < currentIndex
                  ? _StepState.done
                  : (i == currentIndex ? _StepState.current : _StepState.todo),
              showLabel: !compact || i == currentIndex,
            ),
          ],
        ],
      ),
    );
  }
}

enum _StepState { done, current, todo }

class _StepCircle extends StatelessWidget {
  final String label;
  final double size;
  final _StepState state;
  final bool showLabel;

  const _StepCircle({
    required this.label,
    required this.size,
    required this.state,
    required this.showLabel,
  });

  @override
  Widget build(BuildContext context) {
    final Color fill;
    final Widget inner;
    switch (state) {
      case _StepState.done:
        fill = AppColors.mint;
        inner = Icon(Icons.check_rounded,
            size: size * 0.62, color: AppColors.navy);
        break;
      case _StepState.current:
        fill = AppColors.mint;
        inner = Container(
          width: size * 0.32,
          height: size * 0.32,
          decoration: const BoxDecoration(
            color: AppColors.navy,
            shape: BoxShape.circle,
          ),
        );
        break;
      case _StepState.todo:
        fill = Colors.white.withOpacity(0.18);
        inner = const SizedBox.shrink();
        break;
    }

    final circle = AnimatedContainer(
      duration: const Duration(milliseconds: 250),
      width: size,
      height: size,
      decoration: BoxDecoration(
        color: fill,
        shape: BoxShape.circle,
        border: state == _StepState.current
            ? Border.all(color: Colors.white, width: 2.5)
            : null,
        boxShadow: state == _StepState.current
            ? [
                BoxShadow(
                  color: AppColors.mint.withOpacity(0.55),
                  blurRadius: 14,
                  spreadRadius: 1,
                ),
              ]
            : null,
      ),
      child: Center(child: inner),
    );

    if (!showLabel) return circle;

    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        circle,
        const SizedBox(height: 5),
        AppText(
          label,
          style: TextStyle(
            fontSize: 11,
            fontWeight:
                state == _StepState.current ? FontWeight.bold : FontWeight.w400,
            color: state == _StepState.todo
                ? Colors.white.withOpacity(0.45)
                : Colors.white,
          ),
        ),
      ],
    );
  }
}

/// The standard primary button used in step pages.
class StudyPrimaryButton extends StatelessWidget {
  final String label;
  final VoidCallback? onPressed;
  final bool busy;

  const StudyPrimaryButton({
    super.key,
    required this.label,
    required this.onPressed,
    this.busy = false,
  });

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 50,
      child: ElevatedButton(
        onPressed: busy ? null : onPressed,
        style: ElevatedButton.styleFrom(
          backgroundColor: AppColors.purple,
          disabledBackgroundColor: Colors.grey.shade300,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
        ),
        child: busy
            ? const SizedBox(
                width: 22,
                height: 22,
                child: CircularProgressIndicator(
                    color: Colors.white, strokeWidth: 2.5),
              )
            : AppText(
                label,
                style: const TextStyle(fontSize: 16, color: Colors.white),
              ),
      ),
    );
  }
}
