// Reading-comprehension questions, keyed by session number. They match the
// passages in readings.dart:
//   1 — Cambridge IELTS 18 · Test 3 · Passage 1: the authentic 13-question
//       set (section matching A–H, summary completion, person matching).
//   2 — 10 IELTS-style questions (True/False/Not Given, paragraph
//       information matching, multiple choice).
//   3 — 10 harder IELTS-style questions (writer's-view MC, tricky T/F/NG).

// How a question is answered on screen.
enum QuestionKind {
  /// Pick one of [QuizQuestion.options] (multiple choice, True/False/Not
  /// Given, section matching A–H, person matching A–D).
  choice,

  /// Type a short answer — IELTS summary completion ("ONE WORD ONLY").
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
  /// question group ("Questions 5–8 · Complete the summary below.").
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

/// Section labels for "Which section contains the following information?"
const List<String> _sectionsAH = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'];

/// The four people in the Cambridge 18 T3 P1 matching task.
const List<String> _people = [
  'A — Chris Cheeseman',
  'B — Markus Mannström',
  'C — Anna Surgenor',
  'D — Felix Preston and Johanna Lehne',
];

const Map<int, List<QuizQuestion>> quizQuestionsBySession = {
  // ── Session 1 · Cambridge IELTS 18 · Test 3 · Reading Passage 1 ──
  // Questions 1–13 as printed in the book. Answer key derived from the
  // passage; the letter each index maps to is noted per question.
  //   Q1–4   section matching  → options _sectionsAH (0=A … 7=H)
  //   Q5–8   summary gaps      → ONE WORD ONLY, graded case-insensitively
  //   Q9–13  person matching   → options _people (0=A … 3=D)
  // ── Session 1 · Cambridge IELTS 18 · Test 3 · Reading Passage 1 ──
  // Deliberately SHORT: three medium-difficulty comprehension items rather
  // than the book's full 13-question set. The study measures reading
  // behaviour, not English proficiency, so the questions exist only to give
  // the reading a natural purpose. Answers are recorded but never shown to
  // the participant and never used to evaluate them.
  //
  // The three items deliberately draw on the START, MIDDLE and END of the
  // passage, so the responses of someone who disengaged part-way still
  // carry information.
  1: [
    QuizQuestion(
      id: 's1q1',
      groupHeader: 'Questions 1–3',
      prompt: '1. According to the passage, why does concrete have such a '
          'large carbon footprint?',
      options: [
        'Concrete has to be transported over very long distances.',
        'The raw materials of concrete are rare and hard to obtain.',
        'Producing cement releases carbon dioxide, and concrete is used on '
            'an enormous scale.',
        'Concrete buildings need to be rebuilt every few decades.',
      ],
      correctIndex: 2, // Sections A + B
    ),
    QuizQuestion(
      id: 's1q2',
      prompt: '2. True or False: Cross-laminated timber is light, but as '
          'strong as concrete and steel.',
      options: ['True', 'False'],
      correctIndex: 0, // Section E — "light but has the strength of…"
    ),
    QuizQuestion(
      id: 's1q3',
      prompt: '3. What problem does the passage mention with using waste '
          'products such as fly ash in concrete?',
      options: [
        'They make the resulting concrete much weaker.',
        'They can only be used in low-rise buildings.',
        'They cost considerably more than ordinary cement.',
        'Shipping them a long way can cancel out the carbon they save.',
      ],
      correctIndex: 3, // Section G — Surgenor on life-cycle calculations
    ),
  ],




  // // ── Session 2 · IELTS-style, long & dry ─────────────────────────
  // 2: [
  //   QuizQuestion(
  //     id: 's2q1',
  //     prompt:
  //         'Q1 (True/False/Not Given): Before standardization, the main cost '
  //         'problem with early containers was the price of building the '
  //         'boxes themselves.',
  //     options: _tfng,
  //     correctIndex: 1, // False — the cost of repeated handling was.
  //   ),
  //   QuizQuestion(
  //     id: 's2q2',
  //     prompt:
  //         'Q2 (True/False/Not Given): The 1958 committees fixed the '
  //         'container width at eight feet mainly because of highway '
  //         'regulations in most American states.',
  //     options: _tfng,
  //     correctIndex: 0, // True
  //   ),
  //   QuizQuestion(
  //     id: 's2q3',
  //     prompt:
  //         'Q3 (True/False/Not Given): The largest container operator of the '
  //         'late 1950s immediately adopted the new national standard '
  //         'lengths.',
  //     options: _tfng,
  //     correctIndex: 1, // False — refused for years.
  //   ),
  //   QuizQuestion(
  //     id: 's2q4',
  //     prompt:
  //         'Q4 (True/False/Not Given): The Japanese delegation to ISO later '
  //         'withdrew its request for special exceptions.',
  //     options: _tfng,
  //     correctIndex: 2, // Not Given
  //   ),
  //   QuizQuestion(
  //     id: 's2q5',
  //     prompt:
  //         'Q5: Which paragraph describes the dispute over the design of the '
  //         'corner fittings?',
  //     options: ['Paragraph B', 'Paragraph C', 'Paragraph D', 'Paragraph E'],
  //     correctIndex: 3,
  //   ),
  //   QuizQuestion(
  //     id: 's2q6',
  //     prompt:
  //         'Q6: Which paragraph compares the container\'s effect on trade '
  //         'with the effect of tariff reductions?',
  //     options: ['Paragraph D', 'Paragraph E', 'Paragraph F', 'Paragraph G'],
  //     correctIndex: 2,
  //   ),
  //   QuizQuestion(
  //     id: 's2q7',
  //     prompt: 'Q7: The deadlock over the corner fitting ended because',
  //     options: [
  //       'a completely new third design was invented.',
  //       'the American patent holder gave up its royalties under government '
  //           'pressure.',
  //       'the European design proved too weak for larger ships.',
  //       'ISO imposed a compromise design by majority vote.',
  //     ],
  //     correctIndex: 1,
  //   ),
  //   QuizQuestion(
  //     id: 's2q8',
  //     prompt:
  //         'Q8: According to the passage, the American eight-foot width '
  //         'survived the international negotiations mainly because',
  //     options: [
  //       'it was technically superior to the alternatives.',
  //       'European railways eventually changed their loading rules.',
  //       'the scale of transatlantic trade gave the American position '
  //           'practical weight.',
  //       'the British and French delegations supported it from the start.',
  //     ],
  //     correctIndex: 2,
  //   ),
  //   QuizQuestion(
  //     id: 's2q9',
  //     prompt:
  //         'Q9: The writer mentions Felixstowe and Tanjung Pelepas as '
  //         'examples of',
  //     options: [
  //       'ports that declined after containerization.',
  //       'minor harbours that became globally important.',
  //       'cities that resisted the new standard.',
  //       'the first ports to install container cranes.',
  //     ],
  //     correctIndex: 1,
  //   ),
  //   QuizQuestion(
  //     id: 's2q10',
  //     prompt:
  //         'Q10: In the final paragraph, the writer suggests that the '
  //         'container standard succeeded because',
  //     options: [
  //       'engineers eventually found the optimal design.',
  //       'the parties who lost least accepted their losses early.',
  //       'governments forced all operators to comply.',
  //       'the negotiations attracted wide public attention.',
  //     ],
  //     correctIndex: 1,
  //   ),
  // ],

  // // ── Session 3 · hardest ─────────────────────────────────────────
  // 3: [
  //   QuizQuestion(
  //     id: 's3q1',
  //     prompt:
  //         'Q1 (True/False/Not Given): The writer believes the debate about '
  //         'industrial-era living standards remains open mainly because too '
  //         'little evidence has survived.',
  //     options: _tfng,
  //     correctIndex: 1, // False — "less because evidence is scarce…"
  //   ),
  //   QuizQuestion(
  //     id: 's3q2',
  //     prompt:
  //         'Q2 (True/False/Not Given): Money wage records survive mostly for '
  //         'workers whose experience may not have been typical.',
  //     options: _tfng,
  //     correctIndex: 0, // True
  //   ),
  //   QuizQuestion(
  //     id: 's3q3',
  //     prompt:
  //         'Q3 (True/False/Not Given): The choice between a Laspeyres and a '
  //         'Paasche index was first debated by economic historians in the '
  //         'twentieth century.',
  //     options: _tfng,
  //     correctIndex: 2, // Not Given
  //   ),
  //   QuizQuestion(
  //     id: 's3q4',
  //     prompt:
  //         'Q4 (True/False/Not Given): Both sides of the height debate '
  //         'accept that adult stature is influenced by factors that can no '
  //         'longer be separated.',
  //     options: _tfng,
  //     correctIndex: 0, // True — "both sides agree…"
  //   ),
  //   QuizQuestion(
  //     id: 's3q5',
  //     prompt: 'Q5: The "antebellum puzzle" refers to the finding that',
  //     options: [
  //       'military recruits were taller in wartime than in peacetime.',
  //       'heights fell in periods when real wages appeared to be rising.',
  //       'child labor increased while urban disease declined.',
  //       'wage series and household budgets gave identical results.',
  //     ],
  //     correctIndex: 1,
  //   ),
  //   QuizQuestion(
  //     id: 's3q6',
  //     prompt:
  //         'Q6: What problem does the writer identify with historical '
  //         'household budgets?',
  //     options: [
  //       'They were collected by observers whose purposes biased the '
  //           'samples.',
  //       'They ignored the earnings of women and children.',
  //       'Too few of them were ever collected to be useful.',
  //       'They recorded spending but not income.',
  //     ],
  //     correctIndex: 0,
  //   ),
  //   QuizQuestion(
  //     id: 's3q7',
  //     prompt:
  //         'Q7: The example of candles and electric light is used to '
  //         'illustrate that',
  //     options: [
  //       'the price of lighting fell dramatically after industrialization.',
  //       'technological progress always improves welfare.',
  //       'long-run comparisons depend on which quantity is chosen to be '
  //           'held fixed.',
  //       'eighteenth-century consumers had fewer choices than modern ones.',
  //     ],
  //     correctIndex: 2,
  //   ),
  //   QuizQuestion(
  //     id: 's3q8',
  //     prompt:
  //         'Q8: According to the writer, most practitioners respond to the '
  //         'conceptual critique of welfare measurement by',
  //     options: [
  //       'rejecting it as philosophically confused.',
  //       'accepting it in principle but using many measures whose errors '
  //           'are unlikely to be correlated.',
  //       'abandoning long-run index numbers altogether.',
  //       'restricting their claims to the twentieth century.',
  //     ],
  //     correctIndex: 1,
  //   ),
  //   QuizQuestion(
  //     id: 's3q9',
  //     prompt:
  //         'Q9: The writer regards the disagreement between wage and height '
  //         'evidence for the early industrial decades as',
  //     options: [
  //       'a temporary problem that digitized archives will resolve.',
  //       'proof that biological measures are unreliable.',
  //       'itself an informative finding about how unevenly change was '
  //           'distributed.',
  //       'a reason to prefer household budgets over both.',
  //     ],
  //     correctIndex: 2,
  //   ),
  //   QuizQuestion(
  //     id: 's3q10',
  //     prompt: 'Q10: Which statement best expresses the writer\'s own view?',
  //     options: [
  //       'Quantitative history should be abandoned as arithmetic '
  //           'interpretation.',
  //       'The choice of measure largely determines the history that gets '
  //           'written.',
  //       'Real wages remain the most reliable single measure of welfare.',
  //       'The critics of index numbers have won the argument.',
  //     ],
  //     correctIndex: 1,
  //   ),
  // ],
};
