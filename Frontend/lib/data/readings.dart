/// Reading passages for the study session.
///
/// TWO PASSAGES, written to authentic IELTS Academic Reading specification:
///
///   1 — "The Sailing Stones" (~730 words, paragraphs A-G). Passage 1
///       difficulty: narrative-expository, concrete subject, chronological
///       structure. A scientific puzzle and its resolution.
///   2 — "The Collapse of the Northern Cod" (~830 words, paragraphs A-H).
///       Passage 2-3 difficulty: argumentative, competing explanations,
///       hedged claims, an institutional subject chosen to be genuinely dry.
///
/// LENGTH IS A DESIGN PARAMETER, not a stylistic choice. A real Academic
/// Reading paper is ~2,150 words across three passages in 60 minutes, i.e.
/// ~36 words/min. These two total ~1,560 words, so in the 35-minute window
/// the participant faces ~44 words/min — about 1.24x authentic pace. Tight,
/// like a rushed practice test, but completable.
///
/// The previous passages ran to ~1,400 words EACH. Two of those would have
/// meant ~80 words/min, over twice authentic pace: not demanding but
/// unfinishable, and a task nobody can complete measures giving up rather
/// than procrastinating. The primary measures cannot separate those two.
///
/// The second consequence of authentic length is dosage. 26 questions
/// guarantee the participant is still working at minute 20, so the second
/// scheduled cue is actually reachable — which is what keeps exposure equal
/// across arms.
///
/// All passages here are ORIGINAL texts written in the style, register and
/// difficulty of the exam. Real IELTS passages are copyrighted; passage 3
/// below is licensed material retained for reference and is NOT used by
/// default (see StudyConfig.sessionPassages).
class ReadingPassage {
  final String title;

  /// The italic strapline under the title, if the passage has one.
  final String subtitle;

  /// Citation shown under the title (empty for the original passages).
  final String source;

  /// Short exam-style instruction line shown above the text.
  final String instructions;

  /// The passage body. Paragraphs separated by blank lines; paragraphs are
  /// labelled "A." ... "H." at the start of the line, as in the exam, so that
  /// matching-information questions can refer to them.
  final String body;

  const ReadingPassage({
    required this.title,
    required this.instructions,
    required this.body,
    this.subtitle = '',
    this.source = '',
  });

  /// True while a licensed passage still has to be pasted in. Lets the UI
  /// show a clear notice instead of an empty reading pane.
  bool get isPlaceholder => body.trim().startsWith('<<<');
}

// ───────────────────────────────────────────────────────────────────
// PASSAGE 1 — Academic Reading Passage 1 difficulty
// ───────────────────────────────────────────────────────────────────
const String _sailingStones = '''
A. Racetrack Playa is a dry lake bed in the northern reaches of Death Valley National Park, California. It is remarkably flat: across its 4.5-kilometre length, the elevation varies by less than four centimetres. The surface is a pale, cracked crust of dried mud, and for most of the year it holds no water at all. What has drawn visitors and scientists to this otherwise unremarkable place for nearly a century is a scattering of stones — some weighing more than 300 kilograms — each of which trails a furrow in the mud behind it. The tracks run for tens or even hundreds of metres. Some are straight; others curve gently, or turn at sharp angles, and a few double back on themselves. Until very recently, nobody had ever seen a stone move.

B. The stones themselves are not native to the playa floor. They are fragments of dolomite and syenite that have broken away from the steep slopes at the southern end of the basin and tumbled down onto the flat surface below. Their arrival is easily explained. Their subsequent journeys are not. Early visitors assumed that the tracks were the work of pranksters, but the absence of any footprints in the soft mud made this difficult to sustain. By the 1940s the phenomenon had attracted the attention of professional geologists, and a series of formal investigations began.

C. The first published explanation, advanced in 1948, held that the stones were driven by dust devils — the small, intense whirlwinds that are common in desert basins. The hypothesis had obvious appeal, but it did not survive scrutiny. Dust devils are short-lived and highly localised, and it was hard to see how they could produce the long, parallel tracks that several stones sometimes shared. Nor could they account for the observation that stones of very different masses appeared to have travelled comparable distances.

D. A second theory proposed that the playa surface, once wet, became slippery enough for ordinary desert winds to push the stones along it. Researchers calculated the wind speeds this mechanism would require and arrived at figures approaching several hundred kilometres per hour — far in excess of anything ever recorded at the site. Direct measurement of the wet surface compounded the difficulty: the mud proved considerably less slick than the theory demanded.

E. Attention then turned to ice. In winter the playa occasionally floods to a depth of a few centimetres, and overnight temperatures fall below freezing. Several researchers suggested that the stones became locked into large sheets of ice, which the wind could then drag across the flooded surface, carrying the stones with them. This "ice raft" hypothesis accounted neatly for the parallel tracks, since stones frozen into a single sheet would necessarily move together. It was, however, extremely difficult to test. Field visits were infrequent, the flooding was unpredictable, and the movement events themselves appeared to be rare — perhaps one in a decade.

F. The question was finally settled between 2011 and 2014 by a team who installed a weather station at the playa and fitted fifteen stones with GPS units. In December 2013 the playa flooded. On the mornings that followed, thin sheets of ice — no more than three to six millimetres thick — formed over the shallow water. As the sun rose, the ice began to break apart into large floating panels. A light wind, of only three to five metres per second, was sufficient to push these panels across the pond, and where a panel met a stone it shunted the stone forward through the soft mud beneath. The stones moved slowly, at a few centimetres per second, and only for a few minutes at a time. Several were recorded travelling more than sixty metres over the course of a single winter.

G. The result was, in one sense, an anticlimax. The mechanism required no exceptional forces: no violent winds, no thick ice, no rare geological event. It required only a precise and uncommon combination of entirely ordinary conditions — enough rain to form a shallow pond, nights cold enough to freeze a thin crust upon it, and sun and wind arriving in the right order the following morning. The rarity of the movement was explained not by the rarity of any single ingredient but by the improbability of all of them coinciding. The investigation had taken sixty-six years, and its conclusion was that nothing unusual had been happening at all.
''';

// ───────────────────────────────────────────────────────────────────
// PASSAGE 2 — Academic Reading Passage 2/3 difficulty
// ───────────────────────────────────────────────────────────────────
const String _northernCod = '''
A. For almost five centuries the continental shelf off Newfoundland supported one of the most productive fisheries on earth. The northern cod stock that spawned there had drawn European fleets since the sixteenth century, and by the middle of the twentieth it was yielding some 250,000 tonnes a year to Canadian and foreign vessels alike. In July 1992 the Canadian government closed the fishery altogether. The spawning stock had fallen to roughly one per cent of its historical level. Some thirty thousand people lost their livelihoods in a single announcement, and a moratorium that was intended to last two years has, in practice, never been lifted.

B. The immediate cause is not seriously disputed. From the late 1950s the arrival of factory freezer trawlers transformed the scale on which cod could be taken. These vessels could work in almost any weather, process and freeze their catch at sea, and remain on the grounds for weeks at a time. Landings climbed steeply, peaking at more than 800,000 tonnes in 1968, and then fell away. Canada's extension of its exclusive economic zone to 200 nautical miles in 1977 removed most foreign vessels from the grounds, but the domestic fleet expanded to occupy the space they had vacated, encouraged by public investment in new vessels and processing plants.

C. What remains contested is why the decline was not detected and acted upon in time. Stock assessments throughout the 1980s consistently reported a large and harvestable population. These estimates were produced by the federal fisheries department and depended heavily on catch rates reported by the commercial fleet — the quantity of fish landed for each unit of fishing effort expended. The reasoning appeared sound: if the catch taken per hour of trawling held steady, the underlying population was presumably stable too.

D. The assumption was mistaken, and its failure has since become a standard illustration in the literature on resource management. Cod do not distribute themselves evenly through the water; they aggregate, and they aggregate more tightly as their numbers fall. A shrinking population may concentrate into progressively smaller and denser shoals, which vessels equipped with sonar are able to locate with increasing efficiency. Catch rates therefore held up even as the stock collapsed beneath them, a phenomenon now generally termed hyperstability. The fleet's effort data were, in effect, measuring the improvement of its own technology rather than the abundance of the fish.

E. Independent research surveys, which sampled fixed locations irrespective of where the fish were expected to be, told a different story, and from the middle of the 1980s their results diverged sharply from the commercial figures. The divergence was noticed at the time. Several scientists within the department argued that the quotas being set were far too high, and one of them later published analyses concluding that the stock had been overfished by a wide margin for a decade. Their assessments did not prevail. The explanations offered by subsequent public inquiries were institutional rather than scientific: the department was charged both with conserving the stock and with supporting the industry that depended upon it, and reductions in quota carried costs that were immediate and highly visible, while their benefits were deferred and uncertain.

F. A competing account attributes the collapse principally to environmental change. Water temperatures on the shelf fell during the late 1980s, and cold conditions are known both to slow the growth of cod and to reduce the survival of young fish. Seal populations, meanwhile, had risen substantially following restrictions on hunting. A number of commentators, including several within the fishing industry itself, maintained that these factors rather than fishing pressure accounted for the disappearance of the stock.

G. Most subsequent analyses treat the environmental account as insufficient on its own. Comparable cold periods had occurred before without producing anything of the kind, and the collapse was too rapid and too complete to be explained by a modest decline in recruitment. The more defensible position is that environmental stress acted upon a population already reduced to the point at which it had no capacity left to absorb it. The distinction is not merely academic, because the two accounts imply quite different lessons: on one reading the fishery was unlucky, on the other it was mismanaged.

H. The stock has not recovered. Three decades after the moratorium the biomass remains far below the levels of the 1960s, and the ecosystem itself appears to have reorganised around the absence of its former dominant predator. Capelin and shrimp, once prey, now occupy much of the space that cod formerly held, and there is evidence that they suppress any recovery by consuming cod eggs and larvae. Whether the system will eventually return to its earlier state, or has instead settled into a stable alternative, remains unresolved. What is no longer disputed is the more general lesson: an assessment method that draws its data from the industry it is meant to regulate will tend to report what that industry is able to catch, and not what is left in the sea.
''';

const ReadingPassage _passage1 = ReadingPassage(
  title: 'The Sailing Stones',
  subtitle: 'How a sixty-six-year mystery in Death Valley was finally solved',
  instructions: 'You should spend about 15 minutes on Questions 1-13, which '
      'are based on Reading Passage 1 below.',
  body: _sailingStones,
);

const ReadingPassage _passage2 = ReadingPassage(
  title: 'The Collapse of the Northern Cod',
  subtitle: 'What the closure of the Newfoundland fishery revealed about how '
      'fish stocks are counted',
  instructions: 'You should spend about 20 minutes on Questions 14-26, which '
      'are based on Reading Passage 2 below.',
  body: _northernCod,
);

/// Keyed by passage id. `StudyConfig.sessionPassages` selects which are shown.
const Map<int, ReadingPassage> readingsBySession = {
  1: _passage1,
  2: _passage2,
};
