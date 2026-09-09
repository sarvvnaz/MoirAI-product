import 'package:flutter/material.dart';
import '../data/study_steps.dart';
import '../services/api_service.dart';
import '../theme/app_colors.dart';
import '../widgets/study_scaffold.dart';
import 'done_page.dart';

/// Last feedback step before finishing the study: overall experience,
/// motivation, usefulness of reminders — with dragging bars (sliders).
class FinalFeedbackPage extends StatefulWidget {
  final int userId;
  const FinalFeedbackPage({super.key, required this.userId});

  @override
  State<FinalFeedbackPage> createState() => _FinalFeedbackPageState();
}

class _FinalFeedbackPageState extends State<FinalFeedbackPage> {
  double? _motivation;
  double? _usefulness;
  double? _easeOfUse;
  double? _overall;
  final TextEditingController _commentController = TextEditingController();
  bool _sending = false;

  @override
  void dispose() {
    _commentController.dispose();
    super.dispose();
  }

  String? get _firstMissing {
    if (_motivation == null) return 'انگیزه';
    if (_usefulness == null) return 'مفید بودن یادآورها';
    if (_easeOfUse == null) return 'راحتی کار با سامانه';
    if (_overall == null) return 'تجربه‌ی کلی';
    return null;
  }

  Future<void> _submit() async {
    final missing = _firstMissing;
    if (missing != null) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('لطفاً بخش «$missing» را هم مشخص کن 🙂')),
      );
      return;
    }
    setState(() => _sending = true);
    try {
      await ApiService.logEvent(widget.userId, 'final_survey', {
        'motivation': _motivation!.round(),
        'reminder_usefulness': _usefulness!.round(),
        'ease_of_use': _easeOfUse!.round(),
        'overall_experience': _overall!.round(),
        'comment': _commentController.text.trim().isEmpty
            ? null
            : _commentController.text.trim(),
      });
    } catch (_) {
      // Don't block completion on logging.
    } finally {
      if (mounted) setState(() => _sending = false);
    }
    if (!mounted) return;
    Navigator.pushReplacement(
      context,
      MaterialPageRoute(builder: (_) => const DonePage()),
    );
  }

  Widget _slider(String label, double? value, ValueChanged<double> onChanged,
      {String low = 'کم', String high = 'زیاد'}) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: const TextStyle(
              fontSize: 15,
              fontWeight: FontWeight.w600,
              color: AppColors.navy),
        ),
        Row(
          children: [
            Text(low,
                style: TextStyle(
                    fontSize: 12, color: AppColors.navy.withOpacity(0.6))),
            Expanded(
              child: Slider(
                value: value ?? 4,
                min: 1,
                max: 7,
                divisions: 6,
                label: (value ?? 4).round().toString(),
                activeColor: AppColors.purple,
                inactiveColor: AppColors.purple.withOpacity(0.2),
                onChanged: onChanged,
              ),
            ),
            Text(high,
                style: TextStyle(
                    fontSize: 12, color: AppColors.navy.withOpacity(0.6))),
          ],
        ),
        const SizedBox(height: 6),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    return StudyScaffold(
      currentStep: StudyStep.finish,
      bottomBar: Row(
        children: [
          const Spacer(),
          SizedBox(
            width: 170,
            child: StudyPrimaryButton(
              label: 'پایان پژوهش 🎉',
              busy: _sending,
              onPressed: _submit,
            ),
          ),
        ],
      ),
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(28),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text(
              'قدم آخر: نظرت برای ما مهم است 💜',
              style: TextStyle(
                  fontSize: 20,
                  fontWeight: FontWeight.bold,
                  color: AppColors.navy),
            ),
            const SizedBox(height: 16),
            _slider('این تجربه چقدر انگیزه‌ات برای ادامه‌ی یادگیری را بیشتر کرد؟',
                _motivation, (v) => setState(() => _motivation = v)),
            _slider('یادآورهای شخصی چقدر برایت مفید بودند؟', _usefulness,
                (v) => setState(() => _usefulness = v)),
            _slider('کار کردن با سامانه چقدر راحت بود؟', _easeOfUse,
                (v) => setState(() => _easeOfUse = v),
                low: 'سخت', high: 'راحت'),
            _slider('تجربه‌ی کلی‌ات از این مطالعه چطور بود؟', _overall,
                (v) => setState(() => _overall = v),
                low: 'بد', high: 'عالی'),
            const SizedBox(height: 8),
            TextField(
              controller: _commentController,
              minLines: 3,
              maxLines: 5,
              decoration: InputDecoration(
                labelText: 'حرف یا پیشنهادی داری؟ (اختیاری)',
                filled: true,
                fillColor: Colors.white,
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: BorderSide.none,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
