import 'package:flutter_test/flutter_test.dart';
import 'package:moirai/data/quiz_questions.dart';
import 'package:moirai/data/readings.dart';
import 'package:moirai/services/study_config.dart';

/// The single session is assembled from [StudyConfig.sessionPassages]. These
/// guard the assembly, because every failure mode here is silent: a missing
/// passage just renders less text, and a duplicate question id overwrites an
/// answer without any error.
void main() {
  List<QuizQuestion> sessionQuestions() => [
        for (final id in StudyConfig.sessionPassages)
          ...(quizQuestionsBySession[id] ?? const <QuizQuestion>[]),
      ];

  group('session composition', () {
    test('every configured passage exists', () {
      for (final id in StudyConfig.sessionPassages) {
        expect(readingsBySession[id], isNotNull,
            reason: 'passage $id is configured but has no reading');
      }
    });

    test('every configured passage has questions', () {
      for (final id in StudyConfig.sessionPassages) {
        expect(quizQuestionsBySession[id], isNotNull,
            reason: 'passage $id is configured but has no question set');
        expect(quizQuestionsBySession[id], isNotEmpty);
      }
    });

    test('question ids are unique across the combined set', () {
      // The answer map is keyed by id. A collision between passages would
      // silently overwrite one answer with another and score both wrong,
      // with nothing in the UI or the export looking unusual.
      final ids = sessionQuestions().map((q) => q.id).toList();
      expect(ids.toSet().length, ids.length,
          reason: 'duplicate question id across passages');
    });

    test('the session has questions at all', () {
      expect(sessionQuestions(), isNotEmpty);
    });

    test('reading pace stays near authentic IELTS', () {
      // ~36 words/min is real Academic IELTS pace. Much above it and the task
      // is not completable, which measures giving up rather than
      // procrastinating — a different behaviour the primary measures cannot
      // separate from the one being studied.
      final words = StudyConfig.sessionPassages
          .map((id) => readingsBySession[id]!.body.split(RegExp(r'\s+')).length)
          .fold<int>(0, (a, b) => a + b);
      final pace = words / StudyConfig.readingWindow.inMinutes;
      expect(pace, lessThan(60),
          reason: 'reading pace $pace w/min is far above authentic IELTS');
    });
  });

  group('cue schedule fits the window', () {
    test('both cues land inside the reading window with room after', () {
      for (final offset in StudyConfig.cueOffsets) {
        expect(offset, lessThan(StudyConfig.readingWindow));
      }
      // The last cue needs room after it for the retention measure to mean
      // anything: a cue at the very end has nothing to retain attention for.
      final last = StudyConfig.cueOffsets.last;
      expect(StudyConfig.readingWindow - last,
          greaterThanOrEqualTo(const Duration(minutes: 10)));
    });

    test('cue offsets are strictly increasing', () {
      for (var i = 1; i < StudyConfig.cueOffsets.length; i++) {
        expect(StudyConfig.cueOffsets[i],
            greaterThan(StudyConfig.cueOffsets[i - 1]));
      }
    });

    test('grace never overlaps the next slot', () {
      // Overlapping windows would let one slot still be claimable when the
      // next opens, so a single participant could take two cues at once.
      for (var i = 1; i < StudyConfig.cueOffsets.length; i++) {
        final prevEnd = StudyConfig.cueOffsets[i - 1] + StudyConfig.cueGrace;
        expect(prevEnd, lessThanOrEqualTo(StudyConfig.cueOffsets[i]));
      }
    });
  });

  group('question integrity', () {
    String allText() => StudyConfig.sessionPassages
        .map((id) => readingsBySession[id]!.body)
        .join(' ')
        .toLowerCase();

    test('every gap answer actually appears in the passage', () {
      // IELTS summary completion says "ONE WORD ONLY FROM THE PASSAGE". An
      // answer that is not in the text is unanswerable however carefully the
      // participant reads, and it silently scores everyone wrong.
      final text = allText();
      for (final q in sessionQuestions()
          .where((q) => q.kind == QuestionKind.gap)) {
        for (final alt in q.correctText.split('|')) {
          expect(text.contains(alt.trim().toLowerCase()), isTrue,
              reason: '${q.id}: "$alt" does not occur in the passage');
        }
      }
    });

    test('every gap answer is a single word', () {
      for (final q in sessionQuestions()
          .where((q) => q.kind == QuestionKind.gap)) {
        for (final alt in q.correctText.split('|')) {
          expect(alt.trim().split(RegExp(r'\s+')).length, 1,
              reason: '${q.id}: "$alt" is not ONE WORD ONLY');
        }
      }
    });

    test('every choice question has a valid answer index', () {
      // A correctIndex outside the options list marks every response wrong,
      // and nothing in the UI would reveal it.
      for (final q in sessionQuestions()
          .where((q) => q.kind == QuestionKind.choice)) {
        expect(q.options.length, greaterThanOrEqualTo(2), reason: q.id);
        expect(q.correctIndex, greaterThanOrEqualTo(0), reason: q.id);
        expect(q.correctIndex, lessThan(q.options.length), reason: q.id);
      }
    });

    test('paragraph-matching answers exist in the passage', () {
      // "Which paragraph contains..." can only be answered if that paragraph
      // label is actually printed in the text.
      final text = allText();
      for (final q in sessionQuestions().where(
          (q) => q.options.length == 8 && q.options.first == 'A')) {
        final letter = q.options[q.correctIndex].toLowerCase();
        expect(text.contains('\n$letter.'), isTrue,
            reason: '${q.id}: paragraph $letter is not labelled in the text');
      }
    });

    test('the paper is IELTS-sized', () {
      // 26-27 questions across two passages is the real specification. Far
      // fewer and a fast reader finishes before the minute-20 cue.
      expect(sessionQuestions().length, inInclusiveRange(24, 30));
    });

    test('gap answers are not case-sensitive traps', () {
      for (final q in sessionQuestions()
          .where((q) => q.kind == QuestionKind.gap)) {
        expect(q.isGapAnswerCorrect(q.correctText.split('|').first.toUpperCase()),
            isTrue,
            reason: '${q.id} should accept any casing');
      }
    });
  });
}
