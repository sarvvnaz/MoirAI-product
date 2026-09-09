import 'package:flutter/material.dart';
import '../data/study_steps.dart';
import '../theme/app_colors.dart';
import '../widgets/study_scaffold.dart';

/// Entry point of the study: first-time participants start the journey,
/// returning participants continue with their code.
class StartPage extends StatelessWidget {
  const StartPage({super.key});

  @override
  Widget build(BuildContext context) {
    return StudyScaffold(
      currentStep: StudyStep.start,
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text(
              'به مویرای خوش اومدی',
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: 28,
                fontWeight: FontWeight.bold,
                color: AppColors.navy,
              ),
            ),
            const SizedBox(height: 12),
            const Text(
              'یک تجربه‌ی کوتاه و متفاوت برای دیدن آینده‌ای که براش تلاش می‌کنی',
              textAlign: TextAlign.center,
              style: TextStyle(
                  fontSize: 16, height: 1.8, color: AppColors.navy),
            ),
            const SizedBox(height: 40),
            StudyPrimaryButton(
              label: 'برای اولین بار شروع می‌کنم',
              onPressed: () => Navigator.pushNamed(context, '/intro'),
            ),
            const SizedBox(height: 14),
            SizedBox(
              height: 50,
              child: OutlinedButton(
                onPressed: () => Navigator.pushNamed(context, '/login'),
                style: OutlinedButton.styleFrom(
                  side: const BorderSide(color: AppColors.purple, width: 1.5),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                ),
                child: const Text(
                  'قبلاً شرکت کرده‌ام (ورود با شناسه)',
                  style: TextStyle(fontSize: 15, color: AppColors.purple),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
