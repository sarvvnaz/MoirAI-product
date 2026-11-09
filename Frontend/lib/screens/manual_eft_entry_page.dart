import '../l10n/app_language.dart';
import 'package:flutter/material.dart';
import '../data/study_steps.dart';
import '../services/api_service.dart';
import '../theme/app_colors.dart';
import '../widgets/study_scaffold.dart';
import 'prepare_page.dart';

/// Manual fallback for the EFT chat: the same 7 questions as plain text
/// boxes, for participants the chatbot fails (it stalls, misunderstands
/// them, or they simply prefer typing).
///
/// The two paths are MUTUALLY EXCLUSIVE and the first submission wins:
///   - reached from the chat page only while the chat is unsubmitted;
///   - «بازگشت به گفتگو» returns to the still-live chat (pop, so the
///     conversation keeps its messages);
///   - submitting here is FINAL — the chat is closed afterwards (enforced
///     by the backend too), so the stack is cleared on the way out.
class ManualEftEntryPage extends StatefulWidget {
  final int userId;
  const ManualEftEntryPage({super.key, required this.userId});

  @override
  State<ManualEftEntryPage> createState() => _ManualEftEntryPageState();
}

class _ManualEftEntryPageState extends State<ManualEftEntryPage> {
  /// Keys MUST match the backend question keys (eft_chat_service_v2.QUESTIONS).
  static const List<_ManualQuestion> _questions = [
    _ManualQuestion(
      key: 'goal',
      label: '۱. هدف بلندمدتت چیه؟',
      hint: 'مثلاً پیشرفت در کار، تحصیل، یا یک پروژه‌ی شخصی',
    ),
    _ManualQuestion(
      key: 'where',
      label: '۲. اون لحظه که به هدفت رسیدی، دقیقاً کجایی؟',
      hint: 'شهر و مکان رو دقیق بگو — انگار همین الان اونجایی',
    ),
    _ManualQuestion(
      key: 'when',
      label: '۳. اون لحظه کِی اتفاق می‌افته؟',
      hint: 'چند ماه یا چند سال دیگه؟ چه فصلی؟ صبح یا عصر؟',
    ),
    _ManualQuestion(
      key: 'action',
      label: '۴. توی اون لحظه داری چه کاری می‌کنی؟',
      hint: 'مثلاً حرف می‌زنی، ارائه می‌دی، چیزی می‌خونی یا می‌نویسی',
    ),
    _ManualQuestion(
      key: 'objects',
      label: '۵. دور و برت چه چیزهایی می‌بینی؟',
      hint: 'چند تا چیز رو نام ببر — مثلاً میز، لپ‌تاپ، پنجره، درخت',
    ),
    _ManualQuestion(
      key: 'who',
      label: '۶. تنهایی یا کسی باهاته؟',
      hint: 'مثلاً دوست، همکار، استاد یا خانواده',
    ),
    _ManualQuestion(
      key: 'feeling',
      label: '۷. اون لحظه چه حس خوبی داری؟',
      hint: 'مثلاً آرامش، غرور، اعتماد به نفس یا هیجان',
    ),
  ];

  late final Map<String, TextEditingController> _controllers = {
    for (final q in _questions) q.key: TextEditingController(),
  };

  bool _submitting = false;
  String? _error;

  @override
  void dispose() {
    for (final c in _controllers.values) {
      c.dispose();
    }
    super.dispose();
  }

  bool get _allFilled =>
      _controllers.values.every((c) => c.text.trim().isNotEmpty);

  Future<void> _submit() async {
    if (!_allFilled || _submitting) return;

    // Submitting is irreversible (the chat closes for good) — confirm first.
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => Directionality(
        textDirection: AppLanguage.of(context).direction,
        child: AlertDialog(
          backgroundColor: Colors.white,
          shape:
              RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
          title: const AppText('ثبت نهایی پاسخ‌ها؟',
              style: TextStyle(color: AppColors.navy, fontSize: 18)),
          content: const AppText(
            'بعد از ثبت، دیگه نمی‌تونی به گفتگو برگردی و از اون راه ادامه '
            'بدی. اگه هنوز می‌خوای گفتگو رو امتحان کنی، «بازگشت» رو بزن.',
            style: TextStyle(fontSize: 14.5, height: 1.9, color: AppColors.navy),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(ctx).pop(false),
              child: const AppText('بازگشت',
                  style: TextStyle(color: AppColors.navy)),
            ),
            ElevatedButton(
              style: ElevatedButton.styleFrom(
                backgroundColor: AppColors.purple,
                shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(10)),
              ),
              onPressed: () => Navigator.of(ctx).pop(true),
              child: const AppText('بله، ثبت کن',
                  style: TextStyle(color: Colors.white)),
            ),
          ],
        ),
      ),
    );
    if (confirmed != true || !mounted) return;

    setState(() {
      _submitting = true;
      _error = null;
    });

    final answers = {
      for (final q in _questions) q.key: _controllers[q.key]!.text.trim(),
    };
    final error = await ApiService.submitManualEpisode(answers);

    if (!mounted) return;
    setState(() => _submitting = false);
    if (error != null) {
      setState(() => _error = error);
      return;
    }

    // Submitted → the chat is closed. Clear the stack so it can't be
    // reached with the back button.
    Navigator.of(context).pushAndRemoveUntil(
      MaterialPageRoute(builder: (_) => PreparePage(userId: widget.userId)),
      (route) => false,
    );
  }

  @override
  Widget build(BuildContext context) {
    return StudyScaffold(
      currentStep: StudyStep.chat,
      bottomBar: Row(
        children: [
          TextButton.icon(
            onPressed: _submitting ? null : () => Navigator.of(context).pop(),
            icon: const Icon(Icons.arrow_forward_rounded,
                size: 18, color: AppColors.purple),
            label: const AppText('بازگشت به گفتگو',
                style: TextStyle(color: AppColors.purple, fontSize: 13.5)),
          ),
          const Spacer(),
          if (!_allFilled)
            const Padding(
              padding: EdgeInsets.only(left: 12),
              child: AppText('همه‌ی ۷ سوال را کامل کن',
                  style: TextStyle(fontSize: 12.5, color: AppColors.navy)),
            ),
          SizedBox(
            width: 150,
            child: StudyPrimaryButton(
              label: 'ثبت نهایی',
              busy: _submitting,
              onPressed: _allFilled ? _submit : null,
            ),
          ),
        ],
      ),
      child: SingleChildScrollView(
        padding: const EdgeInsets.fromLTRB(28, 24, 28, 20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const AppText(
              'نوشتن دستی پاسخ‌ها ✍️',
              style: TextStyle(
                  fontSize: 21,
                  fontWeight: FontWeight.bold,
                  color: AppColors.navy),
            ),
            const SizedBox(height: 8),
            const AppText(
              'همون ۷ سوال گفتگو، این بار با جای خالی برای نوشتن. هر چی '
              'دقیق‌تر بنویسی، تصویرت شخصی‌تر می‌شه. اگه هنوز همه‌ی جزئیات '
              'رو نمی‌دونی اشکالی نداره — همون چیزی که به ذهنت می‌رسه کافیه.',
              style:
                  TextStyle(fontSize: 14, height: 1.9, color: AppColors.navy),
            ),
            const SizedBox(height: 20),
            for (final q in _questions) _field(q),
            if (_error != null) ...[
              const SizedBox(height: 4),
              AppText(_error!,
                  style: const TextStyle(
                      fontSize: 13, color: Colors.redAccent, height: 1.7)),
            ],
          ],
        ),
      ),
    );
  }

  Widget _field(_ManualQuestion q) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 18),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          AppText(
            q.label,
            style: const TextStyle(
                fontSize: 15,
                fontWeight: FontWeight.w600,
                color: AppColors.navy),
          ),
          const SizedBox(height: 8),
          TextField(
            controller: _controllers[q.key],
            enabled: !_submitting,
            minLines: 2,
            maxLines: 4,
            textInputAction: TextInputAction.newline,
            // Rebuilds so the submit button enables as soon as all 7 fill.
            onChanged: (_) => setState(() {}),
            style: const TextStyle(fontSize: 14.5, height: 1.7),
            decoration: InputDecoration(
              hintText: tr(q.hint, context),
              hintStyle: TextStyle(
                  fontSize: 13, color: AppColors.navy.withOpacity(0.45)),
              filled: true,
              fillColor: Colors.white,
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(12),
                borderSide: BorderSide.none,
              ),
              contentPadding:
                  const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
            ),
          ),
        ],
      ),
    );
  }
}

class _ManualQuestion {
  final String key;
  final String label;
  final String hint;
  const _ManualQuestion(
      {required this.key, required this.label, required this.hint});
}
