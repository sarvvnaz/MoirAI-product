// Idle detection is a MEASUREMENT, not a UI nicety: the threshold defines
// what counts as a disengagement, and the events it emits are outcome data.
// These tests pin both down.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:moirai/services/idle_detector.dart';
import 'package:moirai/services/study_config.dart';

/// A controllable stand-in for the wall clock, so elapsed real time can be
/// advanced alongside Flutter's timer queue.
class _FakeClock {
  DateTime _now = DateTime(2026, 1, 1, 12);
  DateTime call() => _now;
  void advance(Duration d) => _now = _now.add(d);
}

void main() {
  group('StudyConfig', () {
    test('idle threshold is 60s for real runs', () {
      // If this fails because debugTimings was left on, the study would be
      // recording a different definition of "disengaged" than the one
      // written up.
      expect(StudyConfig.debugTimings, isFalse,
          reason: 'debugTimings must be false for any run producing data');
      expect(StudyConfig.idleThreshold, const Duration(seconds: 60));
    });

    test('reading window is 35 minutes and both cues fall inside it', () {
      expect(StudyConfig.readingWindow, const Duration(minutes: 35));
      expect(StudyConfig.cueOffsets,
          [const Duration(minutes: 10), const Duration(minutes: 20)]);
      for (final offset in StudyConfig.cueOffsets) {
        expect(offset + StudyConfig.cueGrace,
            lessThan(StudyConfig.readingWindow),
            reason: 'a cue slot must be able to resolve before the window ends');
      }
    });
  });

  group('IdleDetector', () {
    const threshold = Duration(seconds: 60);

    /// Mounts the detector and returns the events it emitted.
    Future<List<String>> pumpDetector(
      WidgetTester tester, {
      required _FakeClock clock,
      required Duration elapse,
      VoidCallback? onIdle,
      List<Map<String, dynamic>>? capture,
    }) async {
      final events = <String>[];
      await tester.pumpWidget(MaterialApp(
        home: IdleDetector(
          userId: 1,
          idleThreshold: threshold,
          nowFn: clock.call,
          logSink: (userId, eventType, details) {
            events.add(eventType);
            capture?.add({'type': eventType, ...details});
          },
          onIdle: onIdle,
          child: const Scaffold(body: Text('reading')),
        ),
      ));

      // Advance the wall clock and the timer queue together — the detector
      // guards on elapsed real time, so moving only one proves nothing.
      clock.advance(elapse);
      await tester.pump(elapse);
      return events;
    }

    testWidgets('stays quiet before the threshold', (tester) async {
      var idleFired = false;
      final events = await pumpDetector(
        tester,
        clock: _FakeClock(),
        elapse: const Duration(seconds: 59),
        onIdle: () => idleFired = true,
      );

      expect(idleFired, isFalse);
      expect(events, isNot(contains('idle_detected')));
    });

    testWidgets('reports idle once the threshold passes', (tester) async {
      var idleFired = false;
      final events = await pumpDetector(
        tester,
        clock: _FakeClock(),
        elapse: const Duration(seconds: 61),
        onIdle: () => idleFired = true,
      );

      expect(idleFired, isTrue);
      expect(events, contains('idle_detected'));
    });

    testWidgets('does not report idle twice for one episode', (tester) async {
      var idleCount = 0;
      final clock = _FakeClock();
      await pumpDetector(
        tester,
        clock: clock,
        elapse: const Duration(seconds: 61),
        onIdle: () => idleCount++,
      );

      // Keep sitting still well past a second threshold.
      clock.advance(const Duration(seconds: 120));
      await tester.pump(const Duration(seconds: 120));

      expect(idleCount, 1,
          reason: 'one continuous silence is one disengagement episode');
    });

    testWidgets('activity resets the clock', (tester) async {
      var idleFired = false;
      final clock = _FakeClock();
      await tester.pumpWidget(MaterialApp(
        home: IdleDetector(
          userId: 1,
          idleThreshold: threshold,
          nowFn: clock.call,
          logSink: (_, __, ___) {},
          onIdle: () => idleFired = true,
          child: const Scaffold(body: Text('reading')),
        ),
      ));

      // Almost idle, then a tap, then almost idle again — never 60s of
      // silence in a row, so never a disengagement.
      for (var i = 0; i < 3; i++) {
        clock.advance(const Duration(seconds: 50));
        await tester.pump(const Duration(seconds: 50));
        await tester.tap(find.text('reading'));
      }

      expect(idleFired, isFalse);
    });

    testWidgets('idle event carries the measured silence and threshold',
        (tester) async {
      final captured = <Map<String, dynamic>>[];
      await pumpDetector(
        tester,
        clock: _FakeClock(),
        elapse: const Duration(seconds: 61),
        capture: captured,
      );

      final idle = captured.firstWhere((e) => e['type'] == 'idle_detected');
      // Analysis needs to know what threshold produced the row, not just
      // that a row exists.
      expect(idle['idle_threshold_ms'], threshold.inMilliseconds);
      expect(idle['silent_for_ms'], greaterThanOrEqualTo(60000));
    });

    testWidgets('persistence is enabled', (tester) async {
      expect(IdleDetector.persistBehaviorLogs, isTrue,
          reason: 'behaviour events are outcome data and must be persisted');
    });
  });
}
