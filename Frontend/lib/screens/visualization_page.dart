import 'package:flutter/material.dart';

import '../data/study_steps.dart';
import '../services/api_service.dart';
import '../services/flow_router.dart';
import '../theme/app_colors.dart';
import '../widgets/study_scaffold.dart';

/// The visualization step: the participant's generated future, shown back to
/// them to look at and imagine for a minute or two.
///
/// This is the first time they see the image. Everything before it either
/// collected their words or generated from them; nothing displayed it.
///
/// No enforced timer. The instruction asks for roughly one to two minutes and
/// the Continue button is available immediately — a countdown that locks the
/// button would turn "look at this for a while" into a task to wait out, and
/// for a demo it is one more thing that can misbehave in front of an
/// audience.
class VisualizationPage extends StatefulWidget {
  const VisualizationPage({super.key, required this.userId});

  final int userId;

  @override
  State<VisualizationPage> createState() => _VisualizationPageState();
}

class _VisualizationPageState extends State<VisualizationPage> {
  static const String _instruction =
      'لحظه‌ای به تصویر نگاه کن و خودت رو در این آینده تصور کن.';

  bool _loading = true;
  bool _sending = false;
  String? _imageUrl;
  String? _cue;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final future = await ApiService.getGeneratedFuture();
    if (!mounted) return;
    setState(() {
      _imageUrl = future?['image_url'] as String?;
      _cue = future?['cue'] as String?;
      _loading = false;
    });
  }

  Future<void> _continue() async {
    setState(() => _sending = true);
    // Marked server-side so a refresh does not drop the participant back
    // here, and so the export records that the screen was actually reached.
    await ApiService.markVisualizationSeen(widget.userId);
    if (!mounted) return;
    Navigator.of(context).pushReplacement(
      MaterialPageRoute(builder: (_) => FlowGate(userId: widget.userId)),
    );
  }

  @override
  Widget build(BuildContext context) {
    return StudyScaffold(
      currentStep: StudyStep.prepare,
      bottomBar: Row(
        children: [
          const Spacer(),
          SizedBox(
            width: 190,
            child: StudyPrimaryButton(
              label: 'ادامه',
              busy: _sending,
              onPressed: _sending ? null : _continue,
            ),
          ),
        ],
      ),
      child: _loading
          ? const Center(child: CircularProgressIndicator())
          : SingleChildScrollView(
              padding: const EdgeInsets.fromLTRB(24, 20, 24, 28),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  // The instruction sits ABOVE the scene: it tells the
                  // participant what to do with what they are about to see,
                  // and read afterwards it would arrive too late.
                  Container(
                    padding: const EdgeInsets.symmetric(
                        horizontal: 18, vertical: 16),
                    decoration: BoxDecoration(
                      color: AppColors.purple.withOpacity(0.07),
                      borderRadius: BorderRadius.circular(14),
                    ),
                    child: const Text(
                      _instruction,
                      style: TextStyle(
                          fontSize: 15, height: 2.0, color: AppColors.navy),
                    ),
                  ),
                  const SizedBox(height: 22),
                  if (_imageUrl != null) _buildImage(),
                  if (_cue != null && _cue!.trim().isNotEmpty) ...[
                    const SizedBox(height: 20),
                    Container(
                      padding: const EdgeInsets.all(20),
                      decoration: BoxDecoration(
                        color: Colors.white,
                        borderRadius: BorderRadius.circular(16),
                      ),
                      child: Text(
                        _cue!.trim(),
                        style: const TextStyle(
                            fontSize: 16.5,
                            height: 2.1,
                            color: AppColors.navy),
                      ),
                    ),
                  ],
                  if (_imageUrl == null && (_cue ?? '').trim().isEmpty)
                    // Generation failed or produced nothing. Say so plainly
                    // and let them continue: stranding someone on a blank
                    // screen is worse than a missing image, and the post
                    // questionnaire can still be answered.
                    Padding(
                      padding: const EdgeInsets.symmetric(vertical: 40),
                      child: Text(
                        'ساخت صحنه‌ی تو این بار کامل نشد. می‌تونی ادامه بدی.',
                        textAlign: TextAlign.center,
                        style: TextStyle(
                            fontSize: 15,
                            height: 1.9,
                            color: AppColors.navy.withOpacity(0.7)),
                      ),
                    ),
                ],
              ),
            ),
    );
  }

  Widget _buildImage() {
    return ClipRRect(
      borderRadius: BorderRadius.circular(16),
      child: Image.network(
        ApiService.absoluteUrl(_imageUrl!),
        fit: BoxFit.cover,
        loadingBuilder: (context, child, progress) => progress == null
            ? child
            : const SizedBox(
                height: 260,
                child: Center(child: CircularProgressIndicator()),
              ),
        // A broken image must not take the page down with it.
        errorBuilder: (_, __, ___) => const SizedBox(
          height: 200,
          child: Center(
            child: Icon(Icons.image_not_supported_outlined,
                size: 40, color: AppColors.purple),
          ),
        ),
      ),
    );
  }
}
