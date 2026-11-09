import 'package:flutter/material.dart';
import '../data/study_steps.dart';
import '../theme/app_colors.dart';
import '../widgets/study_scaffold.dart';

class IntroPage extends StatelessWidget {
  const IntroPage({super.key});

  @override
  Widget build(BuildContext context) => StudyScaffold(
    currentStep: StudyStep.intro,
    bottomBar: Row(
      children: [
        TextButton(
          onPressed: () => Navigator.pushNamed(context, '/login'),
          child: const Text('ورود به حساب'),
        ),
        const Spacer(),
        SizedBox(
          width: 160,
          child: StudyPrimaryButton(
            label: 'شروع',
            onPressed: () => Navigator.pushNamed(context, '/signup'),
          ),
        ),
      ],
    ),
    child: SingleChildScrollView(
      padding: const EdgeInsets.all(32),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'برای چیزی که برات مهمه، وقت بذار',
            style: TextStyle(
              fontSize: 26,
              fontWeight: FontWeight.bold,
              color: AppColors.navy,
              height: 1.6,
            ),
          ),
          const SizedBox(height: 16),
          const Text(
            'مویرای همراه مطالعه‌ی توئه؛ با یادآوری هدفت، کمکت می‌کنه وقتی حواست پرت شد دوباره برگردی.',
            style: TextStyle(fontSize: 16, height: 1.9, color: AppColors.navy),
          ),
          const SizedBox(height: 24),
          _section(
            Icons.chat_bubble_outline,
            'از هدفت بگو',
            'در یک گفتگوی کوتاه، از آینده‌ای که می‌خوای می‌گی تا یادآور شخصی‌ات ساخته بشه.',
          ),
          _section(
            Icons.upload_file,
            'فایلت رو انتخاب کن',
            'کتاب، مقاله یا جزوه‌ات رو به‌صورت PDF باز کن و بخون.',
          ),
          _section(
            Icons.favorite_border,
            'وقتی حواست رفت، برگرد',
            'یادآورت بهت یادآوری می‌کنه برای چی شروع کردی.',
          ),
        ],
      ),
    ),
  );

  Widget _section(IconData icon, String title, String text) => Padding(
    padding: const EdgeInsets.only(bottom: 20),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(icon, color: AppColors.purple, size: 24),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                title,
                style: const TextStyle(
                  fontSize: 17,
                  fontWeight: FontWeight.bold,
                  color: AppColors.navy,
                ),
              ),
              const SizedBox(height: 6),
              Text(
                text,
                style: const TextStyle(
                  fontSize: 15,
                  height: 1.9,
                  color: AppColors.navy,
                ),
              ),
            ],
          ),
        ),
      ],
    ),
  );
}
