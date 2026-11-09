import 'package:flutter/material.dart';

/// The computer-based-test layout: **questions on the LEFT, passage on the
/// RIGHT**, each scrolling independently.
///
/// Lives in its own widget for one reason: the pane ORDER has to survive the
/// app's right-to-left direction. The study UI is Persian and therefore RTL,
/// and a plain `Row` in an RTL context lays its children out right-to-left —
/// so the "first" child would appear on the right and the layout would come
/// out mirrored from what the protocol specifies. Forcing LTR here fixes the
/// order, while each pane's own content keeps whatever direction it needs.
///
/// Below [breakpoint] the panes stack instead, passage first. A split view on
/// a narrow screen gives two unusably thin columns, and the reading task is
/// the thing being measured — it must not be degraded by whatever device the
/// participant happens to bring.
class ExamSplitView extends StatelessWidget {
  const ExamSplitView({
    super.key,
    required this.questionsPane,
    required this.passagePane,
    this.breakpoint = 900,
    this.stackedPassageHeight = 420,
    this.stackedQuestionsHeight = 520,
  });

  final Widget questionsPane;
  final Widget passagePane;
  final double breakpoint;
  final double stackedPassageHeight;
  final double stackedQuestionsHeight;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        if (constraints.maxWidth < breakpoint) {
          return SingleChildScrollView(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                SizedBox(height: stackedPassageHeight, child: passagePane),
                const SizedBox(height: 16),
                SizedBox(height: stackedQuestionsHeight, child: questionsPane),
              ],
            ),
          );
        }
        return Directionality(
          textDirection: TextDirection.ltr,
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Expanded(flex: 5, child: questionsPane),
              const SizedBox(width: 12),
              Expanded(flex: 6, child: passagePane),
            ],
          ),
        );
      },
    );
  }
}
