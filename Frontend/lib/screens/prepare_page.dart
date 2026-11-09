import '../l10n/app_language.dart';
import 'package:flutter/material.dart';
import '../data/study_steps.dart';
import '../services/api_service.dart';
import '../theme/app_colors.dart';
import '../widgets/study_scaffold.dart';
import '../services/flow_router.dart';

/// Preparation step: while the participant's 3 reminder images + notes are
/// generated from their confirmed EFT episode, they answer feedback about
/// the chatbot / imagining experience with dragging bars (sliders).
class PreparePage extends StatefulWidget {
  final int userId;
  const PreparePage({super.key, required this.userId});

  @override
  State<PreparePage> createState() => _PreparePageState();
}

class _PreparePageState extends State<PreparePage> {
  // Feedback sliders (1..7), start unset (null) so we can detect skipping.
  double? _vividness;
  double? _ease;
  double? _connection;
  double? _chatExperience;

  bool _sending = false;
  bool _savingFeedback = false;
  bool _feedbackSaved = false;
  String? _feedbackError;

  // Real reminder generation status. The continue button is gated on these:
  // entering a study session without a reminder image means the participant
  // sees no intervention, and the session is unusable as data.
  bool _generating = true;
  bool _generationFailed = false;
  int _retryCount = 0;

  /// How long to wait for the image before letting them through with the
  /// generic one. Image generation regularly runs 30-60s and occasionally
  /// longer, so this is minutes, not seconds — the previous budget expired
  /// while the picture was still being drawn, and every participant fell
  /// through to the fallback.
  static const Duration _generationBudget = Duration(minutes: 4);

  /// Gap between readiness checks. Cheap DB lookups, not generation.
  static const Duration _pollInterval = Duration(seconds: 5);

  @override
  void initState() {
    super.initState();
    _prepareReminderPipeline();
  }

  /// Generates the personalized reminder image + cue from the participant's
  /// confirmed EFT episode, and RETRIES until the server confirms one exists.
  ///
  /// The retry loop is the gate's engine: `_generating` blocks the continue
  /// button, so this must reach a definite ready-or-failed answer rather than
  /// leaving the participant on a dead screen. Generation takes a while and
  /// the single call can time out with the image still landing server-side,
  /// which is why readiness is confirmed by polling the server instead of
  /// trusting this one response.
  Future<void> _prepareReminderPipeline() async {
    setState(() {
      _generating = true;
      _generationFailed = false;
    });

    // Kick generation off ONCE. Retrying this call was the bug: each retry
    // started another image job while the first was still running, so the
    // server ran duplicate generations in parallel and none of them had
    // finished before the attempts ran out.
    //
    // One highly-relevant image (rotation of 3 disabled — extra angles
    // produced unsettling/irrelevant results). Bump back up only if needed.
    final body = await ApiService.generateReminderSet(count: 1);
    if (!mounted) return;

    final assets = (body?['assets'] as List?)?.cast<Map<String, dynamic>>();
    if (assets != null && assets.isNotEmpty) {
      setState(() {
        _generating = false;
        _generationFailed = false;
      });
      return;
    }

    // A completed request with no generated image is a failure, not a pending job.
    if (body != null && body['generated'] == false) {
      setState(() {
        _generating = false;
        _generationFailed = true;
      });
      return;
    }

    // The request came back empty or timed out — but the image may still be
    // landing server-side, so the answer comes from polling the server rather
    // than from this one response.
    final deadline = DateTime.now().add(_generationBudget);
    var checks = 0;
    while (DateTime.now().isBefore(deadline)) {
      await Future.delayed(_pollInterval);
      if (!mounted) return;

      if (await ApiService.isReminderReady()) {
        if (!mounted) return;
        setState(() {
          _generating = false;
          _generationFailed = false;
        });
        return;
      }
      if (!mounted) return;
      setState(() => _retryCount = ++checks);
    }

    // Budget spent. Let them through on the generic reminder rather than
    // stranding them — a degraded session is recoverable, a participant stuck
    // on a dead screen is not.
    if (!mounted) return;
    setState(() {
      _generating = false;
      _generationFailed = true;
    });
  }

  Future<void> _saveFeedback() async {
    if (_chatExperience == null || _savingFeedback || _feedbackSaved) return;
    setState(() {
      _savingFeedback = true;
      _feedbackError = null;
    });
    try {
      await ApiService.saveExperienceRating(_chatExperience!.round());
      if (mounted) setState(() => _feedbackSaved = true);
    } catch (_) {
      if (mounted)
        setState(() => _feedbackError = 'ثبت نشد؛ دوباره امتحان کن.');
    } finally {
      if (mounted) setState(() => _savingFeedback = false);
    }
  }

  Future<void> _goNext() async {
    if (_savingFeedback) return;
    Navigator.of(context).pushReplacement(
      MaterialPageRoute(builder: (_) => FlowGate(userId: widget.userId)),
    );
  }

  Widget _slider(
    String label,
    double? value,
    ValueChanged<double> onChanged, {
    String low = 'کم',
    String high = 'زیاد',
  }) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        AppText(
          label,
          style: const TextStyle(
            fontSize: 15,
            fontWeight: FontWeight.w600,
            color: AppColors.navy,
          ),
        ),
        Row(
          children: [
            AppText(
              low,
              style: TextStyle(
                fontSize: 12,
                color: AppColors.navy.withOpacity(0.6),
              ),
            ),
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
            AppText(
              high,
              style: TextStyle(
                fontSize: 12,
                color: AppColors.navy.withOpacity(0.6),
              ),
            ),
          ],
        ),
        const SizedBox(height: 6),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    return StudyScaffold(
      currentStep: StudyStep.prepare,
      bottomBar: Row(
        children: [
          if (_generating)
            Expanded(
              child: AppText(
                _retryCount == 0
                    ? 'در حال ساختن تصویر آینده‌ات... چند لحظه صبر کن 🌱'
                    : 'هنوز داریم تلاش می‌کنیم... (تلاش ${_retryCount + 1})',
                style: TextStyle(
                  fontSize: 13,
                  color: AppColors.navy.withOpacity(0.75),
                ),
              ),
            )
          else
            const Spacer(),
          SizedBox(
            width: 190,
            child: StudyPrimaryButton(
              label: _generationFailed ? 'تلاش دوباره' : 'ادامه',
              busy: _sending,
              // NOT gated on the image. Generation runs server-side and keeps
              // going after this page is left, so making people sit here
              // watching a spinner buys nothing — they can install the
              // extension while it finishes. The gate lives on the extension
              // page instead, which is the last hop into a session.
              onPressed: _sending || _savingFeedback || _generating
                  ? null
                  : (_generationFailed ? _prepareReminderPipeline : _goNext),
            ),
          ),
        ],
      ),
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(28),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // ── Generation status (real) ──
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(14),
              ),
              child: Row(
                children: [
                  // No preview of the finished image: seeing it here would
                  // spend the participant's first reaction to it on a
                  // thumbnail, and that first encounter during a session is
                  // the thing being measured.
                  if (_generating)
                    const SizedBox(
                      width: 26,
                      height: 26,
                      child: CircularProgressIndicator(
                        color: AppColors.mint,
                        strokeWidth: 3,
                      ),
                    )
                  else if (_generationFailed)
                    const Icon(
                      Icons.info_outline,
                      color: AppColors.purple,
                      size: 26,
                    )
                  else
                    const Icon(
                      Icons.check_circle_rounded,
                      color: AppColors.mint,
                      size: 26,
                    ),
                  const SizedBox(width: 14),
                  Expanded(
                    child: AppText(
                      _generating
                          ? 'در همین لحظه، یادآورهای شخصی تو در حال ساخته شدن هستند... 🎨'
                          : (_generationFailed
                                ? 'ساخت یادآورها الان جواب نداد؛ نگران نباش، یک یادآور پیش‌فرض جایگزینش شد.'
                                : 'یادآورهای شخصی‌ات آماده‌ان ✅'),
                      style: const TextStyle(
                        fontSize: 14.5,
                        height: 1.7,
                        color: AppColors.navy,
                      ),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 24),
            const AppText(
              'گفتگو چطور بود؟',
              style: TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.bold,
                color: AppColors.navy,
              ),
            ),
            const SizedBox(height: 6),
            const AppText('اختیاری · ۱ ضعیف، ۵ عالی'),
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                for (int rating = 1; rating <= 5; rating++)
                  ChoiceChip(
                    label: AppText('$rating'),
                    selected: _chatExperience == rating,
                    onSelected: _savingFeedback || _feedbackSaved
                        ? null
                        : (_) => setState(
                            () => _chatExperience = rating.toDouble(),
                          ),
                  ),
              ],
            ),
            const SizedBox(height: 10),
            Align(
              alignment: AlignmentDirectional.centerStart,
              child: TextButton(
                onPressed:
                    _chatExperience == null || _savingFeedback || _feedbackSaved
                    ? null
                    : _saveFeedback,
                child: AppText(
                  _feedbackSaved
                      ? 'ثبت شد، ممنون!'
                      : _savingFeedback
                      ? 'در حال ثبت…'
                      : 'ثبت نظر',
                ),
              ),
            ),
            if (_feedbackError != null)
              AppText(
                _feedbackError!,
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
            /* Research feedback questions paused.
            const SizedBox(height: 16),

            const AppText(
              'تا آماده می‌شوند، بگو تجربه‌ات چطور بود 💭',
              style: TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.bold,
                  color: AppColors.navy),
            ),
            const SizedBox(height: 16),
            // Additional research feedback
            _slider('تصویری که از آینده‌ات ساختی چقدر واضح و زنده بود؟',
                _vividness, (v) => setState(() => _vividness = v)),
            _slider('تصور کردن آن لحظه چقدر برایت آسان بود؟', _ease,
                (v) => setState(() => _ease = v),
                low: 'سخت', high: 'آسان'),
            _slider('چقدر با «خودِ آینده‌ات» احساس نزدیکی کردی؟', _connection,
                (v) => setState(() => _connection = v)),

            _slider('گفتگو با راهنما چطور بود؟', _chatExperience,
                (v) => setState(() => _chatExperience = v),
                low: 'ضعیف', high: 'عالی'),
            */
          ],
        ),
      ),
    );
  }
}
