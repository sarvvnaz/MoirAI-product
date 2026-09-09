/// Reading passages for the study sessions, keyed by session number.
///
/// Difficulty deliberately escalates:
///   1 — medium TOEFL-style passage (~600 words), accessible topic.
///   2 — hard IELTS Reading Passage 3 length (~900 words), intentionally dry
///       subject (institutional/bureaucratic history) to induce natural
///       disengagement.
///   3 — hardest: dense, abstract methodological text (~950 words).
///
/// All passages are ORIGINAL texts written in the authentic style and
/// difficulty of the exams (real TOEFL/IELTS passages are copyrighted).
/// To swap in licensed exam material later, only this file needs editing.
class ReadingPassage {
  final String title;

  /// The italic strapline under the title, if the passage has one.
  final String subtitle;

  /// Citation shown under the title (empty for the original passages).
  final String source;

  /// Short exam-style instruction line shown above the text.
  final String instructions;

  /// The passage body. Paragraphs separated by blank lines; IELTS-style
  /// passages label paragraphs "A." … "H." at the start of the line.
  final String body;

  const ReadingPassage({
    required this.title,
    required this.instructions,
    required this.body,
    this.subtitle = '',
    this.source = '',
  });

  /// True while a licensed passage still has to be pasted in (see
  /// `_CAMBRIDGE_18_T3_P1` below). Lets the UI show a clear notice instead
  /// of an empty reading pane.
  bool get isPlaceholder => body.trim().startsWith('<<<');
}

/// ───────────────────────────────────────────────────────────────────
/// Cambridge IELTS 18 · Test 3 · Reading Passage 1
/// "Materials to take us beyond concrete"
///
/// Supplied by the researcher from their own licensed copy of the book, for
/// non-commercial academic use, with the citation displayed on screen (see
/// `source` below). Text © Cambridge University Press — do not redistribute
/// this file outside the study.
/// ───────────────────────────────────────────────────────────────────
const String _cambridge18T3P1 = '''
A. Concrete is the second most used substance in the global economy, after water — and one of the world's biggest single sources of greenhouse gas emissions. The chemical process by which cement, the key ingredient of concrete, is created results in large quantities of carbon dioxide. The UN estimates that there will be 9.8 billion people living on the planet by mid-century. They will need somewhere to live. If concrete is the only answer to the construction of new cities, then carbon emissions will soar, aggravating global warming. And so scientists have started innovating with other materials, in a scramble for alternatives to a universal commodity that has underpinned our modern life for many years.

B. The problem with replacing concrete is that it is so very good at what it does. Chris Cheeseman, an engineering professor at Imperial College London, says the key thing to consider is the extent to which concrete is used around the world, and is likely to continue to be used. 'Concrete is not a high-carbon product. Cement is high carbon, but concrete is not. But it is the scale on which it is used that makes it high carbon. The sheer scale of manufacture is so huge, that is the issue.'

C. Not only are the ingredients of concrete relatively cheap and found in abundance in most places around the globe, the stuff itself has marvellous properties: Portland cement, the vital component of concrete, is mouldable and pourable, but quickly sets hard. Cheeseman also notes another advantage: concrete and steel have similar thermal expansion properties, so steel can be used to reinforce concrete, making it far stronger and more flexible as a building material than it could be on its own. According to Cheeseman, all these factors together make concrete hard to beat. 'Concrete is amazing stuff. Making anything with similar properties is going to be very difficult.'

D. A possible alternative to concrete is wood. Making buildings from wood may seem like a rather medieval idea, but climate change is driving architects to turn to treated timber as a possible resource. Recent years have seen the emergence of tall buildings constructed almost entirely from timber. Vancouver, Vienna and Brumunddal in Norway are all home to tall, wooden buildings.

E. Using wood to construct buildings, however, is not straightforward. Wood expands as it absorbs moisture from the air and is susceptible to pests, not to mention fire. But treating wood and combining it with other materials can improve its properties. Cross-laminated timber is engineered wood. An adhesive is used to stick layers of solid-sawn timber together, crosswise, to form building blocks. This material is light but has the strength of concrete and steel. Construction experts say that wooden buildings can be constructed at a greater speed than ones of concrete and steel and the process, it seems, is quieter.

F. Stora Enso is Europe's biggest supplier of cross-laminated timber, and its vice-president Markus Mannström reports that the company is seeing increasing demand globally for building in wood, with climate change concerns the key driver. Finland, with its large forests, where Stora Enso is based, has been leading the way, but the company is seeing a rise in demand for its timber products across the world, including in Asia. Of course, using timber in a building also locks away the carbon that it absorbed as it grew. But even treated wood has its limitations and only when a wider range of construction projects has been proven in practice will it be possible to see wood as a real alternative to concrete in constructing tall buildings.

G. Fly ash and slag from iron ore are possible alternatives to cement in a concrete mix. Fly ash, a byproduct of coal-burning power plants, can be incorporated into concrete mixes to make up as much as 15 to 30% of the cement, without harming the strength or durability of the resulting mix. Iron-ore slag, a byproduct of the iron-ore smelting process, can be used in a similar way. Their incorporation into concrete mixes has the potential to reduce greenhouse gas emissions.

But Anna Surgenor, of the UK's Green Building Council, notes that although these waste products can save carbon in the concrete mix, their use is not always straightforward. 'It's possible to replace the cement content in concrete with waste products to lower the overall carbon impact. But there are several calculations that need to be considered across the entire life cycle of the building — these include factoring in where these materials are being shipped from. If they are transported over long distances, using fossil fuels, the use of alternative materials might not make sense from an overall carbon reduction perspective.'

H. While these technologies are all promising ideas, they are either unproven or based on materials that are not abundant. In their overview of innovation in the concrete industry, Felix Preston and Johanna Lehne of the UK's Royal Institute of International Affairs reached the conclusion that, 'Some novel cements have been discussed for more than a decade within the research community, without breaking through. At present, these alternatives are rarely as cost-effective as conventional cement, and they face raw-material shortages and resistance from customers.'
''';

const Map<int, ReadingPassage> readingsBySession = {
  1: ReadingPassage(
    title: 'Materials to take us beyond concrete',
    subtitle: 'Concrete is everywhere, but it\'s bad for the planet, '
        'generating large amounts of carbon dioxide — alternatives are '
        'being developed',
    source: 'Cambridge IELTS 18 · Test 3 · Reading Passage 1 '
        '(Cambridge University Press)',
    instructions:
        '',
    body: _cambridge18T3P1,
  ),
  2: _shippingContainers,
  3: _historicalLivingStandards,
};

const ReadingPassage _shippingContainers = ReadingPassage(
    title: 'The Standardization of the Shipping Container',
    instructions:
        'Answer ALL '
        'questions. For True / False / Not Given questions choose:\n'
        'True — the statement agrees with the information in the passage.\n'
        'False — the statement contradicts the information.\n'
        'Not Given — there is no information on this in the passage.',
    body: '''
A. It is difficult to think of an object at once so consequential and so uninteresting to look at as the intermodal shipping container. The corrugated steel box, typically twenty or forty feet long, is now so uniform across the world's ports that it is easy to assume its dimensions were settled quickly and amicably. The historical record shows otherwise. The container's standard measurements were the product of nearly fifteen years of committee negotiation, involving domestic trade associations, national standards bodies, the International Organization for Standardization (ISO), and several governments, and the process was marked at almost every stage by disagreement over matters that outsiders found trivial, such as the placement of lifting fittings and the thickness of corner posts.

B. Before standardization, containers of a sort had existed for decades. Railways in Europe and North America had experimented since the 1920s with demountable boxes that could be transferred between flatcars and lorries. These early containers varied enormously: wooden or steel, five to ten feet long, with or without wheels, lifted by cranes, forklifts or ramps. Each railway or shipping line designed containers to fit its own vehicles, with the predictable result that a box that travelled efficiently within one company's network had to be unpacked and repacked the moment its cargo passed to another carrier. The cost of this repeated handling, rather than the cost of the boxes themselves, was the principal obstacle to through-transport of goods.

C. The first serious attempt at unification came not from the shipping industry but from the American trucking and railroad sectors. In 1958, the United States Maritime Administration, concerned that federal subsidies were about to finance a generation of mutually incompatible ships, convened two expert committees to recommend standard container dimensions. The committees quickly agreed that height should be fixed at eight feet, and after some argument settled on a width of eight feet as well, chiefly because this was the maximum that could travel on highways in most American states without special permits. Length proved far more contentious. Existing operators had fleets built around ten, twelve, seventeen, twenty, twenty-four and thirty-five foot boxes, and each argued that its own investment should define the national standard. The eventual compromise — a family of lengths at ten, twenty, thirty and forty feet, each a multiple of the ten-foot module — satisfied almost no one, and the largest operator of the day, whose thirty-five foot containers fit neither series, refused for years to adopt it.

D. When the question moved to the international stage in 1961, under ISO Technical Committee 104, the disagreements multiplied. European railways operated under loading restrictions that made the American eight-foot width awkward, and several delegations pressed for a narrower box. The British argued for dimensions compatible with their smaller rail wagons; the French had a national container series of their own; and the Japanese delegation, whose domestic roads at the time limited vehicle widths severely, requested exceptions that would have created, in effect, a parallel standard. Five years of correspondence, draft proposals and postal ballots followed. The eight-foot width ultimately survived, largely because the volume of transatlantic trade gave the American position a practical weight that procedural objections could not overcome.

E. A separate and, by most accounts, even more tedious battle concerned the corner fitting — the steel casting at each corner of the container by which it is lifted, stacked and locked to vehicles. Since every crane, spreader and twist-lock in the world would have to engage with this fitting, its internal apertures had to be identical everywhere, to tolerances of a few millimeters. Two incompatible designs, one American and one European, each protected by patents, competed for adoption. The deadlock was broken only when the American patent holder, under pressure from its own government, released its design royalty-free in 1963. Even then, testing revealed that the released design was too weak for the newest generation of larger ships, and a strengthened version had to be agreed, drawn, circulated and re-balloted, delaying final publication of the standard until 1965.

F. The economic effects of these dull negotiations were anything but dull. Once any container could be handled by any crane, stacked in any cell of any ship and locked to any chassis in any country, the cost of moving manufactured goods across oceans fell steeply. Economists studying trade flows in the decades after standardization have attributed to the container a larger share of the growth in world trade than to all tariff reductions of the same period combined. Ports that had employed thousands of dockworkers to handle loose cargo were rebuilt around the box; entire cities that had lived on break-bulk shipping declined, while previously minor harbours with deep water and cheap land — Felixstowe in England, Tanjung Pelepas in Malaysia — rose to global significance.

G. Historians of technology draw a wider lesson from the episode. Standardization is often imagined as a technical exercise in finding the best design, but the container's history suggests it is better understood as a political process of distributing losses: every dimension chosen destroyed someone's existing investment, and the standard succeeded not because it was optimal — engineers at the time agreed it was not — but because the parties who lost least were persuaded to accept their losses early. The very dullness of the proceedings, on this view, was a condition of their success, since committees survive only where passions can be kept procedural.
''',
);

const ReadingPassage _historicalLivingStandards = ReadingPassage(
    title: 'Measuring the Past: The Problem of Historical Living Standards',
    instructions:
        'You should spend about 20 minutes on this passage. The questions '
        'below include True / False / Not Given items and multiple-choice '
        'items about the writer\'s views. Choose the best answer for each.',
    body: '''
A. Whether ordinary people became better or worse off during the first century of industrialization is among the oldest questions in economic history, and it remains unsettled less because evidence is scarce than because the question itself is resistant to measurement. To say that living standards rose is to make a quantitative claim about aggregate welfare; yet welfare is not directly observable, and every proxy through which historians approach it — wages, prices, heights, mortality, consumption — embodies assumptions that predetermine, to a degree rarely acknowledged, the answer that will be found.

B. The most venerable proxy is the real wage: the money wage of some defined worker divided by the price of some defined basket of goods. Each element of this construction conceals difficulties. Money wage series survive mainly for urban, male, unionized or institutionally employed workers — builders on cathedral accounts, laborers on college estates — whose experience may be unrepresentative precisely because it was recorded. The composition of the basket is more troublesome still. If the basket is held constant across a century, the calculation ignores the substitutions consumers actually made as relative prices shifted; if the basket is updated, the index ceases to compare like with like. The choice between these procedures, formally the choice between a Laspeyres and a Paasche index, can reverse the direction of a measured trend, and the decision between them cannot be made on evidence internal to the series: it is a decision about what the historian wishes the number to mean.

C. Dissatisfaction with wage evidence has driven a turn toward biological measures, of which adult stature is the most exploited. Height, the argument runs, integrates net nutrition over childhood — food intake minus the claims of disease and labor — and is recorded for populations, such as military recruits, that wage data ignore. The anthropometric literature has produced one of the field's most cited paradoxes: in several industrializing economies, average heights appear to have fallen during decades when conventional real-wage series were rising. Some scholars read this "antebellum puzzle" as proof that monetary measures overstate early industrial welfare, pointing to urban disease environments and the intensification of child labor. Others reply that recruitment records are themselves selected samples — armies accept different men in war and peace — and that the apparent decline may be an artifact of changing selection rather than deteriorating nutrition. The debate has been technically fertile but substantively inconclusive, in part because both sides agree that height responds to influences no one can now apportion.

D. A third tradition attempts to bypass proxies altogether by reconstructing household budgets: what families actually earned, from all members and all sources, and what they actually bought. Where such accounts survive they are revealing, showing, for instance, how heavily early industrial households depended on the earnings of women and children, whose wages appear in no standard series. But budgets were collected by observers — clergymen, factory inspectors, philanthropic societies — with purposes of their own, usually the demonstration of poverty or of improvidence, and their samples were chosen accordingly. Aggregating documents produced to prove opposite theses does not cancel their biases; it merely averages them into invisibility.

E. It might be supposed that these are technical problems, to be resolved as archives are digitized and methods refined. The more radical position, associated with a minority of historians, is that the difficulties are conceptual and therefore permanent. Welfare comparisons across long periods, they argue, require a stable unit of account — a common measure of how well a life is going — and no such unit exists between societies whose consumption sets barely overlap. The eighteenth-century laborer bought candles, the twentieth-century worker electric light; the price of "lighting" can be constructed to fall by any factor one likes, depending on whether lumens, hours or social participation is the quantity held fixed. On this view, long-run index numbers do not measure welfare change so much as encode, in apparently neutral arithmetic, a particular theory of what mattered.

F. The pragmatic response, which probably commands the assent of most practitioners, concedes the philosophical point while denying its practical force. All measurement, in any science, rests on conventions; the remedy for a conventional measure is not abandonment but multiplication. Where wages, heights, mortality and budgets all point the same way — as, for the second half of the nineteenth century, they largely do — confidence is warranted, not because any single series is sound, but because their errors are unlikely to be correlated. Where they diverge, as in the early decades of industrialization, the divergence is itself the finding: it marks a period in which the gains and losses of economic change were distributed too unevenly, across regions, occupations and members of households, for any aggregate to summarize.

G. The dispute is thus less about the past than about the ambitions of quantification. Those who construct the indices regard a noisy number as better than none, since without it every claim about long-run change floats free of discipline. Their critics regard the number as worse than none, since it lends the authority of arithmetic to what remains an interpretation. What neither side disputes is that the choice of measure is prior to, and largely determines, the history that gets written — a conclusion that students of any quantitative discipline may find has an application wider than economic history.
''',
);
