/// Study parameters that define the protocol, in one place.
///
/// These are DESIGN decisions, not UI details: the length of the reading
/// window, when cues are scheduled, and how long silence counts as idle all
/// appear in the write-up and determine what the behavioural measures mean.
/// They live together so a reader checking the protocol can see them at once,
/// and so nobody has to hand-edit a constant buried in a page.
///
/// The server is the authority on cue timing — it stamps the start of the
/// reading window and decides when a slot is due. The offsets below are
/// mirrored here only so the client can show sensible UI; they must match
/// `CUE_OFFSETS_SECONDS` in the backend config.
library;

class StudyConfig {
  StudyConfig._();

  /// Set true ONLY for local debugging. It shortens the idle threshold so a
  /// developer does not have to sit still for a minute to see the idle path.
  ///
  /// This must be false for any run that produces data: the idle threshold
  /// defines what counts as a disengagement, so changing it changes the
  /// primary measures.
  static const bool debugTimings = false;

  /// How long the reading window lasts.
  ///
  /// Two authentic IELTS Academic Reading passages in 35 minutes is tighter
  /// than real IELTS pace (which allows ~20 min per passage). That is
  /// deliberate: mild time pressure makes the task aversive enough that
  /// natural disengagement actually happens, which is what the primary
  /// measures need in order to have variance to explain.
  static const Duration readingWindow = Duration(minutes: 35);

  /// Which reading passages make up the single session, in order.
  ///
  /// TWO passages, written to authentic IELTS Academic Reading length
  /// (~730 + ~830 words) with 26 questions between them. In the 35-minute
  /// window that is ~44 words/min against ~36 in a real paper — about 1.24x
  /// authentic pace. Tight, like a rushed practice test, but completable.
  ///
  /// Both numbers are design parameters, and they pull in opposite
  /// directions:
  ///
  ///   · too LONG and the task is unfinishable, so it measures giving up
  ///     rather than procrastinating — two behaviours the primary measures
  ///     cannot separate. The previous passages ran ~1,400 words each, which
  ///     at two passages was ~80 w/min, over twice authentic pace.
  ///   · too SHORT and a fast reader finishes before minute 20 and receives
  ///     one cue instead of two, breaking the equal-exposure guarantee the
  ///     whole design rests on.
  ///
  /// 26 questions is what buys the second half of that: it keeps the
  /// participant working past minute 20. Watch `session_ended_before_slot`
  /// in scripts/report.py during piloting to confirm it actually does.
  static const List<int> sessionPassages = [1, 2];

  /// Silence after which the participant counts as idle.
  ///
  /// Idle is now both a state classifier (which cue form to show) and an
  /// outcome (how often they disengaged), so this threshold is a measurement
  /// decision rather than a UI nicety.
  static Duration get idleThreshold =>
      debugTimings ? const Duration(seconds: 10) : const Duration(seconds: 60);

  /// When the two scheduled cues are due, as offsets from the start of the
  /// reading window. Mirrors the server; the server still decides.
  static const List<Duration> cueOffsets = [
    Duration(minutes: 10),
    Duration(minutes: 20),
  ];

  /// How long after a slot opens the cue may still be delivered before it is
  /// recorded as undelivered. Covers the case where the participant is on a
  /// page the extension cannot inject into.
  static const Duration cueGrace = Duration(seconds: 90);

  /// How often the app asks the server whether a cue slot is due. Polling
  /// happens only while the tab is visible.
  static const Duration cuePollInterval = Duration(seconds: 5);
}
