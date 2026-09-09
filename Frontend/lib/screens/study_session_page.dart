import 'dart:async';
import 'package:flutter/material.dart';
import '../data/quiz_questions.dart';
import '../data/readings.dart';
import '../data/study_steps.dart';
import '../services/api_service.dart';
import '../services/idle_detector.dart';
import '../theme/app_colors.dart';
import '../widgets/study_scaffold.dart';
// The closing measure is the final feedback page again — the IMMS/TAM
// kept in the codebase so the old measures can be restored.
import 'final_feedback_page.dart';
import 'measures_page.dart';

/// The study session step:
///  1. A 5-second breathing countdown with friendly, no-pressure framing.
///  2. The reading PDF with quiz questions below it in one scroll (no timer).
///  3. Submitting the quiz finishes the session → offer an optional second
///     session, otherwise continue to final feedback.
///
/// Idle (90s) and tab-switch detection run during the session (work step 7:
/// detection only — persistence comes later).
class StudySessionPage extends StatefulWidget {
  final int userId;
  const StudySessionPage({super.key, required this.userId});

  @override
  State<StudySessionPage> createState() => _StudySessionPageState();
}

class _StudySessionPageState extends State<StudySessionPage> {
  // TODO(pre-pilot): restore to 90s for the real study. 10s for debugging.
  static const Duration idleThreshold = Duration(seconds: 10);

  // ── breathing countdown ──
  int _countdown = 5;
  bool _inCountdown = true;
  Timer? _countdownTimer;

  /// Time allowed per reading part. When it runs out the participant is
  /// moved on automatically — they can also skip forward at any moment.
  static const Duration readingTimeLimit = Duration(minutes: 20);

  // ── session state ──
  int _sessionNumber = 1;
  int? _sessionId;
  final Map<String, int> _answers = {};
  // Typed answers for IELTS summary-completion ("ONE WORD ONLY") items.
  final Map<String, TextEditingController> _gapControllers = {};
  bool _submitting = false;
  bool _finishing = false;

  // ── 25-minute part timer ──
  DateTime? _readingStartedAt;
  Duration _remaining = readingTimeLimit;
  Timer? _partTimer;

  /// Seconds spent on this reading part so far (0 before it starts).
  int get _elapsedSeconds => _readingStartedAt == null
      ? 0
      : DateTime.now().difference(_readingStartedAt!).inSeconds;

  TextEditingController _gapController(String id) =>
      _gapControllers.putIfAbsent(id, () => TextEditingController());

  // ── in-app idle reminder (steps 9-10) ──
  // The full set (up to 3 images); overlays rotate through it.
  List<Map<String, dynamic>> _reminderSet = [];
  int _reminderIdx = 0;
  String? _reminderImageUrl;
  String? _reminderCue;
  bool _showIdleReminder = false;
  Timer? _idleReminderTimer;

  // Re-pushes the session flag + token to the extension during the session,
  // so an extension that was (re)loaded after session start still gets armed.
  Timer? _extensionHeartbeat;

  /// Advances the rotation and sets the current image/cue.
  bool _rotateReminder() {
    if (_reminderSet.isEmpty) return false;
    final asset = _reminderSet[_reminderIdx % _reminderSet.length];
    _reminderIdx++;
    final raw = (asset['image_url'] as String?) ?? '';
    if (raw.isEmpty) return false;
    _reminderImageUrl = ApiService.resolveBackendUrl(raw);
    _reminderCue = asset['cue'] as String?;
    return true;
  }

  @override
  void initState() {
    super.initState();
    _startCountdown();
  }

  @override
  void dispose() {
    _countdownTimer?.cancel();
    _idleReminderTimer?.cancel();
    _extensionHeartbeat?.cancel();
    _partTimer?.cancel();
    for (final c in _gapControllers.values) {
      c.dispose();
    }
    // Deactivate extension reminders if the participant leaves mid-session.
    ApiService.notifyExtensionSessionState(false);
    super.dispose();
  }

  void _startCountdown() {
    setState(() {
      _inCountdown = true;
      _countdown = 5;
    });
    _countdownTimer?.cancel();
    _countdownTimer = Timer.periodic(const Duration(seconds: 1), (t) async {
      if (!mounted) return;
      if (_countdown <= 1) {
        t.cancel();
        await _startSession();
        if (mounted) setState(() => _inCountdown = false);
      } else {
        setState(() => _countdown--);
      }
    });
  }

  Future<void> _startSession() async {
    try {
      final info = await ApiService.startSession();
      if (info != null) {
        _sessionId = (info['session_id'] as num?)?.toInt();
        _sessionNumber = (info['session_number'] as num?)?.toInt() ?? 1;
      }
    } catch (_) {
      // Session tracking must never block the study.
    }

    // Step 9: activate the extension only for the duration of the session
    // (it prefetches + caches the reminder image on this signal).
    try {
      final ok = await ApiService.notifyExtensionSessionState(true);
      debugPrint('🧩 extension session-start signal: $ok');
    } catch (_) {}
    // A one-shot signal is lost if the extension is (re)installed after
    // session start — its storage comes back empty and it stays silent.
    // The heartbeat re-arms it within 20s for the rest of the session.
    _extensionHeartbeat?.cancel();
    _extensionHeartbeat =
        Timer.periodic(const Duration(seconds: 20), (_) async {
      try {
        await ApiService.notifyExtensionSessionState(true);
      } catch (_) {}
    });

    _startPartTimer();

    // Fetch the reminder set for the in-app idle overlay (rotates).
    try {
      final set = await ApiService.getReminderSet();
      if (mounted && set.isNotEmpty) {
        setState(() {
          _reminderSet = set;
          _rotateReminder();
        });
        debugPrint('🖼 in-app reminder set ready: ${set.length} asset(s)');
      }
    } catch (e) {
      debugPrint('⚠️ could not fetch in-app reminder set: $e');
    }
  }

  /// Step 9: idle for 90s → show the participant's EFT image inside the app.
  /// Self-contained: if the reminder wasn't loaded at session start, it is
  /// fetched here — the in-app overlay never depends on the extension.
  Future<void> _onIdle() async {
    if (!mounted || _showIdleReminder) return;

    if (_reminderSet.isEmpty) {
      debugPrint('🔔 idle fired but reminder set not loaded — fetching now');
      try {
        _reminderSet = await ApiService.getReminderSet();
      } catch (e) {
        debugPrint('⚠️ reminder fetch on idle failed: $e');
      }
      if (_reminderSet.isEmpty) {
        debugPrint('⚠️ no reminder available — in-app overlay skipped');
        return;
      }
    }
    // Rotate to the next image in the set for this trigger.
    if (!_rotateReminder()) return;

    if (!mounted) return;
    setState(() => _showIdleReminder = true);
    debugPrint('🔔 [detected] in-app idle reminder shown');
    // Step 11: one research event row per idle trigger, written immediately.
    ApiService.researchTrigger('idle', reminderShown: true);
    _idleReminderTimer?.cancel();
    _idleReminderTimer =
        Timer(const Duration(seconds: 7), () => _dismissIdleReminder());
  }

  void _dismissIdleReminder({bool tapped = false}) {
    _idleReminderTimer?.cancel();
    if (mounted && _showIdleReminder) {
      setState(() => _showIdleReminder = false);
      if (tapped) {
        // Tapping the overlay away counts as an explicit dismissal + return.
        ApiService.researchReturn(dismissed: true);
      }
    }
  }

  /// Starts the 25-minute clock for this reading part. When it expires the
  /// participant is carried on automatically (nothing is lost — whatever
  /// they answered is submitted and the time spent is logged).
  void _startPartTimer() {
    _readingStartedAt = DateTime.now();
    _partTimer?.cancel();
    setState(() => _remaining = readingTimeLimit);
    _partTimer = Timer.periodic(const Duration(seconds: 1), (t) {
      if (!mounted) return;
      final left = readingTimeLimit - Duration(seconds: _elapsedSeconds);
      if (left <= Duration.zero) {
        t.cancel();
        setState(() => _remaining = Duration.zero);
        _finishPart('time_up');
      } else {
        setState(() => _remaining = left);
      }
    });
  }

  /// Ends the reading part and moves on. [reason] is one of
  /// 'submitted' | 'skipped' | 'time_up' and is recorded with the elapsed
  /// time, so analysis can tell a finished part from an abandoned one.
  Future<void> _finishPart(String reason) async {
    if (_finishing) return;
    _finishing = true;
    _partTimer?.cancel();

    final seconds = _elapsedSeconds;
    final answered = _questions.where(_isAnswered).length;

    try {
      await ApiService.logEvent(widget.userId, 'reading_part_finished', {
        'session_number': _sessionNumber,
        'session_id': _sessionId,
        'reason': reason,
        'seconds_spent': seconds,
        'time_limit_seconds': readingTimeLimit.inSeconds,
        'questions_answered': answered,
        'questions_total': _questions.length,
      });
      await ApiService.endSession();
      await ApiService.researchSessionClosed();
    } catch (_) {
      // Logging must never trap the participant mid-study.
    }

    // Session over → extension reminders off (heartbeat first, so it can't
    // re-arm them afterwards).
    _extensionHeartbeat?.cancel();
    try {
      await ApiService.notifyExtensionSessionState(false);
    } catch (_) {}

    if (!mounted) return;
    _finishing = false;
    if (reason == 'time_up') {
      _showTimeUpDialog();
    } else {
      _askAnotherSession();
    }
  }

  void _showTimeUpDialog() {
    showDialog<void>(
      context: context,
      barrierDismissible: false,
      builder: (ctx) => Directionality(
        textDirection: TextDirection.rtl,
        child: AlertDialog(
          backgroundColor: Colors.white,
          shape:
              RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
          title: const Text('زمان این بخش تمام شد ⏱',
              style: TextStyle(color: AppColors.navy, fontSize: 19)),
          content: const Text(
            'دمت گرم! زمان این بخش تموم شد. بریم سراغ مرحله‌ی بعد.',
            style:
                TextStyle(fontSize: 15, height: 1.9, color: AppColors.navy),
          ),
          actions: [
            ElevatedButton(
              style: ElevatedButton.styleFrom(
                backgroundColor: AppColors.purple,
                shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(10)),
              ),
              onPressed: () {
                Navigator.of(ctx).pop();
                Navigator.of(context).pushReplacement(
                  MaterialPageRoute(
                    builder: (_) => MeasuresPage(
                      userId: widget.userId,
                      timepoint: _sessionNumber == 1 ? 'session1' : 'session2',
                      title: 'درباره‌ی یادآورهای این جلسه',
                      step: StudyStep.study,
                      nextPage: () => FinalFeedbackPage(userId: widget.userId),
                    ),
                  ),
                );
              },
              child: const Text('ادامه',
                  style: TextStyle(color: Colors.white)),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _skipPart() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => Directionality(
        textDirection: TextDirection.rtl,
        child: AlertDialog(
          backgroundColor: Colors.white,
          shape:
              RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
          title: const Text('می‌خوای بری؟',
              style: TextStyle(color: AppColors.navy, fontSize: 18)),
          content: const Text(
            '',
            style:
                TextStyle(fontSize: 14.5, height: 1.9, color: AppColors.navy),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(ctx).pop(false),
              child: const Text('می‌مونم',
                  style: TextStyle(color: AppColors.navy)),
            ),
            ElevatedButton(
              style: ElevatedButton.styleFrom(
                backgroundColor: AppColors.purple,
                shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(10)),
              ),
              onPressed: () => Navigator.of(ctx).pop(true),
              child: const Text('بله، کامل مطالعه کردم',
                  style: TextStyle(color: Colors.white)),
            ),
          ],
        ),
      ),
    );
    if (confirmed == true) await _finishPart('skipped');
  }

  bool _isAnswered(QuizQuestion q) => q.kind == QuestionKind.gap
      ? _gapController(q.id).text.trim().isNotEmpty
      : _answers.containsKey(q.id);

  /// Step 11: tab switch away from the study → trigger row.
  void _onFocusLost() {
    ApiService.researchTrigger('tab_switch');
  }

  /// Back at the reading (after idle activity resumes, or tab refocus).
  void _onFocusReturn() {
    _dismissIdleReminder();
    ApiService.researchReturn();
  }

  List<QuizQuestion> get _questions =>
      quizQuestionsBySession[_sessionNumber] ??
      quizQuestionsBySession[1] ??
      const [];

  ReadingPassage get _reading =>
      readingsBySession[_sessionNumber] ?? readingsBySession[1]!;

  /// Sessions escalate 1→3 in difficulty; after the third there is no
  /// harder material, so the "another session?" offer stops.
  static const int _maxSessions = 3;

  Future<void> _submitQuiz() async {
    final unanswered = _questions.where((q) => !_isAnswered(q));
    if (unanswered.isNotEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
            content: Text('لطفاً قبل از ادامه به همه‌ی سوالات پاسخ بده 🙂')),
      );
      return;
    }

    setState(() => _submitting = true);
    try {
      int correct = 0;
      for (final q in _questions) {
        final bool isCorrect;
        final Map<String, dynamic> detail = {
          'session_number': _sessionNumber,
          'question_id': q.id,
          'kind': q.kind.name,
        };
        if (q.kind == QuestionKind.gap) {
          final typed = _gapController(q.id).text.trim();
          isCorrect = q.isGapAnswerCorrect(typed);
          detail['typed_answer'] = typed;
          detail['expected_answer'] = q.correctText;
        } else {
          final selected = _answers[q.id]!;
          // correctIndex < 0 means the answer key isn't filled in yet.
          isCorrect = q.correctIndex >= 0 && selected == q.correctIndex;
          detail['selected_index'] = selected;
          detail['correct_index'] = q.correctIndex;
        }
        if (isCorrect) correct++;
        detail['is_correct'] = isCorrect;
        await ApiService.logEvent(widget.userId, 'quiz_answer', detail);
      }
      await ApiService.logEvent(widget.userId, 'quiz_completed', {
        'session_number': _sessionNumber,
        'score': correct,
        'total': _questions.length,
        'seconds_spent': _elapsedSeconds,
      });
    } catch (_) {
      // Logging failures must not trap the participant.
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
    if (!mounted) return;
    // Shared teardown: logs the time spent, closes the session and the
    // research window, and switches the extension reminders off.
    await _finishPart('submitted');
  }

  void _askAnotherSession() {
    // All readings done → no more sessions to offer.
    if (_sessionNumber >= _maxSessions) {
      Navigator.of(context).pushReplacement(
        MaterialPageRoute(
          builder: (_) => MeasuresPage(
                      userId: widget.userId,
                      timepoint: _sessionNumber == 1 ? 'session1' : 'session2',
                      title: 'درباره‌ی یادآورهای این جلسه',
                      step: StudyStep.study,
                      nextPage: () => FinalFeedbackPage(userId: widget.userId),
                    ),
        ),
      );
      return;
    }
    showDialog<void>(
      context: context,
      barrierDismissible: false,
      builder: (ctx) => Directionality(
        textDirection: TextDirection.rtl,
        child: AlertDialog(
          backgroundColor: Colors.white,
          shape:
              RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
          title: const Text('آفرین، این جلسه تمام شد 🎉',
              style: TextStyle(color: AppColors.navy, fontSize: 19)),
          content: const Text(
            'دوست داری یک جلسه‌ی مطالعه‌ی دیگر هم انجام بدهی؟ کاملاً اختیاری است.',
            style:
                TextStyle(fontSize: 15, height: 1.8, color: AppColors.navy),
          ),
          actions: [
            TextButton(
              onPressed: () {
                Navigator.of(ctx).pop();
                Navigator.of(context).pushReplacement(
                  MaterialPageRoute(
                    builder: (_) => MeasuresPage(
                      userId: widget.userId,
                      timepoint: _sessionNumber == 1 ? 'session1' : 'session2',
                      title: 'درباره‌ی یادآورهای این جلسه',
                      step: StudyStep.study,
                      nextPage: () => FinalFeedbackPage(userId: widget.userId),
                    ),
                  ),
                );
              },
              child: const Text('نه، برویم مرحله آخر',
                  style: TextStyle(color: AppColors.navy)),
            ),
            ElevatedButton(
              style: ElevatedButton.styleFrom(
                backgroundColor: AppColors.purple,
                shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(10)),
              ),
              onPressed: () {
                Navigator.of(ctx).pop();
                setState(() {
                  _answers.clear();
                });
                _startCountdown();
              },
              child: const Text('بله، یک جلسه دیگر',
                  style: TextStyle(color: Colors.white)),
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return StudyScaffold(
      currentStep: StudyStep.study,
      child: _inCountdown ? _buildCountdown() : _buildSession(),
    );
  }

  // ── 5-second breathing countdown ──
  Widget _buildCountdown() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            AnimatedSwitcher(
              duration: const Duration(milliseconds: 300),
              child: Text(
                '$_countdown',
                key: ValueKey(_countdown),
                style: const TextStyle(
                  fontSize: 72,
                  fontWeight: FontWeight.bold,
                  color: AppColors.purple,
                ),
              ),
            ),
            const SizedBox(height: 18),
            const Text(
              'یک نفس عمیق بکش... 🌬️',
              style: TextStyle(
                  fontSize: 22,
                  fontWeight: FontWeight.bold,
                  color: AppColors.navy),
            ),
            const SizedBox(height: 14),
            const Text(
              'حالا یک متن کوتاه انگلیسی می‌خونی و بعدش چند سوال جواب می‌دی.\n'
              'مثل همیشه‌ی خودت رفتار کن — اگه حواست پرت شد، اشکالی نداره!\n'
              'نه تمرکز کامل جایزه داره و نه پاسخ درست هدف ماست. راحت باش 🙂',
              textAlign: TextAlign.center,
              style: TextStyle(
                  fontSize: 15.5, height: 2.0, color: AppColors.navy),
            ),
          ],
        ),
      ),
    );
  }

  // ── PDF + quiz in one scroll ──
  Widget _buildSession() {
    return Stack(
      children: [
        _buildSessionContent(),
        if (_showIdleReminder && _reminderImageUrl != null)
          _buildIdleReminderOverlay(),
      ],
    );
  }

  /// Step 9: the in-app reminder overlay shown after 90s of inactivity.
  Widget _buildIdleReminderOverlay() {
    return Positioned.fill(
      child: GestureDetector(
        onTap: () => _dismissIdleReminder(tapped: true),
        child: Container(
          color: AppColors.navy.withOpacity(0.92),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              ClipRRect(
                borderRadius: BorderRadius.circular(16),
                child: Image.network(
                  _reminderImageUrl!,
                  width: 380,
                  fit: BoxFit.contain,
                  errorBuilder: (_, __, ___) => const SizedBox.shrink(),
                ),
              ),
              if ((_reminderCue ?? '').isNotEmpty) ...[
                const SizedBox(height: 18),
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 32),
                  child: Text(
                    _reminderCue!,
                    textAlign: TextAlign.center,
                    style: const TextStyle(
                      fontSize: 18,
                      height: 1.9,
                      color: AppColors.lavender,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
              ],
              const SizedBox(height: 16),
              Text(
                'برای ادامه ضربه بزن',
                style: TextStyle(
                    fontSize: 13, color: Colors.white.withOpacity(0.6)),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildSessionContent() {
    return IdleDetector(
      userId: widget.userId,
      idleThreshold: idleThreshold,
      onIdle: _onIdle,
      onFocusLost: _onFocusLost,
      onFocusReturn: _onFocusReturn,
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              'جلسه مطالعه ${_sessionNumber > 1 ? '$_sessionNumber از $_maxSessions ' : ''}📖',
              style: const TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.bold,
                  color: AppColors.navy),
            ),
            const SizedBox(height: 4),
            const Text(
              'متن را بخوان و بعد به سوالات پایین صفحه پاسخ بده.',
              style: TextStyle(fontSize: 13.5, color: AppColors.navy),
            ),
            const SizedBox(height: 12),
            // _buildTimeBanner(),
            // const SizedBox(height: 12),
            // Fixed-height reading pane (scrolls internally); the page
            // itself scrolls on to the questions below.
            Container(
              height: 460,
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(14),
              ),
              clipBehavior: Clip.antiAlias,
              child: Directionality(
                textDirection: TextDirection.ltr,
                child: Scrollbar(
                  thumbVisibility: true,
                  child: SingleChildScrollView(
                    padding: const EdgeInsets.fromLTRB(28, 24, 28, 32),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Reading Passage $_sessionNumber',
                          style: TextStyle(
                            fontSize: 12.5,
                            letterSpacing: 1.1,
                            fontWeight: FontWeight.w600,
                            color: AppColors.navy.withOpacity(0.55),
                          ),
                        ),
                        const SizedBox(height: 6),
                        Text(
                          _reading.title,
                          style: const TextStyle(
                            fontSize: 21,
                            fontWeight: FontWeight.bold,
                            color: AppColors.navy,
                            height: 1.4,
                          ),
                        ),
                        if (_reading.subtitle.isNotEmpty) ...[
                          const SizedBox(height: 6),
                          Text(
                            _reading.subtitle,
                            style: TextStyle(
                              fontSize: 14,
                              height: 1.6,
                              fontStyle: FontStyle.italic,
                              color: AppColors.navy.withOpacity(0.8),
                            ),
                          ),
                        ],
                        if (_reading.source.isNotEmpty) ...[
                          const SizedBox(height: 8),
                          Text(
                            'Source: ${_reading.source}',
                            style: TextStyle(
                              fontSize: 11.5,
                              height: 1.5,
                              color: AppColors.navy.withOpacity(0.5),
                            ),
                          ),
                        ],
                        const SizedBox(height: 10),
                        Text(
                          _reading.instructions,
                          style: TextStyle(
                            fontSize: 13,
                            height: 1.6,
                            fontStyle: FontStyle.italic,
                            color: AppColors.navy.withOpacity(0.75),
                          ),
                        ),
                        const Divider(height: 28),
                        SelectableText(
                          _reading.body.trim(),
                          style: const TextStyle(
                            fontSize: 15.5,
                            height: 1.85,
                            color: AppColors.navy,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
            const SizedBox(height: 24),
            const Text(
              'سوالات ✍️',
              style: TextStyle(
                  fontSize: 17,
                  fontWeight: FontWeight.bold,
                  color: AppColors.navy),
            ),
            const SizedBox(height: 8),
            ..._questions.map(_buildQuestion),
            const SizedBox(height: 10),
            StudyPrimaryButton(
              label: 'ثبت پاسخ‌ها و پایان جلسه',
              busy: _submitting,
              onPressed: _submitQuiz,
            ),
            const SizedBox(height: 10),
            Center(
              child: TextButton(
                onPressed: _submitting ? null : _skipPart,
                child: Text(
                  'رد کردن و رفتن به مرحله‌ی بعد ←',
                  style: TextStyle(
                    fontSize: 13,
                    color: AppColors.purple.withOpacity(0.85),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildQuestion(QuizQuestion q) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Directionality(
        textDirection: TextDirection.ltr,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (q.groupHeader.isNotEmpty) ...[
              Text(
                q.groupHeader,
                style: TextStyle(
                  fontSize: 13,
                  height: 1.7,
                  fontWeight: FontWeight.w600,
                  color: AppColors.purple.withOpacity(0.95),
                ),
              ),
              const Divider(height: 20),
            ],
            Text(
              q.prompt,
              style: const TextStyle(
                  fontSize: 15,
                  fontWeight: FontWeight.w600,
                  color: AppColors.navy),
            ),
            const SizedBox(height: 4),
            if (q.kind == QuestionKind.gap)
              // IELTS summary completion — ONE WORD ONLY, typed in.
              TextField(
                controller: _gapController(q.id),
                enabled: !_submitting,
                textDirection: TextDirection.ltr,
                onChanged: (_) => setState(() {}),
                style: const TextStyle(fontSize: 14.5),
                decoration: InputDecoration(
                  hintText: 'ONE WORD ONLY',
                  hintStyle: TextStyle(
                      fontSize: 13,
                      color: AppColors.navy.withOpacity(0.35)),
                  isDense: true,
                  filled: true,
                  fillColor: AppColors.lavender,
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(10),
                    borderSide: BorderSide.none,
                  ),
                  contentPadding: const EdgeInsets.symmetric(
                      horizontal: 12, vertical: 10),
                ),
              )
            else
              // Multiple choice / section matching (A–H) / person matching.
              ...List.generate(q.options.length, (i) {
                return RadioListTile<int>(
                  value: i,
                  groupValue: _answers[q.id],
                  onChanged: (v) => setState(() => _answers[q.id] = v!),
                  title:
                      Text(q.options[i], style: const TextStyle(fontSize: 14)),
                  activeColor: AppColors.purple,
                  dense: true,
                  contentPadding: EdgeInsets.zero,
                );
              }),
          ],
        ),
      ),
    );
  }

  /// The 25-minute notice + live countdown for this reading part.
//   Widget _buildTimeBanner() {
//     final m = _remaining.inMinutes;
//     final s = _remaining.inSeconds % 60;
//     final low = _remaining.inMinutes < 5;
//     return Container(
//       padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
//       decoration: BoxDecoration(
//         color: Colors.white,
//         borderRadius: BorderRadius.circular(12),
//         border: Border.all(
//             color: low
//                 ? Colors.redAccent.withOpacity(0.5)
//                 : AppColors.purple.withOpacity(0.25)),
//       ),
//       child: Row(
//         children: [
//           Icon(Icons.schedule_rounded,
//               size: 20, color: low ? Colors.redAccent : AppColors.purple),
//           const SizedBox(width: 10),
//           const Expanded(
//             child: Text(
//               '',
//               style: TextStyle(
//                   fontSize: 12.5, height: 1.8, color: AppColors.navy),
//             ),
//           ),
//           const SizedBox(width: 10),
//           // Directionality(
//           //   textDirection: TextDirection.ltr,
//           //   child: Text(
//           //     '${m.toString().padLeft(2, '0')}:${s.toString().padLeft(2, '0')}',
//           //     style: TextStyle(
//           //       fontSize: 18,
//           //       fontWeight: FontWeight.bold,
//           //       fontFeatures: const [FontFeature.tabularFigures()],
//           //       color: low ? Colors.redAccent : AppColors.navy,
//           //     ),
//           //   ),
//           // ),
//         ],
//       ),
//     );
//   }
 }
