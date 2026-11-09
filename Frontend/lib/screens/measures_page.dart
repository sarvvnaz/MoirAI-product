import 'package:flutter/material.dart';

import '../data/study_steps.dart';
import '../services/api_service.dart';
import '../theme/app_colors.dart';
import '../widgets/circles_scale.dart';
import '../widgets/study_scaffold.dart';

/// Renders whatever the server says is due at a given timepoint.
///
/// The item bank lives on the backend, so this page knows nothing about which
/// questions exist, which arm gets them, or how they are scored — it renders
/// what it is given. That is what lets the battery change during piloting
/// without shipping a new build to participants mid-study.
///
/// If the server returns no items (the control arm at post_chat, for example)
/// the page skips itself immediately rather than showing an empty form.
class MeasuresPage extends StatefulWidget {
  final int userId;
  final String timepoint;
  final String title;

  /// Where to go once answers are saved — or skipped.
  final Widget Function() nextPage;

  /// Which step to highlight in the progress bar. Measures are attached to
  /// the phase they belong to rather than getting a step of their own; a
  /// progress bar that grows a new box for every questionnaire makes the
  /// study feel longer than it is.
  final StudyStep step;

  const MeasuresPage({
    super.key,
    required this.userId,
    required this.timepoint,
    required this.title,
    required this.nextPage,
    required this.step,
  });

  @override
  State<MeasuresPage> createState() => _MeasuresPageState();
}

class _MeasuresPageState extends State<MeasuresPage> {
  List<Map<String, dynamic>> _items = [];

  /// The participant's own future goal, shown above the items when the
  /// server says this timepoint needs it. The instrumentality wording refers
  /// to "this future goal", so on those pages it must be on screen or the
  /// items ask about something the participant cannot see.
  String? _futureGoal;
  String _goalPrompt = '';

  /// Codes the participant may leave blank (the open-ended prompts).
  Set<String> _optional = {};

  /// int for rated items, String for open-ended ones. Typed as dynamic
  /// because the battery mixes both and the server stores them in separate
  /// columns; forcing one type here is what made an open-ended prompt render
  /// as a rating scale.
  final Map<String, dynamic> _answers = {};

  /// One controller per open-ended item, created lazily and disposed with the
  /// page.
  final Map<String, TextEditingController> _textControllers = {};

  bool _loading = true;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final payload = await ApiService.getMeasurePayload(widget.timepoint);
    final items = payload?['items'] as List<Map<String, dynamic>>?;
    if (!mounted) return;
    if (items == null || items.isEmpty) {
      // Nothing due for this arm — move on without showing anything.
      _goNext();
      return;
    }
    setState(() {
      _items = items;
      _futureGoal = (payload?['future_goal'] as String?)?.trim();
      _goalPrompt = (payload?['goal_prompt_fa'] as String?) ?? '';
      _optional = ((payload?['optional_codes'] as List?) ?? const [])
          .map((e) => e.toString())
          .toSet();
      _loading = false;
    });
  }

  void _goNext() {
    if (!mounted) return;
    Navigator.of(context).pushReplacement(
      MaterialPageRoute(builder: (_) => widget.nextPage()),
    );
  }

  /// Answered means "has a value"; for an open-ended item that means
  /// non-empty text, not merely a touched field.
  bool _isAnswered(Map<String, dynamic> item) {
    if (_optional.contains(item['code'])) return true;
    final v = _answers[item['code']];
    if (v == null) return false;
    if (v is String) return v.trim().isNotEmpty;
    if (v is Map) {
      // A duration needs at least one field filled. An untouched pair of
      // empty boxes is not an answer of zero.
      return v['hours'] != null || v['minutes'] != null;
    }
    return true;
  }

  Future<void> _submit() async {
    final missing = _items.firstWhere(
      (i) => !_isAnswered(i),
      orElse: () => {},
    );
    if (missing.isNotEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('لطفاً به همه‌ی سوال‌ها جواب بده 🙂')),
      );
      return;
    }

    setState(() => _saving = true);
    final ok = await ApiService.saveMeasureResponses(widget.timepoint, _answers);
    if (!mounted) return;
    setState(() => _saving = false);

    if (!ok) {
      // Never trap a participant on a questionnaire because the network
      // blinked — the study continues and the gap is visible in the export.
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('ذخیره نشد، ولی می‌تونی ادامه بدی.')),
      );
    }
    _goNext();
  }

  @override
  void dispose() {
    for (final c in _textControllers.values) {
      c.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return StudyScaffold(
        currentStep: widget.step,
        child: const Center(
          child: Padding(
            padding: EdgeInsets.all(48),
            child: CircularProgressIndicator(),
          ),
        ),
      );
    }

    return StudyScaffold(
      currentStep: widget.step,
      bottomBar: Row(
        children: [
          Expanded(
            child: StudyPrimaryButton(
              label: 'ادامه',
              busy: _saving,
              onPressed: _submit,
            ),
          ),
        ],
      ),
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(28),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              widget.title,
              style: const TextStyle(
                  fontSize: 20,
                  fontWeight: FontWeight.bold,
                  color: AppColors.navy),
            ),
            const SizedBox(height: 20),
            if (_futureGoal != null && _futureGoal!.isNotEmpty) ...[
              _buildGoalBanner(),
              const SizedBox(height: 24),
            ],
            for (final item in _items) ...[
              _buildItem(item),
              const SizedBox(height: 26),
            ],
          ],
        ),
      ),
    );
  }

  /// The participant's own goal, in their own words, above the items that
  /// refer to it.
  ///
  /// Shown identically at pre and post. Half the design is that the two
  /// administrations ask about the SAME future — if the goal were only
  /// visible the first time, the post items would be answered against
  /// whatever the participant happened to remember.
  Widget _buildGoalBanner() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 16),
      decoration: BoxDecoration(
        color: AppColors.purple.withOpacity(0.07),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.purple.withOpacity(0.18)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (_goalPrompt.isNotEmpty)
            Text(
              _goalPrompt,
              style: TextStyle(
                  fontSize: 13.5,
                  height: 1.8,
                  color: AppColors.navy.withOpacity(0.75)),
            ),
          const SizedBox(height: 8),
          Text(
            _futureGoal!,
            style: const TextStyle(
                fontSize: 16,
                height: 2.0,
                fontWeight: FontWeight.w600,
                color: AppColors.navy),
          ),
        ],
      ),
    );
  }

  Widget _buildItem(Map<String, dynamic> item) {
    final code = item['code'] as String;
    final scale = (item['scale'] as Map).cast<String, dynamic>();
    final kind = scale['kind'] as String? ?? 'likert';

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          item['text_fa'] as String? ?? '',
          style: const TextStyle(
              fontSize: 14.5, height: 1.9, color: AppColors.navy),
        ),
        if ((item['helper_fa'] as String? ?? '').isNotEmpty) ...[
          const SizedBox(height: 6),
          Text(
            item['helper_fa'] as String,
            style: TextStyle(
                fontSize: 12.5,
                height: 1.8,
                color: AppColors.navy.withOpacity(0.6)),
          ),
        ],
        const SizedBox(height: 10),
        if (kind == 'circles')
          CirclesScale(
            value: _answers[code],
            onChanged: (v) => setState(() => _answers[code] = v),
            leftLabel: 'خودِ الان',
            rightLabel: 'خودت یک سال دیگه',
          )
        else if (kind == 'choice')
          _choices(code, (scale['options_fa'] as List).cast<String>())
        else if (kind == 'text')
          _freeText(code, multiline: scale['multiline'] == true)
        else if (kind == 'duration')
          _duration(code, scale)
        else
          _likert(code, scale),
      ],
    );
  }

  /// Open-ended items — the goal-elicitation prompt asks the participant to
  /// DESCRIBE something, and there is no rating that could answer it.
  Widget _freeText(String code, {bool multiline = false}) {
    final controller = _textControllers.putIfAbsent(
      code,
      () => TextEditingController(text: _answers[code] as String? ?? ''),
    );
    return TextField(
      controller: controller,
      minLines: multiline ? 3 : 1,
      maxLines: multiline ? 6 : 1,
      textInputAction:
          multiline ? TextInputAction.newline : TextInputAction.done,
      style: const TextStyle(fontSize: 14.5, height: 1.7),
      decoration: InputDecoration(
        hintText: 'جوابت رو اینجا بنویس…',
        filled: true,
        fillColor: Colors.white,
        contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide(color: AppColors.purple.withOpacity(0.35)),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide(color: AppColors.purple.withOpacity(0.25)),
        ),
      ),
      // No setState per keystroke: the map is read on submit, and rebuilding
      // the whole battery on every character makes typing stutter.
      onChanged: (v) => _answers[code] = v,
    );
  }

  /// Hours + minutes. Deliberately NOT a Likert: this is the only
  /// quantitative outcome in the battery, and collapsing a duration into a
  /// rating would throw away everything that makes it one.
  ///
  /// The map value is {'hours': int, 'minutes': int}; the server stores both
  /// the raw entry and the normalised total.
  Widget _duration(String code, Map<String, dynamic> scale) {
    final current = (_answers[code] as Map?)?.cast<String, dynamic>() ??
        <String, dynamic>{};
    final maxHours = (scale['max_hours'] as int?) ?? 168;

    void update(String field, String raw) {
      final n = int.tryParse(raw.trim());
      final next = Map<String, dynamic>.from(current);
      if (n == null) {
        next.remove(field);
      } else {
        // Clamped rather than rejected: a participant who types 75 minutes
        // means something, and refusing the keystroke mid-entry is worse
        // than accepting the nearest valid value. The server validates
        // again regardless.
        next[field] = field == 'hours'
            ? n.clamp(0, maxHours)
            : n.clamp(0, 59);
      }
      setState(() => _answers[code] = next);
    }

    Widget box(String field, String label) => Expanded(
          child: Row(
            children: [
              SizedBox(
                width: 74,
                child: TextField(
                  controller: _textControllers.putIfAbsent(
                    '$code.$field',
                    () => TextEditingController(
                        text: current[field]?.toString() ?? ''),
                  ),
                  keyboardType: TextInputType.number,
                  textAlign: TextAlign.center,
                  style: const TextStyle(fontSize: 16),
                  decoration: InputDecoration(
                    hintText: '۰',
                    filled: true,
                    fillColor: Colors.white,
                    contentPadding:
                        const EdgeInsets.symmetric(vertical: 12),
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(10),
                      borderSide:
                          BorderSide(color: AppColors.purple.withOpacity(0.3)),
                    ),
                  ),
                  onChanged: (v) => update(field, v),
                ),
              ),
              const SizedBox(width: 8),
              Text(label,
                  style: const TextStyle(
                      fontSize: 14, color: AppColors.navy)),
            ],
          ),
        );

    return Row(children: [box('hours', 'ساعت'), box('minutes', 'دقیقه')]);
  }

  Widget _likert(String code, Map<String, dynamic> scale) {
    final min = scale['min'] as int? ?? 1;
    final max = scale['max'] as int? ?? 5;
    final labels = (scale['labels_fa'] as Map?)?.map(
            (k, v) => MapEntry(int.parse(k.toString()), v.toString())) ??
        {};
    return Wrap(
      alignment: WrapAlignment.center,
      spacing: 6,
      runSpacing: 6,
      children: [
        for (int v = min; v <= max; v++)
          _chip(
            selected: _answers[code] == v,
            label: labels[v] ?? '$v',
            onTap: () => setState(() => _answers[code] = v),
          ),
      ],
    );
  }

  Widget _choices(String code, List<String> options) {
    return Column(
      children: [
        for (int i = 0; i < options.length; i++)
          Padding(
            padding: const EdgeInsets.only(bottom: 6),
            child: _chip(
              selected: _answers[code] == i + 1,
              label: options[i],
              // 1-based so a stored value never collides with "unanswered".
              onTap: () => setState(() => _answers[code] = i + 1),
              fullWidth: true,
            ),
          ),
      ],
    );
  }

  Widget _chip({
    required bool selected,
    required String label,
    required VoidCallback onTap,
    bool fullWidth = false,
  }) {
    final child = Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: selected
            ? AppColors.purple.withValues(alpha: 0.12)
            : Colors.transparent,
        border: Border.all(
          color: selected ? AppColors.purple : Colors.grey.shade300,
          width: selected ? 2 : 1,
        ),
        borderRadius: BorderRadius.circular(10),
      ),
      child: Text(
        label,
        textAlign: TextAlign.center,
        style: TextStyle(
          fontSize: 13,
          fontWeight: selected ? FontWeight.bold : FontWeight.normal,
          color: selected ? AppColors.purple : AppColors.navy,
        ),
      ),
    );

    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(10),
      child: fullWidth ? SizedBox(width: double.infinity, child: child) : child,
    );
  }
}
