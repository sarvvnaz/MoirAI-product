import 'package:flutter/material.dart';
import '../data/study_steps.dart';
import '../services/api_service.dart';
import 'measures_page.dart';
import '../services/flow_router.dart';
import '../theme/app_colors.dart';
import '../widgets/study_scaffold.dart';
import 'eft_chat_page.dart';

/// Research questionnaire step. Explanations are shown above the form,
/// every field is mandatory, and age is a dropdown from 18 to 25.
class BaselineProfilePage extends StatefulWidget {
  final int userId;
  const BaselineProfilePage({super.key, required this.userId});

  @override
  State<BaselineProfilePage> createState() => _BaselineProfilePageState();
}

class _BaselineProfilePageState extends State<BaselineProfilePage> {
  int? _age;
  String? _gender;
  String? _educationLevel;
  String? _studyField;
  String? _englishGoal;
  String? _englishLevel;
  String? _studyFrequency;

  bool _submitting = false;



  String? get _firstMissingField {
    if (_age == null) return 'سن';
    if (_gender == null) return 'جنسیت';
    if (_educationLevel == null) return 'مقطع تحصیلی';
    if (_studyField == null) return 'رشته یا زمینه';
    if (_englishGoal == null) return 'هدف یادگیری زبان';
    if (_englishLevel == null) return 'سطح زبان';
    if (_studyFrequency == null) return 'میزان مطالعه';
    return null;
  }

  Future<void> _submitProfile() async {
    final missing = _firstMissingField;
    if (missing != null) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('لطفاً «$missing» را هم تکمیل کن 🙂')),
      );
      return;
    }

    setState(() => _submitting = true);
    try {
      await ApiService.submitProfile({
        'age': _age,
        'gender': _gender,
        'education_level': _educationLevel,
        'study_field': _studyField,
        'english_goal': _englishGoal,
        'english_level': _englishLevel,
        'study_frequency': _studyFrequency,
      });
      if (!mounted) return;
      // Where next depends on the arm, and the ARM IS THE SERVER'S ANSWER —
      // asking it (rather than deciding here) means the route a participant
      // takes can never disagree with the group recorded against their data.
      // Control participants do no EFT chat, so they go straight on to the
      // extension setup that every session needs.
      final next = await FlowRouter.resolveNextScreen(widget.userId);
      if (!mounted) return;
      // Baseline measures come between the profile and the study proper:
      // future-self continuity and study intention must be recorded BEFORE
      // any intervention, or there is nothing to compare the closing
      // measurement against.
      Navigator.of(context).pushReplacement(
        MaterialPageRoute(
          builder: (_) => MeasuresPage(
            userId: widget.userId,
            timepoint: 'baseline',
            title: 'چند سوال کوتاه قبل از شروع',
            step: StudyStep.questionnaire,
            nextPage: () => next,
          ),
        ),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('خطا در ذخیره‌سازی: $e')),
      );
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  InputDecoration _decoration(String label) {
    return InputDecoration(
      labelText: label,
      filled: true,
      fillColor: Colors.white,
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: BorderSide.none,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return StudyScaffold(
      currentStep: StudyStep.questionnaire,
      bottomBar: Row(
        children: [
          const Spacer(),
          SizedBox(
            width: 150,
            child: StudyPrimaryButton(
              label: 'ادامه',
              busy: _submitting,
              onPressed: _submitProfile,
            ),
          ),
        ],
      ),
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(28),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // ── Explanations above the form ──
            const Text(
              'کمی از خودت بگو 📝',
              style: TextStyle(
                  fontSize: 22,
                  fontWeight: FontWeight.bold,
                  color: AppColors.navy),
            ),
       
            const SizedBox(height: 22),

            // ── Age: dropdown 18-25 ──
            DropdownButtonFormField<int>(
              initialValue: _age,
              decoration: _decoration('سن'),
              items: [
                for (int a = 18; a <= 25; a++)
                  DropdownMenuItem(value: a, child: Text('$a')),
              ],
              onChanged: (v) => setState(() => _age = v),
            ),
            const SizedBox(height: 12),
            DropdownButtonFormField<String>(
              initialValue: _gender,
              decoration: _decoration('جنسیت'),
              items: const [
                DropdownMenuItem(value: 'زن', child: Text('زن')),
                DropdownMenuItem(value: 'مرد', child: Text('مرد')),
                DropdownMenuItem(
                    value: 'ترجیح می‌دهم نگویم',
                    child: Text('ترجیح می‌دهم نگویم')),
              ],
              onChanged: (v) => setState(() => _gender = v),
            ),
            const SizedBox(height: 12),
            DropdownButtonFormField<String>(
              initialValue: _educationLevel,
              decoration: _decoration('مقطع تحصیلی'),
              items: const [
                DropdownMenuItem(value: 'دیپلم', child: Text('دیپلم')),
                DropdownMenuItem(value: 'کارشناسی', child: Text('کارشناسی')),
                DropdownMenuItem(
                    value: 'کارشناسی ارشد', child: Text('کارشناسی ارشد')),
                DropdownMenuItem(value: 'دکترا', child: Text('دکترا')),
                DropdownMenuItem(value: 'سایر', child: Text('سایر')),
              ],
              onChanged: (v) => setState(() => _educationLevel = v),
            ),
            const SizedBox(height: 12),
            DropdownButtonFormField<String>(
              initialValue: _studyField,
              decoration: _decoration('رشته یا زمینهٔ تحصیلی/کاری'),
              items: const [
                DropdownMenuItem(value: 'مهندسی کامپیوتر/برق',child: Text('مهندسی کامپیوتر/برق')),
                DropdownMenuItem(value: 'سایر رشته‌های مهندسی', child: Text('سایر رشته‌های مهندسی')),
                DropdownMenuItem(value: 'سایر', child: Text('سایر')),
              ],
              onChanged: (v) => setState(() => _studyField = v),
            ),
            const SizedBox(height: 12),
            DropdownButtonFormField<String>(
              initialValue: _englishGoal,
              decoration: _decoration('هدف یادگیری زبان'),
              items: const [
                DropdownMenuItem(value: 'IELTS', child: Text('آیلتس')),
                DropdownMenuItem(value: 'TOEFL', child: Text('تافل')),
                DropdownMenuItem(
                    value: 'General English', child: Text('یادگیری عمومی')),
                DropdownMenuItem(value: 'Other', child: Text('سایر')),
              ],
              onChanged: (v) => setState(() => _englishGoal = v),
            ),
            const SizedBox(height: 12),
            DropdownButtonFormField<String>(
              initialValue: _englishLevel,
              decoration: _decoration('سطح کنونی زبان انگلیسی'),
              items: const [
                DropdownMenuItem(value: 'Beginner', child: Text('مبتدی')),
                DropdownMenuItem(value: 'Intermediate', child: Text('متوسط')),
                DropdownMenuItem(value: 'Advanced', child: Text('پیشرفته')),
              ],
              onChanged: (v) => setState(() => _englishLevel = v),
            ),
            const SizedBox(height: 12),
            DropdownButtonFormField<String>(
              initialValue: _studyFrequency,
              decoration: _decoration('میزان مطالعه‌ی زبان در هفته'),
              items: const [
                DropdownMenuItem(
                    value: 'none', child: Text('مطالعه نمی‌کنم')),
                DropdownMenuItem(
                    value: '0-1h', child: Text('کمتر از ۱ ساعت')),
                DropdownMenuItem(value: '1-2h', child: Text('۱ تا ۲ ساعت')),
                DropdownMenuItem(
                    value: '2h+', child: Text('بیش از ۲ ساعت')),
              ],
              onChanged: (v) => setState(() => _studyFrequency = v),
            ),
          ],
        ),
      ),
    );
  }
}
