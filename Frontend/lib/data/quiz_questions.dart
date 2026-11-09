// Reading-comprehension questions, keyed by passage id, matching the passages
// in readings.dart.
//
// WRITTEN TO AUTHENTIC IELTS SPECIFICATION. A real Academic Reading paper
// gives 13-14 questions per passage and mixes task types within a passage;
// both are reproduced here, because the task type is a large part of what
// makes the exam cognitively demanding. A passage followed by four plain
// multiple-choice items is a comprehension quiz, not an IELTS section, and it
// would not produce the sustained effort this study is trying to observe.
//
//   Passage 1 (13 items) — True/False/Not Given · summary completion
//                          (ONE WORD ONLY) · multiple choice
//   Passage 2 (13 items) — Yes/No/Not Given · matching information to
//                          paragraphs · summary completion · multiple choice
//
// Question count is also a DOSAGE parameter: 26 items keep the participant
// working past minute 20, so the second scheduled cue is reachable and
// exposure stays equal across arms.

/// How a question is answered on screen.
enum QuestionKind {
  /// Pick one of [QuizQuestion.options] (multiple choice, True/False/Not
  /// Given, Yes/No/Not Given, paragraph matching A-H).
  choice,

  /// Type a short answer — summary completion ("ONE WORD ONLY").
  /// Graded against [QuizQuestion.correctText], case- and space-insensitive.
  gap,
}

class QuizQuestion {
  final String id;
  final String prompt;
  final QuestionKind kind;

  /// Choice questions only.
  final List<String> options;
  final int correctIndex;

  /// Gap questions only. Alternatives can be given as 'word|alternative'.
  final String correctText;

  /// Optional heading rendered above this question, used to introduce a new
  /// question group ("Questions 7-10 · Complete the summary below.").
  final String groupHeader;

  const QuizQuestion({
    required this.id,
    required this.prompt,
    this.kind = QuestionKind.choice,
    this.options = const [],
    this.correctIndex = -1,
    this.correctText = '',
    this.groupHeader = '',
  });

  /// Case-insensitive, whitespace-tolerant grading for typed answers.
  bool isGapAnswerCorrect(String typed) {
    final given = typed.trim().toLowerCase();
    if (given.isEmpty) return false;
    return correctText
        .toLowerCase()
        .split('|')
        .map((e) => e.trim())
        .where((e) => e.isNotEmpty)
        .contains(given);
  }
}

const List<String> _tfng = ['True', 'False', 'Not Given'];
const List<String> _ynng = ['Yes', 'No', 'Not Given'];
const List<String> _paragraphsAH = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'];

const Map<int, List<QuizQuestion>> quizQuestionsBySession = {
  // ══════════════════════════════════════════════════════════════════
  // PASSAGE 1 · The Sailing Stones · Questions 1-13
  // ══════════════════════════════════════════════════════════════════
  1: [
    QuizQuestion(
      id: 'p1q1',
      groupHeader: 'Questions 1–6\n'
          'Do the following statements agree with the information given in '
          'Reading Passage 1?\n\n'
          'TRUE  if the statement agrees with the information\n'
          'FALSE  if the statement contradicts the information\n'
          'NOT GIVEN  if there is no information on this',
      prompt: '1. The surface of Racetrack Playa is almost perfectly level.',
      options: _tfng,
      correctIndex: 0, // A: elevation varies by less than four centimetres
    ),
    QuizQuestion(
      id: 'p1q2',
      prompt: '2. The stones found on the playa came from the slopes '
          'surrounding the basin.',
      options: _tfng,
      correctIndex: 0, // B: broken away from the steep slopes
    ),
    QuizQuestion(
      id: 'p1q3',
      prompt: '3. Early visitors found evidence that people had moved the '
          'stones by hand.',
      options: _tfng,
      correctIndex: 1, // B: the ABSENCE of footprints made this hard to sustain
    ),
    QuizQuestion(
      id: 'p1q4',
      prompt: '4. Dust devils occur more frequently at Racetrack Playa than '
          'at other desert sites.',
      options: _tfng,
      correctIndex: 2, // C says only that they are common in desert basins
    ),
    QuizQuestion(
      id: 'p1q5',
      prompt: '5. The wind speeds required by the second theory had never '
          'been measured at the playa.',
      options: _tfng,
      correctIndex: 0, // D: far in excess of anything ever recorded
    ),
    QuizQuestion(
      id: 'p1q6',
      prompt: '6. The 2011–2014 study was the first investigation to use GPS '
          'equipment at the site.',
      options: _tfng,
      correctIndex: 2, // F reports the GPS use but never claims priority
    ),
    QuizQuestion(
      id: 'p1q7',
      kind: QuestionKind.gap,
      groupHeader: 'Questions 7–10\n'
          'Complete the summary below.\n'
          'Choose ONE WORD ONLY from the passage for each answer.',
      prompt: '7. The stones reach the floor of the playa after falling from '
          'nearby ________.',
      correctText: 'slopes',
    ),
    QuizQuestion(
      id: 'p1q8',
      kind: QuestionKind.gap,
      prompt: '8. Their movement was once attributed to whirlwinds, but this '
          'could not explain tracks that lay ________ to one another.',
      correctText: 'parallel',
    ),
    QuizQuestion(
      id: 'p1q9',
      kind: QuestionKind.gap,
      prompt: '9. A rival theory was rejected because the wind speeds it '
          'required had never been ________ at the site.',
      correctText: 'recorded',
    ),
    QuizQuestion(
      id: 'p1q10',
      kind: QuestionKind.gap,
      prompt: '10. In 2013 researchers saw floating panels of ice push the '
          'stones through the soft ________ beneath the water.',
      correctText: 'mud',
    ),
    QuizQuestion(
      id: 'p1q11',
      groupHeader: 'Questions 11–13\n'
          'Choose the correct letter, A, B, C or D.',
      prompt: '11. Why was the dust devil hypothesis rejected?',
      options: [
        'Dust devils are not found in desert basins.',
        'They could not account for tracks shared by several stones.',
        'They occur only during the winter months.',
        'They are too powerful to leave narrow tracks.',
      ],
      correctIndex: 1,
    ),
    QuizQuestion(
      id: 'p1q12',
      prompt: '12. According to the passage, what made the ice raft '
          'hypothesis difficult to test?',
      options: [
        'The stones were too heavy to fit with instruments.',
        'The playa was closed to researchers during winter.',
        'Flooding was unpredictable and movement events were rare.',
        'The ice was too thin to be observed directly.',
      ],
      correctIndex: 2,
    ),
    QuizQuestion(
      id: 'p1q13',
      prompt: '13. What does the writer suggest about the final explanation?',
      options: [
        'It confirmed that a rare geological event had taken place.',
        'It depended on a chance combination of ordinary conditions.',
        'It showed that earlier researchers had been careless.',
        'It required winds stronger than any previously measured.',
      ],
      correctIndex: 1,
    ),
  ],

  // ══════════════════════════════════════════════════════════════════
  // PASSAGE 2 · The Collapse of the Northern Cod · Questions 14-26
  // ══════════════════════════════════════════════════════════════════
  2: [
    QuizQuestion(
      id: 'p2q14',
      groupHeader: 'Questions 14–18\n'
          'Do the following statements agree with the claims of the writer in '
          'Reading Passage 2?\n\n'
          'YES  if the statement agrees with the claims of the writer\n'
          'NO  if the statement contradicts the claims of the writer\n'
          'NOT GIVEN  if it is impossible to say what the writer thinks',
      prompt: '14. The immediate cause of the collapse remains a matter of '
          'serious disagreement.',
      options: _ynng,
      correctIndex: 1, // B: "The immediate cause is not seriously disputed."
    ),
    QuizQuestion(
      id: 'p2q15',
      prompt: '15. The 1977 extension of the economic zone reduced the total '
          'fishing capacity working on the grounds.',
      options: _ynng,
      correctIndex: 1, // B: the domestic fleet expanded to occupy the space
    ),
    QuizQuestion(
      id: 'p2q16',
      prompt: '16. Concerns about the state of the stock were raised before '
          'the fishery was closed.',
      options: _ynng,
      correctIndex: 0, // E: scientists argued quotas were far too high
    ),
    QuizQuestion(
      id: 'p2q17',
      prompt: '17. Environmental change on its own provides an adequate '
          'explanation for the collapse.',
      options: _ynng,
      correctIndex: 1, // G: treated as insufficient on its own
    ),
    QuizQuestion(
      id: 'p2q18',
      prompt: '18. Cod fisheries in other parts of the world have declined in '
          'the same way.',
      options: _ynng,
      correctIndex: 2, // never discussed
    ),
    QuizQuestion(
      id: 'p2q19',
      groupHeader: 'Questions 19–22\n'
          'Reading Passage 2 has eight paragraphs, A–H.\n'
          'Which paragraph contains the following information?\n'
          'Write the correct letter, A–H.',
      prompt: '19. an explanation of why catch data can misrepresent the size '
          'of a population',
      options: _paragraphsAH,
      correctIndex: 3, // D — hyperstability
    ),
    QuizQuestion(
      id: 'p2q20',
      prompt: '20. a description of conflicting responsibilities within a '
          'government department',
      options: _paragraphsAH,
      correctIndex: 4, // E
    ),
    QuizQuestion(
      id: 'p2q21',
      prompt: '21. figures showing the highest level the fishery ever reached',
      options: _paragraphsAH,
      correctIndex: 1, // B — 800,000 tonnes in 1968
    ),
    QuizQuestion(
      id: 'p2q22',
      prompt: '22. evidence that other species now occupy the role cod once '
          'held',
      options: _paragraphsAH,
      correctIndex: 7, // H — capelin and shrimp
    ),
    QuizQuestion(
      id: 'p2q23',
      kind: QuestionKind.gap,
      groupHeader: 'Questions 23–26\n'
          'Complete the summary below.\n'
          'Choose ONE WORD ONLY from the passage for each answer.',
      prompt: '23. As their numbers fell, the cod gathered into smaller and '
          'denser ________.',
      correctText: 'shoals',
    ),
    QuizQuestion(
      id: 'p2q24',
      kind: QuestionKind.gap,
      prompt: '24. Vessels using ________ were therefore able to find them '
          'with increasing efficiency.',
      correctText: 'sonar',
    ),
    QuizQuestion(
      id: 'p2q25',
      kind: QuestionKind.gap,
      prompt: '25. Because catch rates stayed steady while the stock fell, '
          'the effect is known as ________.',
      correctText: 'hyperstability',
    ),
    QuizQuestion(
      id: 'p2q26',
      kind: QuestionKind.gap,
      prompt: '26. Independent surveys, which sampled ________ locations, '
          'produced very different results.',
      correctText: 'fixed',
    ),
  ],
};
