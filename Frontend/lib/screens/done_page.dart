import 'package:flutter/material.dart';
import '../data/study_steps.dart';
import '../theme/app_colors.dart';
import '../widgets/study_scaffold.dart';

/// Final thank-you screen shown after the participant completes the study.
class DonePage extends StatelessWidget {
  const DonePage({super.key});

  @override
  Widget build(BuildContext context) {
    return StudyScaffold(
      currentStep: StudyStep.finish,
      child: Center(
        child: Padding(
          padding: const EdgeInsets.all(36),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: const [
              Icon(Icons.check_circle_rounded, color: AppColors.mint, size: 76),
              SizedBox(height: 20),
              Text(
                'برای چیزی که برات مهم بود، وقت گذاشتی 🌱',
                textAlign: TextAlign.center,
                style: TextStyle(
                  fontSize: 24,
                  fontWeight: FontWeight.bold,
                  color: AppColors.navy,
                ),
              ),
              SizedBox(height: 12),
              Text(
                'وقت یک استراحت کوتاهه.',
                textAlign: TextAlign.center,
                style: TextStyle(
                    fontSize: 16, height: 1.9, color: AppColors.navy),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
