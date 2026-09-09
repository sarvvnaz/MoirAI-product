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
  final Map<String, int> _answers = {};
  bool _loading = true;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final items = await ApiService.getMeasureItems(widget.timepoint);
    if (!mounted) return;
    if (items == null || items.isEmpty) {
      // Nothing due for this arm — move on without showing anything.
      _goNext();
      return;
    }
    setState(() {
      _items = items;
      _loading = false;
    });
  }

  void _goNext() {
    if (!mounted) return;
    Navigator.of(context).pushReplacement(
      MaterialPageRoute(builder: (_) => widget.nextPage()),
    );
  }

  Future<void> _submit() async {
    final missing = _items.firstWhere(
      (i) => !_answers.containsKey(i['code']),
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
            for (final item in _items) ...[
              _buildItem(item),
              const SizedBox(height: 26),
            ],
          ],
        ),
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
        else
          _likert(code, scale),
      ],
    );
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
