import 'package:flutter/material.dart';
import '../theme/app_colors.dart';

/// The overlapping-circles future self-continuity measure
/// (Ersner-Hershfield et al., 2009; adapted from Aron, Aron & Smollan, 1992).
///
/// Seven pairs of circles, from fully separate to almost coincident. The
/// participant picks the pair that represents their relationship to their
/// future self.
///
/// Drawn rather than written on purpose. It is the one measure in this study
/// that asks about the future self, and this population finds that a heavy
/// question; a picture with two short labels asks it far more gently than a
/// paragraph would. It also sidesteps the translation risk that a wordier
/// instrument would carry, since the only Persian here is the two labels.
class CirclesScale extends StatelessWidget {
  final int? value; // 1..7, null = nothing chosen yet
  final ValueChanged<int> onChanged;
  final String leftLabel;
  final String rightLabel;

  const CirclesScale({
    super.key,
    required this.value,
    required this.onChanged,
    required this.leftLabel,
    required this.rightLabel,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(leftLabel,
                style: const TextStyle(fontSize: 12, color: AppColors.navy)),
            Text(rightLabel,
                style: const TextStyle(fontSize: 12, color: AppColors.navy)),
          ],
        ),
        const SizedBox(height: 8),
        // Wraps rather than scrolls: on a narrow screen a horizontally
        // scrolling scale hides options, and an option the participant never
        // sees is one they can never choose.
        Wrap(
          alignment: WrapAlignment.center,
          spacing: 6,
          runSpacing: 6,
          children: [
            for (int i = 1; i <= 7; i++)
              _CirclePair(
                index: i,
                selected: value == i,
                onTap: () => onChanged(i),
              ),
          ],
        ),
      ],
    );
  }
}

class _CirclePair extends StatelessWidget {
  final int index; // 1 = separate … 7 = almost coincident
  final bool selected;
  final VoidCallback onTap;

  const _CirclePair({
    required this.index,
    required this.selected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Semantics(
      button: true,
      selected: selected,
      label: 'گزینه $index از ۷',
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(10),
        child: Container(
          width: 74,
          padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 4),
          decoration: BoxDecoration(
            color: selected
                ? AppColors.purple.withValues(alpha: 0.12)
                : Colors.transparent,
            border: Border.all(
              color: selected ? AppColors.purple : Colors.grey.shade300,
              width: selected ? 2 : 1,
            ),
            borderRadius: BorderRadius.circular(10),
          ),
          child: Column(
            children: [
              SizedBox(
                height: 40,
                width: 62,
                child: CustomPaint(
                  painter: _PairPainter(
                    overlap: (index - 1) / 6.0,
                    color: selected ? AppColors.purple : AppColors.navy,
                  ),
                ),
              ),
              const SizedBox(height: 4),
              Text('$index',
                  style: TextStyle(
                    fontSize: 11,
                    fontWeight: selected ? FontWeight.bold : FontWeight.normal,
                    color: selected ? AppColors.purple : Colors.grey.shade600,
                  )),
            ],
          ),
        ),
      ),
    );
  }
}

class _PairPainter extends CustomPainter {
  final double overlap; // 0 = apart, 1 = almost coincident
  final Color color;

  _PairPainter({required this.overlap, required this.color});

  @override
  void paint(Canvas canvas, Size size) {
    final r = size.height / 2 - 2;
    final cy = size.height / 2;
    // At overlap 0 the circles just touch; at 1 their centres nearly meet.
    // Never fully coincident — the published scale keeps the last pair
    // distinguishable rather than showing a single circle.
    final gap = r * (2 - 1.7 * overlap);
    final cx = size.width / 2;

    final stroke = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.6
      ..color = color;
    final fill = Paint()
      ..style = PaintingStyle.fill
      ..color = color.withValues(alpha: 0.10);

    for (final dx in [-gap / 2, gap / 2]) {
      canvas.drawCircle(Offset(cx + dx, cy), r, fill);
      canvas.drawCircle(Offset(cx + dx, cy), r, stroke);
    }
  }

  @override
  bool shouldRepaint(_PairPainter old) =>
      old.overlap != overlap || old.color != color;
}
