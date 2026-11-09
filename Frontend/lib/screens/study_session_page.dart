import 'dart:async';
import 'dart:typed_data';
import 'pdf_upload_page.dart';
import 'package:syncfusion_flutter_pdfviewer/pdfviewer.dart';
import 'package:flutter/material.dart';
import '../data/quiz_questions.dart';
import '../data/readings.dart';
import '../data/study_steps.dart';
import '../services/api_service.dart';
import '../services/flow_router.dart';
import '../services/idle_detector.dart';
import '../services/study_config.dart';
import '../theme/app_colors.dart';
import '../widgets/exam_split_view.dart';
import '../widgets/study_shell_metrics.dart';
import '../widgets/study_scaffold.dart';
// The closing measure is the final feedback page again — the IMMS/TAM
// kept in the codebase so the old measures can be restored.
// import 'measures_page.dart';

/// The study session step:
///  1. A 5-second breathing countdown with friendly, no-pressure framing.
///  2. The reading PDF with quiz questions below it in one scroll (no timer).
///  3. Submitting the quiz finishes the session → offer an optional second
///     session, otherwise continue to final feedback.
///
/// Idle and tab-switch detection run during the session and ARE persisted:
/// they are outcome measures now, not incidental logging. The idle threshold
/// is a study parameter — see [StudyConfig].
class StudySessionPage extends StatefulWidget {
  final int userId;
  final Uint8List? pdfBytes;
  final String? pdfName;
  const StudySessionPage({super.key, required this.userId, this.pdfBytes, this.pdfName});

  @override
  State<StudySessionPage> createState() => _StudySessionPageState();
}

class _StudySessionPageState extends State<StudySessionPage> {
  /// Study parameter — see [StudyConfig]. Not to be edited here.
  static Duration get idleThreshold => StudyConfig.idleThreshold;

  // ── breathing countdown ──
  int _countdown = 5;
  bool _inCountdown = true;
  Timer? _countdownTimer;

  /// The reading window. One session, one window — see [StudyConfig].
  ///
  /// The countdown is deliberately VISIBLE: at this pace it is fidelity to
  /// real IELTS conditions, and the mild time pressure is what makes the task
  /// aversive enough for natural disengagement to occur at all. Without any
  /// pressure the primary measures have no variance to explain.
  static Duration get readingTimeLimit => StudyConfig.readingWindow;

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

  // ── the cue currently on screen ──
  // Set from the SERVER's grant, never chosen here. The server maps slot 1 to
  // asset 1 and slot 2 to asset 2, identically for every participant; a
  // client-side rotation used to pick as well, which is two sources of truth
  // for which stimulus a participant saw. When those disagree the export
  // records one and the participant saw the other, and nothing looks wrong.
  String? _reminderImageUrl;
  String? _reminderCue;
  bool _showIdleReminder = false;
  Timer? _idleReminderTimer;

  // Re-pushes the session flag + token to the extension during the session,
  // so an extension that was (re)loaded after session start still gets armed.
  Timer? _extensionHeartbeat;

  // ── scheduled cues ──
  // Polls the SERVER for whether a slot is due. The app never decides this:
  // once its tab is hidden the browser throttles these timers, which is
  // exactly the state where a cue matters most, so the extension covers that
  // case and this covers the visible case.
  Timer? _cuePoll;

  /// The corner card — the one new cue form. Shown when the slot opens while
  /// the participant is actively reading: non-blocking, so it reinforces the
  /// goal without breaking an active reading strategy.
  bool _showCornerCard = false;
  Timer? _cornerCardTimer;

  /// Delivery id of the cue currently on screen, for interaction reporting.
  int? _activeDeliveryId;

  /// True while a disengagement episode is open on the server, so start/end
  /// stay paired even if idle and tab-switch both fire.
  bool _episodeOpen = false;

  /// One controller per pane: the exam layout scrolls the passage and the
  /// questions independently, which is the point of the split view.
  final ScrollController _passageScroll = ScrollController();
  final ScrollController _questionScroll = ScrollController();

  /// Idle, but still on the study tab. Decides between the corner card and
  /// the existing centred overlay when a slot opens.
  bool _idleNow = false;

  /// The study tab is not in front. While this is true the cue belongs to the
  /// EXTENSION, and this client must not claim it: the app's timers keep
  /// firing (throttled) even when hidden, and a claim from here would be
  /// recorded as `active` — silently moving an off-tab cue into the wrong
  /// primary measure, where nothing about its value would look wrong.
  bool _awayFromTab = false;

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
    _cuePoll?.cancel();
    _cornerCardTimer?.cancel();
    _passageScroll.dispose();
    _questionScroll.dispose();
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

    // Opens the SERVER's clock for this reading window and schedules both
    // cues. Must happen before the poll starts, or the first few polls answer
    // "reading not started" for no reason.
    try {
      await ApiService.startReading();
    } catch (e) {
      debugPrint('⚠️ could not open the reading window: $e');
    }

    _startPartTimer();
    _startCuePolling();

    // Nothing is prefetched here on purpose. The cue arrives with the
    // server's grant, so there is no set to hold and no rotation to keep in
    // step with the server's own slot -> asset mapping.
  }

  // ──────────────────────────────────────────────────────────────────
  // Scheduled cues
  // ──────────────────────────────────────────────────────────────────

  /// Asks the server every few seconds whether a slot is open.
  ///
  /// Only while the tab is VISIBLE. A hidden tab is the extension's job, and
  /// polling from a throttled timer would produce cues that arrive late and
  /// are attributed to the wrong attentional state.
  void _startCuePolling() {
    _cuePoll?.cancel();
    _cuePoll = Timer.periodic(StudyConfig.cuePollInterval, (_) async {
      if (!mounted || _showCornerCard || _showIdleReminder) return;
      if (_awayFromTab) return; // the extension owns the off-tab case
      final due = await ApiService.cueDue();
      final slot = (due?['due_slot'] as num?)?.toInt();
      if (slot == null || !mounted) return;
      await _deliverScheduledCue();
    });
  }

  /// Claims the open slot and renders it in the form the current state calls
  /// for. The STATE decides the form — that is the whole point of the design:
  ///
  ///   active → corner card    (do not interrupt someone who is reading)
  ///   idle   → the existing centred overlay, unchanged
  ///
  /// The off-tab case never reaches here; the extension owns it.
  Future<void> _deliverScheduledCue() async {
    final state = _idleNow ? 'idle' : 'active';

    final grant = await ApiService.claimCue(state);
    if (grant == null || grant['granted'] != true || !mounted) return;

    final asset = (grant['asset'] as Map?) ?? const {};
    final raw = (asset['image_url'] as String?) ?? '';
    if (raw.isEmpty) {
      debugPrint('⚠️ cue granted with no image — nothing to show');
      return;
    }
    _reminderImageUrl = ApiService.resolveBackendUrl(raw);
    _reminderCue = asset['cue'] as String?;
    _activeDeliveryId = (grant['delivery_id'] as num?)?.toInt();

    setState(() {
      if (state == 'idle') {
        _showIdleReminder = true;
      } else {
        _showCornerCard = true;
      }
    });

    if (_activeDeliveryId != null) {
      await ApiService.cueShown(_activeDeliveryId!);
    }
    debugPrint('🔔 scheduled cue slot ${grant['slot']} shown as '
        '${grant['form']} (state=$state)');

    // The corner card is non-blocking, so it takes itself away. The idle
    // overlay keeps its existing dismissal behaviour.
    if (state == 'active') {
      _cornerCardTimer?.cancel();
      _cornerCardTimer = Timer(const Duration(seconds: 12), _dismissCornerCard);
    } else {
      _idleReminderTimer?.cancel();
      _idleReminderTimer =
          Timer(const Duration(seconds: 7), () => _dismissIdleReminder());
    }
  }

  void _dismissCornerCard({bool tapped = false}) {
    _cornerCardTimer?.cancel();
    if (!mounted || !_showCornerCard) return;
    setState(() => _showCornerCard = false);
    final id = _activeDeliveryId;
    if (id != null && tapped) {
      ApiService.cueInteraction(id, dismissed: true);
    }
  }

  void _dismissIdleReminder({bool tapped = false}) {
    _idleReminderTimer?.cancel();
    if (mounted && _showIdleReminder) {
      setState(() => _showIdleReminder = false);
      final id = _activeDeliveryId;
      if (id != null && tapped) {
        ApiService.cueInteraction(id, dismissed: true);
      }
    }
  }

  // ──────────────────────────────────────────────────────────────────
  // Disengagement telemetry — the OUTCOME measures
  // ──────────────────────────────────────────────────────────────────

  /// Idle no longer shows anything by itself. It opens an episode.
  ///
  /// That inversion is the redesign: under the old protocol a reminder fired
  /// because the participant disengaged, which made the cue impossible to use
  /// as a predictor of disengagement. Now the cue is on a fixed clock and
  /// this is simply the outcome being recorded.
  Future<void> _onIdle() async {
    if (!mounted) return;
    _idleNow = true;
    if (_episodeOpen) return;
    _episodeOpen = true;
    await ApiService.disengagementStart('idle');
  }

  /// Tab switch away from the study → an episode opens.
  void _onFocusLost() {
    _awayFromTab = true;
    if (_episodeOpen) return;
    _episodeOpen = true;
    ApiService.disengagementStart('tab_switch');
  }

  /// Back at the reading. Closes the episode, which is also where the server
  /// resolves return latency if a cue was delivered during the absence.
  void _onFocusReturn() {
    _dismissIdleReminder();
    _idleNow = false;
    _awayFromTab = false;
    if (!_episodeOpen) return;
    _episodeOpen = false;
    ApiService.disengagementEnd(endedBy: 'return');
  }

  /// Starts the 25-minute clock for this reading part. When it expires the
  /// participant is carried on automatically (nothing is lost — whatever
  /// they answered is submitted and the time spent is logged).
  void _startPartTimer() {
    // A personal PDF is not a timed exam.
    if (widget.pdfBytes != null) return;
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
    _cuePoll?.cancel();
    _cornerCardTimer?.cancel();

    final seconds = _elapsedSeconds;
    final answered = _questions.where(_isAnswered).length;

    try {
      await ApiService.logEvent(widget.userId, 'reading_part_finished', {
        'session_number': _sessionNumber,
        'session_id': _sessionId,
        'reason': reason,
        'seconds_spent': seconds,
        'time_limit_seconds': readingTimeLimit.inSeconds,
        if (widget.pdfBytes == null) 'questions_answered': answered,
        if (widget.pdfBytes == null) 'questions_total': _questions.length,
      });
      // Closes any open disengagement episode and writes off any slot that
      // never delivered. Without this an episode that ran to the end of the
      // session keeps a NULL duration and drops out of time-on-task —
      // biased in favour of whoever disengaged last.
      await ApiService.endReading();
      await ApiService.endSession();
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
      _goToPostTaskMeasures();
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
                    builder: (_) => FlowGate(userId: widget.userId),
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

  /// Every question in the session, in passage order.
  ///
  /// Ids are unique across passages (s1q*, s2q*), so concatenating is safe
  /// and the answer map stays keyed correctly.
  List<QuizQuestion> get _questions => [
        for (final id in StudyConfig.sessionPassages)
          ...(quizQuestionsBySession[id] ?? const []),
      ];

  /// The passages shown, in order, in one continuous scroll.
  List<ReadingPassage> get _readings => [
        for (final id in StudyConfig.sessionPassages)
          if (readingsBySession[id] != null) readingsBySession[id]!,
      ];

  ReadingPassage get _reading => _readings.isNotEmpty
      ? _readings.first
      : readingsBySession[1]!;

  /// ONE session. The protocol is a single 35-minute reading window with two
  /// scheduled cues; a second session would give those participants four,
  /// breaking the equal-dosage guarantee the design rests on.
  static const int _maxSessions = 1;

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

  /// One session, so there is never another to offer — this goes straight to
  /// the post-task battery. Kept as a single call site rather than inlined so
  /// the two exit paths (submitted, time_up) stay identical.
  /// One session, so there is never another to offer. Goes straight to the
  /// post-task battery.
  ///
  /// The "would you like another session?" offer is gone deliberately: a
  /// second session would give that participant four cues instead of two,
  /// and equal dosage across arms is the claim the whole redesign rests on.
  /// Hands the participant back to the server rather than naming the next
  /// screen here.
  ///
  /// Two things went wrong when this pushed the questionnaire directly. It
  /// sent the participant straight on to the old slider page afterwards,
  /// SKIPPING the open-ended feedback block entirely — three questions that
  /// simply never got asked. And it titled the page «درباره‌ی یادآورهای این
  /// جلسه», which announces that the study is about the reminders on a page
  /// whose FIRST items are the primary task-goal outcome. That outcome is
  /// asked before anything mentions reminders precisely so the participant
  /// does not yet know what is being studied; a title naming them gives it
  /// away before the first question is read.
  void _goToPostTaskMeasures() {
    Navigator.of(context).pushReplacement(
      MaterialPageRoute(builder: (_) => FlowGate(userId: widget.userId)),
    );
  }

  @override
  Widget build(BuildContext context) {
    return StudyScaffold(
      wide: true,
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
              'با ریتم خودت پیش برو.\n'
              ''
              'هر وقت خواستی، تمامش کن.',
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
        if (_showCornerCard && _reminderImageUrl != null) _buildCornerCard(),
      ],
    );
  }

  /// The corner card: the cue form for a participant who IS reading.
  ///
  /// Deliberately small, non-modal and top-aligned. It does not take focus,
  /// does not block scrolling and does not move the page, because the whole
  /// point of the state check is to avoid interrupting active reading — an
  /// interruption here would degrade the usability scores and contaminate the
  /// retention measure it exists to produce.
  Widget _buildCornerCard() {
    return Positioned(
      top: 16,
      right: 16,
      child: Material(
        color: Colors.transparent,
        child: GestureDetector(
          onTap: () => _dismissCornerCard(tapped: true),
          child: Container(
            width: 260,
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(14),
              border: Border.all(color: AppColors.purple.withOpacity(0.35)),
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withOpacity(0.12),
                  blurRadius: 16,
                  offset: const Offset(0, 4),
                ),
              ],
            ),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                ClipRRect(
                  borderRadius: BorderRadius.circular(10),
                  child: Image.network(
                    _reminderImageUrl!,
                    height: 120,
                    fit: BoxFit.cover,
                    errorBuilder: (_, __, ___) => const SizedBox.shrink(),
                  ),
                ),
                if ((_reminderCue ?? '').isNotEmpty) ...[
                  const SizedBox(height: 8),
                  Text(
                    _reminderCue!,
                    textAlign: TextAlign.right,
                    style: const TextStyle(
                        fontSize: 12.5, height: 1.7, color: AppColors.navy),
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
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

  /// Below this width the two panes stack instead of sitting side by side.
  /// A split pane on a narrow screen gives two unusably thin columns, and the
  /// reading task is the thing being measured — it must not be degraded by
  /// the layout on whatever device the participant happens to bring.
  static const double _splitBreakpoint = StudyShellMetrics.splitBreakpoint;

  Widget _buildSessionContent() {
    return IdleDetector(
      userId: widget.userId,
      idleThreshold: idleThreshold,
      logSink: ApiService.logEvent,
      onIdle: _onIdle,
      onFocusLost: _onFocusLost,
      onFocusReturn: _onFocusReturn,
      child: Padding(
            padding: const EdgeInsets.fromLTRB(16, 16, 16, 12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                if (widget.pdfBytes != null)
                  Text(widget.pdfName ?? 'فایل تو', style: const TextStyle(fontWeight: FontWeight.bold, color: AppColors.navy))
                else
                  _buildTimeBanner(),
                const SizedBox(height: 12),
                Expanded(
                  child: widget.pdfBytes != null ? SfPdfViewer.memory(
                    widget.pdfBytes!,
                    onDocumentLoadFailed: (details) {
                      if (!mounted) return;
                      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: const Text('فایل باز نشد. فایل ممکن است آسیب‌دیده یا رمزدار باشد.'), action: SnackBarAction(label: 'انتخاب مجدد', onPressed: () => Navigator.of(context).pushReplacement(MaterialPageRoute(builder: (_) => PdfUploadPage(userId: widget.userId))))));
                    },
                  ) : ExamSplitView(
                    questionsPane: _buildQuestionsPane(),
                    passagePane: _buildPassagePane(),
                    breakpoint: _splitBreakpoint,
                  ),
                ),
                const SizedBox(height: 12),
                if (widget.pdfBytes != null)
                  StudyPrimaryButton(label: 'پایان مطالعه', onPressed: _finishing ? null : () => _finishPart('submitted'))
                else
                  _buildSessionFooter(),
              ],
            ),
      ),
    );
  }

  Widget _paneBox({required Widget child}) => Container(
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: AppColors.purple.withOpacity(0.18)),
        ),
        clipBehavior: Clip.antiAlias,
        child: child,
      );

  /// The reading pane. Both passages run in one continuous scroll, each with
  /// its own exam-style header, as in the real computer-delivered test.
  Widget _buildPassagePane() {
    final readings = _readings;
    return _paneBox(
      child: Directionality(
        textDirection: TextDirection.ltr,
        child: Scrollbar(
          controller: _passageScroll,
          thumbVisibility: true,
          child: SingleChildScrollView(
            controller: _passageScroll,
            padding: const EdgeInsets.fromLTRB(26, 22, 26, 32),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                for (var i = 0; i < readings.length; i++) ...[
                  if (i > 0) const Divider(height: 46, thickness: 1.2),
                  _buildPassageBody(readings[i], i + 1),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildPassageBody(ReadingPassage r, int ordinal) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'READING PASSAGE $ordinal',
          style: TextStyle(
            fontSize: 12,
            letterSpacing: 1.2,
            fontWeight: FontWeight.w700,
            color: AppColors.navy.withOpacity(0.5),
          ),
        ),
        const SizedBox(height: 8),
        if (r.instructions.isNotEmpty) ...[
          Text(
            r.instructions,
            style: TextStyle(
              fontSize: 12.5,
              height: 1.6,
              fontStyle: FontStyle.italic,
              color: AppColors.navy.withOpacity(0.75),
            ),
          ),
          const SizedBox(height: 12),
        ],
        Text(
          r.title,
          style: const TextStyle(
            fontSize: 21,
            fontWeight: FontWeight.bold,
            color: AppColors.navy,
            height: 1.35,
          ),
        ),
        if (r.subtitle.isNotEmpty) ...[
          const SizedBox(height: 6),
          Text(
            r.subtitle,
            style: TextStyle(
              fontSize: 13.5,
              height: 1.6,
              fontStyle: FontStyle.italic,
              color: AppColors.navy.withOpacity(0.78),
            ),
          ),
        ],
        if (r.source.isNotEmpty) ...[
          const SizedBox(height: 8),
          Text(
            'Source: ${r.source}',
            style: TextStyle(
              fontSize: 11.5,
              color: AppColors.navy.withOpacity(0.5),
            ),
          ),
        ],
        const SizedBox(height: 14),
        SelectableText(
          r.body.trim(),
          style: const TextStyle(
            fontSize: 15.5,
            height: 1.85,
            color: AppColors.navy,
          ),
        ),
      ],
    );
  }

  /// The questions pane. Persian instructions and controls, so the content
  /// is RTL even though the pane sits on the left.
  Widget _buildQuestionsPane() {
    return _paneBox(
      child: Directionality(
        textDirection: TextDirection.rtl,
        child: Scrollbar(
          controller: _questionScroll,
          thumbVisibility: true,
          child: SingleChildScrollView(
            controller: _questionScroll,
            padding: const EdgeInsets.fromLTRB(18, 20, 18, 28),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const Text(
                  'سوالات ✍️',
                  style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                      color: AppColors.navy),
                ),
                const SizedBox(height: 4),
                Text(
                  'متن در سمت راست است. می‌تونی همزمان متن رو بخونی و جواب بدی.',
                  style: TextStyle(
                      fontSize: 12.5,
                      height: 1.7,
                      color: AppColors.navy.withOpacity(0.7)),
                ),
                const SizedBox(height: 12),
                ..._questions.map(_buildQuestion),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildSessionFooter() {
    final answered = _questions.where(_isAnswered).length;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          '$answered از ${_questions.length} سوال پاسخ داده شده',
          textAlign: TextAlign.center,
          style: TextStyle(
              fontSize: 12.5, color: AppColors.navy.withOpacity(0.7)),
        ),
        const SizedBox(height: 8),
        StudyPrimaryButton(
          label: 'ثبت پاسخ‌ها و پایان جلسه',
          busy: _submitting,
          onPressed: _submitQuiz,
        ),
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

  /// The live countdown for the reading window.
  ///
  /// Visible on purpose. At this pace it mirrors real IELTS conditions, and
  /// the mild time pressure is what makes the task aversive enough that
  /// natural disengagement happens at all — with no pressure the likely
  /// result is a floor effect in which nobody disengages and the primary
  /// measures have nothing to explain.
  Widget _buildTimeBanner() {
    final m = _remaining.inMinutes;
    final sec = _remaining.inSeconds % 60;
    final low = _remaining.inMinutes < 5;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
            color: low
                ? Colors.redAccent.withOpacity(0.5)
                : AppColors.purple.withOpacity(0.25)),
      ),
      child: Row(
        children: [
          Icon(Icons.schedule_rounded,
              size: 20, color: low ? Colors.redAccent : AppColors.purple),
          const SizedBox(width: 10),
          const Expanded(
            child: Text(
              'زمان باقی‌مانده‌ی این جلسه',
              style: TextStyle(
                  fontSize: 12.5, height: 1.8, color: AppColors.navy),
            ),
          ),
          const SizedBox(width: 10),
          Directionality(
            textDirection: TextDirection.ltr,
            child: Text(
              '${m.toString().padLeft(2, '0')}:'
              '${sec.toString().padLeft(2, '0')}',
              style: TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.bold,
                color: low ? Colors.redAccent : AppColors.navy,
              ),
            ),
          ),
        ],
      ),
    );
  }
 }
