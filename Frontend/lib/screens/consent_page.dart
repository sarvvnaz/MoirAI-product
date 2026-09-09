import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
// ignore: deprecated_member_use
import 'dart:html' as html;
import 'package:shared_preferences/shared_preferences.dart';
import '../data/study_steps.dart';
import '../theme/app_colors.dart';
import '../widgets/study_scaffold.dart';

/// Short consent step, right after the intro. Emphasizes anonymity:
/// EFT content and goals are never seen by a person; data is stored under
/// an anonymous participant code only.
class ConsentPage extends StatefulWidget {
  const ConsentPage({super.key});

  @override
  State<ConsentPage> createState() => _ConsentPageState();
}

class _ConsentPageState extends State<ConsentPage> {
  bool _agree = false;

  Future<void> _continue() async {
    final ts = DateTime.now().toIso8601String();
    if (kIsWeb) {
      html.window.localStorage['moirai:consent_at'] = ts;
    } else {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString('moirai:consent_at', ts);
    }
    if (!mounted) return;
    Navigator.pushNamed(context, '/signup');
  }

  @override
  Widget build(BuildContext context) {
    return StudyScaffold(
      currentStep: StudyStep.consent,
      bottomBar: Row(
        children: [
          const Spacer(),
          SizedBox(
            width: 200,
            child: StudyPrimaryButton(
              label: 'موافقم، ادامه بده',
              onPressed: _agree ? _continue : null,
            ),
          ),
        ],
      ),
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'قبل از شروع، چند قول 🤝',
              style: TextStyle(
                  fontSize: 22,
                  fontWeight: FontWeight.bold,
                  color: AppColors.navy),
            ),
            const SizedBox(height: 16),
            const _ConsentItem(
              icon: Icons.visibility_off_outlined,
              text:
                  'تصویر آینده و هدف‌های شخصی‌ات رو هیچ انسانی نمی‌بینه؛ فقط سیستم ازش برای ساخت یادآور شخصیت استفاده می‌کنه.',
            ),
            const _ConsentItem(
              icon: Icons.badge_outlined,
              text:
                  'کاملاً ناشناس می‌مانی: نه ایمیل می‌خواهیم نه اسم کامل. فقط یک شناسه‌ی دلخواه انتخاب می‌کنی.',
            ),
            const _ConsentItem(
              icon: Icons.science_outlined,
              text:
                  'رفتارهایی مثل جابه‌جایی بین صفحات در طول جلسه‌ی مطالعه به‌صورت خودکار و ناشناس ثبت می‌شود ولی محتوای صفحه‌‌ها و هیچ اطلاعات شخصی‌ای مانیتور نمی شوند.',
            ),
            const _ConsentItem(
              icon: Icons.logout_outlined,
              text: 'شرکت داوطلبانه است و هر لحظه می‌تونی انصراف بدی.',
            ),
            const SizedBox(height: 12),
            CheckboxListTile(
              value: _agree,
              onChanged: (v) => setState(() => _agree = v ?? false),
              activeColor: AppColors.purple,
              controlAffinity: ListTileControlAffinity.leading,
              contentPadding: EdgeInsets.zero,
              title: const Text(
                'با شرایط بالا موافقم و داوطلبانه شرکت می‌کنم.',
                style: TextStyle(
                    fontSize: 15,
                    fontWeight: FontWeight.w600,
                    color: AppColors.navy),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ConsentItem extends StatelessWidget {
  final IconData icon;
  final String text;
  const _ConsentItem({required this.icon, required this.text});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 7),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, color: AppColors.purple, size: 22),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              text,
              style: const TextStyle(
                  fontSize: 14.5, height: 1.8, color: AppColors.navy),
            ),
          ),
        ],
      ),
    );
  }
}
