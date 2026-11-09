// lib/widgets/idle_detector.dart
import 'dart:async';
import 'package:flutter/material.dart';

/// Where a behaviour event goes. Injectable so the idle/focus logic can be
/// tested without a server: these events are outcome measures, so being able
/// to assert on them matters.
typedef BehaviorLogSink = void Function(
    int userId, String eventType, Map<String, dynamic> details);

class IdleDetector extends StatefulWidget {
  /// Behaviour events (idle/focus) are persisted, not just printed.
  ///
  /// This must stay true for any run that produces data. Idle and focus
  /// events are now OUTCOME measures — how often a participant disengages
  /// and how long they hold attention after a cue — rather than incidental
  /// logging. With this false the export still looks healthy, because
  /// research rows are written elsewhere, while the fine-grained behaviour
  /// log is silently empty.
  static const bool persistBehaviorLogs = true;

  final int userId;
  final Widget child;
  final Duration idleThreshold; // e.g. Duration(seconds: 90)
  final VoidCallback? onIdle;   // show your nudge UI
  final VoidCallback? onFocusReturn;

  /// Called when the app/tab loses focus (tab switch, window change).
  final VoidCallback? onFocusLost;

  /// Callback invoked when the user has been idle long enough to trigger a
  /// nudge but the application is not currently in a visible or resumed
  /// lifecycle state. This allows the caller (for example, a page) to
  /// perform background-only behaviour such as scheduling a system
  /// notification without displaying an in-app overlay. If null, suppressed
  /// idle events will be silently deferred and handled when focus returns.
  final VoidCallback? onIdleWhileSuppressed;

  /// Where behaviour events are sent.
  ///
  /// Required, and deliberately so. These events are outcome data, and the
  /// previous failure mode was exactly that they went nowhere while the rest
  /// of the export looked healthy. Making the sink impossible to omit turns
  /// that into a compile error. Keeping it injected also means this widget
  /// does not depend on the API layer, so the idle logic is testable off-web.
  final BehaviorLogSink logSink;

  /// Overrides the wall clock. Defaults to [DateTime.now].
  ///
  /// The idle check compares elapsed real time against [idleThreshold], so a
  /// test that only advances Flutter's timer queue would never see an idle
  /// event — the guard against stale timers would swallow it.
  final DateTime Function()? nowFn;

  const IdleDetector({
    super.key,
    required this.userId,
    required this.child,
    required this.idleThreshold,
    this.onIdle,
    this.onFocusReturn,
    this.onFocusLost,
    this.onIdleWhileSuppressed,
    required this.logSink,
    this.nowFn,
  });

  @override
  State<IdleDetector> createState() => _IdleDetectorState();
}

class _IdleDetectorState extends State<IdleDetector>
    with WidgetsBindingObserver {
  /// Central gate for behavior-event logging. Detection always prints to the
  /// console; persistence is on unless deliberately disabled for debugging.
  void _log(String eventType, Map<String, dynamic> details) {
    debugPrint('🔍 [detected] $eventType $details');
    if (IdleDetector.persistBehaviorLogs) {
      widget.logSink(widget.userId, eventType, details);
    }
  }

  DateTime _now() => (widget.nowFn ?? DateTime.now)();

  Timer? _idleTimer;
  bool _isIdle = false;
  late DateTime _lastActivityAt;

  // Defer nudge when app is not visible / not resumed
  bool _deferNudge = false;
  String? _deferReason;
  DateTime? _deferAt;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _lastActivityAt = _now();
    _startTimer();
  }

  @override
  void dispose() {
    _idleTimer?.cancel();
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  // ───────────────────────────────────────────
  // Lifecycle
  // ───────────────────────────────────────────
  @override
  void didChangeAppLifecycleState(AppLifecycleState state) async {
    debugPrint("📱 Lifecycle: $state");
    if (!mounted) return;

    switch (state) {
      case AppLifecycleState.resumed:
        _isIdle = false;
        _markActivity(); // refresh timer
        _onFocusReturn();

        // focus_resumed is a state change (keep it here)
        _log('focus_resumed', _baseDetails());

        // NOTE: no deferred reminder on return. Time spent away from the tab
        // is the extension's territory; coming back should NOT trigger an
        // in-app reminder. We just clear the deferral bookkeeping.
        _deferNudge = false;
        _deferAt = null;
        _deferReason = null;
        break;

      case AppLifecycleState.inactive:
      case AppLifecycleState.paused:
      case AppLifecycleState.hidden:
        _idleTimer?.cancel();

        _deferNudge = true;
        _deferReason = 'app_background_or_hidden';
        _deferAt = _now();

        _log('idle_suppressed',
            _baseDetails(extra: {'reason': 'app_background_or_hidden'}));
        _log('focus_lost', _baseDetails());

        try {
          widget.onFocusLost?.call();
        } catch (e) {
          debugPrint('⚠️ onFocusLost threw: $e');
        }

        // When the app loses focus, proactively invoke the optional
        // onIdleWhileSuppressed callback. This can be used on web to
        // dispatch a system notification immediately, informing the user
        // that their attention has moved away from the app. Errors are
        // silently ignored.
        if (widget.onIdleWhileSuppressed != null) {
          try {
            widget.onIdleWhileSuppressed!();
          } catch (e) {
            debugPrint('⚠️ onIdleWhileSuppressed (focus lost) threw: $e');
          }
        }
        break;

      case AppLifecycleState.detached:
        _idleTimer?.cancel();
        break;
    }
  }

  // ───────────────────────────────────────────
  // Idle tracking
  // ───────────────────────────────────────────
  void _startTimer() {
    _idleTimer?.cancel();
    _idleTimer = Timer(widget.idleThreshold, _onIdleTimerFired);
  }

  void _resetTimer() {
    if (_isIdle) {
      _isIdle = false;
      _onFocusReturn();
    }
    _idleTimer?.cancel();
    _startTimer();
  }

  void _markActivity() {
    _lastActivityAt = _now();
    _resetTimer();
  }

  Future<void> _onIdleTimerFired() async {
    final now = _now();
    final silentFor = now.difference(_lastActivityAt);

    // Guard against stale timer
    if (silentFor < widget.idleThreshold) {
      _startTimer();
      return;
    }

    if (_isIdle) return;

    // On Flutter web, lifecycleState stays null until the first lifecycle
    // event (e.g. a tab switch) — treat null as "resumed", otherwise idle in
    // a freshly opened tab is wrongly suppressed.
    final lifecycle = WidgetsBinding.instance.lifecycleState;
    final canShow = mounted &&
        (ModalRoute.of(context)?.isCurrent ?? true) &&
        (lifecycle == null || lifecycle == AppLifecycleState.resumed);

    if (!canShow) {
      _deferNudge = true;
      _deferReason = 'not_visible_or_inactive';
      _deferAt = _now();

      _log('idle_suppressed', _baseDetails(extra: {
        'reason': 'not_visible_or_inactive',
        'silent_for_ms': silentFor.inMilliseconds,
        'idle_threshold_ms': widget.idleThreshold.inMilliseconds,
      }));

      // In addition to deferring the nudge until focus returns, invoke the
      // optional callback so the caller can handle this event when the app
      // is backgrounded. This enables features such as dispatching browser
      // notifications when the user navigates away from the tab. Errors are
      // caught and logged but do not crash the idle detector.
      if (widget.onIdleWhileSuppressed != null) {
        try {
          widget.onIdleWhileSuppressed!();
        } catch (e) {
          debugPrint("⚠️ onIdleWhileSuppressed threw: $e");
        }
      }
      return;
    }

    _isIdle = true;

    // Only log idle_detected here
    _log('idle_detected', _baseDetails(extra: {
      'silent_for_ms': silentFor.inMilliseconds,
      'idle_threshold_ms': widget.idleThreshold.inMilliseconds,
    }));

    // Now let parent show the nudge and log `nudge_shown`.
    try {
      widget.onIdle?.call();
    } catch (e) {
      debugPrint("⚠️ onIdle threw: $e");
    }
  }

  void _onFocusReturn() {
    try {
      widget.onFocusReturn?.call();
    } catch (e) {
      debugPrint("⚠️ onFocusReturn threw: $e");
    }
  }

  Map<String, dynamic> _baseDetails({Map<String, dynamic>? extra}) {
    return {
      'route': ModalRoute.of(context)?.settings.name,
      'ts': _now().toIso8601String(),
      ...?extra,
    };
  }

  // ───────────────────────────────────────────
  // Build: capture user activity
  // ───────────────────────────────────────────
  @override
  Widget build(BuildContext context) {
    return Listener(
      behavior: HitTestBehavior.translucent,
      onPointerDown: (_) => _markActivity(),
      onPointerMove: (_) => _markActivity(),
      onPointerUp: (_) => _markActivity(),
      onPointerSignal: (_) => _markActivity(),
      child: NotificationListener<ScrollNotification>(
        onNotification: (n) {
          if (n is UserScrollNotification ||
              n is ScrollUpdateNotification ||
              n is OverscrollNotification) {
            _markActivity();
          }
          return false;
        },
        child: widget.child,
      ),
    );
  }
}
