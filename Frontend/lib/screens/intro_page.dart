import 'package:flutter/material.dart';
import '../data/study_steps.dart';
import '../theme/app_colors.dart';
import '../widgets/study_scaffold.dart';

/// Fun, engaging introduction to the research. Two sub-pages inside one
/// step so the text never feels long.
class IntroPage extends StatefulWidget {
  const IntroPage({super.key});

  @override
  State<IntroPage> createState() => _IntroPageState();
}

class _IntroPageState extends State<IntroPage> {
  int _sub = 0; // 0 = what we do, 1 = the steps

  @override
  Widget build(BuildContext context) {
    return StudyScaffold(
      currentStep: StudyStep.intro,
      bottomBar: Row(
        children: [
          if (_sub > 0)
            TextButton(
              onPressed: () => setState(() => _sub = 0),
              child: const Text('قبلی',
                  style: TextStyle(color: AppColors.purple)),
            ),
          const Spacer(),
          SizedBox(
            width: 160,
            child: StudyPrimaryButton(
              label: _sub == 0 ? 'بعدی' : 'بریم مرحله بعد',
              onPressed: () {
                if (_sub == 0) {
                  setState(() => _sub = 1);
                } else {
                  Navigator.pushNamed(context, '/consent');
                }
              },
            ),
          ),
        ],
      ),
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: AnimatedSwitcher(
          duration: const Duration(milliseconds: 250),
          child: _sub == 0 ? _buildWhat() : _buildSteps(),
        ),
      ),
    );
  }

  Widget _buildWhat() {
    return SingleChildScrollView(
      key: const ValueKey('what'),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: const [
          Text(
            'اینجا چه خبره؟ ✨',
            style: TextStyle(
                fontSize: 24,
                fontWeight: FontWeight.bold,
                color: AppColors.navy),
          ),
          SizedBox(height: 14),
          Text(
            'مویرای یک تجربه‌ی کوتاهه که توش با کمک هوش مصنوعی تصویر روشنی '
            'از آینده‌ت می‌سازی و تأثیرش رو روی کاری که برات مهمه می‌بینی.',
            style: TextStyle(fontSize: 16, height: 2.0, color: AppColors.navy),
          ),
          SizedBox(height: 24),
          Text(
            'چرا ارزشش رو داره؟',
            style: TextStyle(
                fontSize: 19,
                fontWeight: FontWeight.bold,
                color: AppColors.navy),
          ),
          SizedBox(height: 10),
          _IntroStep(
              icon: Icons.rocket_launch_outlined,
              text: 'تصورِ روشن و احساسیِ آینده، یک روش اثبات‌شده برای بالا '
                  'بردن انگیزه و پایبندی به هدفه — اینجا نسخه‌ی '
                  'شخصی‌سازی‌شده‌ش رو تجربه می‌کنی.'),
          _IntroStep(
              icon: Icons.wallpaper_outlined,
              text: 'یک تصویر اختصاصی از لحظه‌ی موفقیتت می‌گیری — ساخته‌شده '
                  'از توصیف خودت، و مال خودت.'),
          _IntroStep(
              icon: Icons.self_improvement_outlined,
              text: 'حسِ رسیدن به هدف رو از نزدیک تجربه می‌کنی و شناخت '
                  'دقیق‌تری از خودت پیدا می‌کنی.'),
          _IntroStep(
              icon: Icons.menu_book_outlined,
              text: 'یک تمرین ریدینگ در سطح آزمون‌های واقعی انجام می‌دی — '
                  'مفید اگر آیلتس یا تافل در برنامه‌ته.'),
        ],
      ),
    );
  }

  Widget _buildSteps() {
    return Column(
      key: const ValueKey('steps'),
      mainAxisAlignment: MainAxisAlignment.center,
      crossAxisAlignment: CrossAxisAlignment.start,
      children: const [
        Text(
          'مراحل مطالعه',
          style: TextStyle(
              fontSize: 24,
              fontWeight: FontWeight.bold,
              color: AppColors.navy),
        ),
        SizedBox(height: 14),
        _IntroStep(
            icon: Icons.looks_one_rounded,
            text: 'یک تصویر ذهنی از آینده‌ت می‌سازی و با جزئیات کامل '
                'توصیفش می‌کنی.'),
        _IntroStep(
            icon: Icons.looks_two_rounded,
            text: 'یک تمرین ریدینگ واقعی انجام می‌دی و تصاویر '
                ' اختصاصی از لحظه‌ی موفقیتت دریافت می‌کنی.'),
        _IntroStep(
            icon: Icons.looks_3_rounded,
            text: 'در پایان، یک پرسشنامه کوتاه درباره‌ی تجربه‌ت پر می‌کنی.'),
      ],
    );
  }
}

class _IntroStep extends StatelessWidget {
  final IconData icon;
  final String text;
  const _IntroStep({required this.icon, required this.text});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        children: [
          Icon(icon, color: AppColors.purple, size: 22),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              text,
              style: const TextStyle(
                  fontSize: 16, height: 1.7, color: AppColors.navy),
            ),
          ),
        ],
      ),
    );
  }
}
