import '../l10n/app_language.dart';
import 'package:flutter/material.dart';
import '../data/study_steps.dart';
import '../services/api_service.dart';
import '../theme/app_colors.dart';
import '../widgets/study_scaffold.dart';
import 'manual_eft_entry_page.dart';
// import 'measures_page.dart';
import 'prepare_page.dart';

/// EFT chat step (work step 12): a guided conversation that walks the
/// participant through building a vivid future episode. A vertical checklist
/// of the 7 questions sits beside the chat and checks off as answers land, so
/// the participant always knows where they are.
class EFTChatPage extends StatefulWidget {
  final int userId;
  const EFTChatPage({super.key, required this.userId});

  @override
  State<EFTChatPage> createState() => _EFTChatPageState();
}

class _EFTChatPageState extends State<EFTChatPage> {
  // Short labels for the checklist rail — must match the backend QUESTIONS
  // order (eft_chat_service_v2.py). The order is the zoom-in ladder: the
  // distal goal, then time (narrowing to a single day), then the sensory
  // five-field schema. Reordering it here without reordering QUESTIONS mislabels
  // every checkmark.
  static const List<String> _questionLabels = [
    'هدف',
    'زمان',
    'مکان',
    'کار',
    'اطراف',
    'افراد',
    'احساس',
  ];

  final List<Map<String, String>> _messages = [];
  final TextEditingController _inputController = TextEditingController();
  final ScrollController _scrollController = ScrollController();

  List<bool> _collected = List.filled(7, false);
  int _activeIndex = 0;
  bool _needsUser = true;
  bool _canStart = false;
  bool _loading = false;

  // Importance of the distal goal (1-6). While true the chip row replaces the
  // text input: this step is a rating, not something to type, and leaving the
  // box open invites an answer the backend would reject.
  bool _awaitingImportance = false;
  int _importanceMin = 1;
  int _importanceMax = 6;
  bool _inspiring = false;

  @override
  void initState() {
    super.initState();
    _sendToServer(message: '', reset: true);
  }

  @override
  void dispose() {
    _inputController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  void _addMessage(String sender, String text) {
    final wasFirst = _messages.isEmpty;
    setState(() => _messages.add({'sender': sender, 'text': text}));
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!_scrollController.hasClients) return;
      // The first message (the long intro) starts from the TOP so its
      // beginning isn't cut off; later messages scroll to the bottom.
      _scrollController.animateTo(
        wasFirst ? 0 : _scrollController.position.maxScrollExtent + 80,
        duration: const Duration(milliseconds: 250),
        curve: Curves.easeOut,
      );
    });
  }

  Future<void> _sendToServer(
      {required String message, bool reset = false, int? importance}) async {
    if (!mounted) return;
    setState(() => _loading = true);
    try {
      final res = await ApiService.eftChat({
        'uid': widget.userId.toString(),
        'message': message,
        'reset': reset,
        if (importance != null) 'importance': importance,
      });
      if (res == null) {
        _addMessage('bot', 'مشکلی در ارتباط با سرور رخ داد. دوباره تلاش کن.');
        return;
      }
      if (res['translation_unavailable'] == true && AppLanguage.instance.isEnglish) {
        _addMessage('bot', "English translation is temporarily unavailable. Showing the original message.");
      }
      final bot = (res['bot'] as String?) ?? '';
      final collected = (res['collected'] as List?)
              ?.map((e) => e == true)
              .toList() ??
          _collected;
      final range = (res['importance_range'] as List?)
          ?.map((e) => (e as num).toInt())
          .toList();
      setState(() {
        _needsUser = (res['needs_user'] as bool?) ?? true;
        _canStart = (res['can_start_session'] as bool?) ?? false;
        _activeIndex = (res['question_index'] as num?)?.toInt() ?? _activeIndex;
        _awaitingImportance = (res['awaiting_importance'] as bool?) ?? false;
        if (range != null && range.length == 2) {
          _importanceMin = range[0];
          _importanceMax = range[1];
        }
        if (collected.length == _questionLabels.length) _collected = collected;
      });
      if (bot.trim().isNotEmpty) _addMessage('bot', bot);
    } catch (e) {
      _addMessage('bot', 'خطایی رخ داد: $e');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _handleSend() async {
    final text = _inputController.text.trim();
    if (text.isEmpty || !_needsUser || _loading) return;
    _inputController.clear();
    _addMessage('user', text);
    await _sendToServer(message: text);
  }

  Future<void> _handleImportance(int value) async {
    if (_loading) return;
    _addMessage('user', '$value');
    await _sendToServer(message: '', importance: value);
  }

  /// Offers example answers for the current step. They go into the input box
  /// rather than the transcript, so the participant edits them into their own
  /// words before sending — an episode they didn't actually imagine is
  /// worthless as data.
  Future<void> _handleInspire() async {
    if (_loading || _inspiring) return;
    setState(() => _inspiring = true);
    try {
      final suggestions = await ApiService.eftInspire();
      if (!mounted) return;
      if (suggestions.isEmpty) {
        _addMessage('bot', 'الان نتونستم نمونه بیارم — با جمله‌ی خودت شروع کن، هرچقدر کوتاه.');
        return;
      }
      await showModalBottomSheet<void>(
        context: context,
        backgroundColor: Colors.white,
        shape: const RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(18)),
        ),
        builder: (ctx) => Padding(
          padding: const EdgeInsets.fromLTRB(16, 18, 16, 24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              AppText(
                'یکی رو انتخاب کن و به دلخواه تغییرش بده',
                textAlign: TextAlign.center,
                style: TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.bold,
                    color: AppColors.navy.withOpacity(0.85)),
              ),
              const SizedBox(height: 14),
              for (final s in suggestions)
                Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: InkWell(
                    onTap: () {
                      _inputController.text = s;
                      _inputController.selection = TextSelection.fromPosition(
                        TextPosition(offset: s.length),
                      );
                      Navigator.of(ctx).pop();
                    },
                    borderRadius: BorderRadius.circular(12),
                    child: Container(
                      width: double.infinity,
                      padding: const EdgeInsets.symmetric(
                          horizontal: 14, vertical: 12),
                      decoration: BoxDecoration(
                        color: AppColors.lavender,
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: AppText(s,
                          style: const TextStyle(
                              fontSize: 14.5,
                              height: 1.6,
                              color: AppColors.navy)),
                    ),
                  ),
                ),
            ],
          ),
        ),
      );
    } finally {
      if (mounted) setState(() => _inspiring = false);
    }
  }

  // Keep the product route without reintroducing the research questionnaire.
  void _goNext() {
    Navigator.of(context).pushReplacement(MaterialPageRoute(
      builder: (_) => PreparePage(userId: widget.userId),
    ));
  }

  /// Manual fallback, offered only while the chat is unsubmitted. Pushed (not
  /// replaced) so «بازگشت به گفتگو» lands back on this live conversation with
  /// its messages intact. If they SUBMIT there, that page clears the stack —
  /// so arriving back here always means they chose to keep chatting.
  Future<void> _openManualEntry() async {
    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => ManualEftEntryPage(userId: widget.userId),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final compact = MediaQuery.of(context).size.width < 640;
    return StudyScaffold(
      currentStep: StudyStep.chat,
      bottomBar: Row(
        children: [
          if (_loading)
            const SizedBox(
              width: 18,
              height: 18,
              child: CircularProgressIndicator(strokeWidth: 2.5),
            ),
          const SizedBox(width: 8),
          AppText(
            _canStart
                ? 'تصویر آینده‌ات آماده است ✅'
                : 'تکمیل‌شده: ${_collected.where((e) => e).length} از ${_questionLabels.length}',
            style: const TextStyle(fontSize: 13, color: AppColors.navy),
          ),
          const Spacer(),
          SizedBox(
            width: 150,
            child: StudyPrimaryButton(
              label: 'ادامه',
              // Enabled only after the episode is confirmed.
              onPressed: _canStart ? _goNext : null,
            ),
          ),
        ],
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (!compact) _buildRail(),
          Expanded(child: _buildChatColumn(compact)),
        ],
      ),
    );
  }

  // ── importance rating (1-6 chips) ──────────────────────────
  /// One tap instead of a typed turn. Rating how much the goal matters is what
  /// ties the present self to the future one, but it is not an imagining task —
  /// making participants type it would cost attention the rest of the chat needs.
  Widget _buildImportanceRow() {
    final values = [
      for (int v = _importanceMin; v <= _importanceMax; v++) v,
    ];
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 12),
      color: Colors.white,
      child: Column(
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              for (final v in values)
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 4),
                  child: InkWell(
                    onTap: _loading ? null : () => _handleImportance(v),
                    borderRadius: BorderRadius.circular(24),
                    child: Container(
                      width: 42,
                      height: 42,
                      alignment: Alignment.center,
                      decoration: BoxDecoration(
                        color: AppColors.lavender,
                        shape: BoxShape.circle,
                        border: Border.all(
                            color: AppColors.purple.withOpacity(0.45)),
                      ),
                      child: AppText(
                        '$v',
                        style: const TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.bold,
                          color: AppColors.navy,
                        ),
                      ),
                    ),
                  ),
                ),
            ],
          ),
          const SizedBox(height: 6),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              // In RTL the first child renders on the RIGHT, which is where
              // the «1» chip sits — so the low-end label comes first.
              AppText('$_importanceMin = خیلی کم',
                  style: TextStyle(
                      fontSize: 11.5,
                      color: AppColors.navy.withOpacity(0.6))),
              AppText('$_importanceMax = خیلی زیاد',
                  style: TextStyle(
                      fontSize: 11.5,
                      color: AppColors.navy.withOpacity(0.6))),
            ],
          ),
        ],
      ),
    );
  }

  // ── vertical checklist rail ────────────────────────────────
  Widget _buildRail() {
    return Container(
      width: 150,
      color: AppColors.navy,
      padding: const EdgeInsets.symmetric(vertical: 18, horizontal: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const AppText(
            'قدم‌ها',
            textAlign: TextAlign.center,
            style: TextStyle(
                color: Colors.white,
                fontSize: 13,
                fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 14),
          for (int i = 0; i < _questionLabels.length; i++)
            _railItem(i),
        ],
      ),
    );
  }

  Widget _railItem(int i) {
    final done = _collected[i];
    final current = !done && i == _activeIndex && !_canStart;
    final Color dotColor =
        done ? AppColors.mint : (current ? Colors.white : Colors.white24);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        children: [
          AnimatedContainer(
            duration: const Duration(milliseconds: 250),
            width: 22,
            height: 22,
            decoration: BoxDecoration(
              color: done ? AppColors.mint : Colors.transparent,
              shape: BoxShape.circle,
              border: Border.all(color: dotColor, width: 2),
              boxShadow: current
                  ? [
                      BoxShadow(
                          color: Colors.white.withOpacity(0.5),
                          blurRadius: 8,
                          spreadRadius: 1)
                    ]
                  : null,
            ),
            child: done
                ? const Icon(Icons.check, size: 14, color: AppColors.navy)
                : (current
                    ? const Center(
                        child: SizedBox(
                          width: 7,
                          height: 7,
                          child: DecoratedBox(
                            decoration: BoxDecoration(
                                color: Colors.white, shape: BoxShape.circle),
                          ),
                        ),
                      )
                    : null),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: AppText(
              _questionLabels[i],
              style: TextStyle(
                color: done
                    ? AppColors.mint
                    : (current ? Colors.white : Colors.white54),
                fontSize: 13.5,
                fontWeight:
                    current ? FontWeight.bold : FontWeight.normal,
              ),
            ),
          ),
        ],
      ),
    );
  }

  // ── chat column ────────────────────────────────────────────
  Widget _buildChatColumn(bool compact) {
    return Column(
      children: [
        // Compact screens: show a slim progress strip instead of the rail.
        if (compact)
          Container(
            color: AppColors.navy,
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceEvenly,
              children: [
                for (int i = 0; i < 7; i++)
                  Icon(
                    _collected[i]
                        ? Icons.check_circle
                        : (i == _activeIndex && !_canStart
                            ? Icons.radio_button_checked
                            : Icons.radio_button_unchecked),
                    size: 18,
                    color: _collected[i]
                        ? AppColors.mint
                        : (i == _activeIndex && !_canStart
                            ? Colors.white
                            : Colors.white24),
                  ),
              ],
            ),
          ),
        Expanded(
          child: ListView.builder(
            controller: _scrollController,
            padding: const EdgeInsets.all(16),
            itemCount: _messages.length,
            itemBuilder: (context, index) {
              final msg = _messages[index];
              final isBot = msg['sender'] == 'bot';
              return Align(
                alignment:
                    isBot ? AlignmentDirectional.centerStart : AlignmentDirectional.centerEnd,
                child: Container(
                  margin: const EdgeInsets.symmetric(vertical: 5),
                  padding:
                      const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                  constraints: const BoxConstraints(maxWidth: 460),
                  decoration: BoxDecoration(
                    color: isBot ? Colors.white : AppColors.purple,
                    borderRadius: BorderRadius.circular(14),
                  ),
                  child: AppText(
                    msg['text'] ?? '',
                    translate: false,
                    style: TextStyle(
                      fontSize: 15,
                      height: 1.8,
                      color: isBot ? AppColors.navy : Colors.white,
                    ),
                  ),
                ),
              );
            },
          ),
        ),
        if (_needsUser && _awaitingImportance)
          _buildImportanceRow()
        else if (_needsUser)
          Container(
            padding: const EdgeInsets.all(10),
            color: Colors.white,
            child: Row(
              children: [
                // Escape hatch for a blank imagination — the single most
                // common place these participants stall, so it carries a
                // visible label rather than being an icon alone: an unlabelled
                // glyph is easy to miss, and shows nothing at all if the icon
                // font fails to render.
                TextButton.icon(
                  style: TextButton.styleFrom(
                    foregroundColor: AppColors.purple,
                    padding: const EdgeInsets.symmetric(horizontal: 10),
                    visualDensity: VisualDensity.compact,
                  ),
                  icon: _inspiring
                      ? const SizedBox(
                          width: 16,
                          height: 16,
                          child: CircularProgressIndicator(strokeWidth: 2.5),
                        )
                      : const AppText('💡', style: TextStyle(fontSize: 16)),
                  label: const AppText('',
                      style: TextStyle(
                          fontSize: 13, fontWeight: FontWeight.w600)),
                  onPressed: (_loading || _inspiring) ? null : _handleInspire,
                ),
                Expanded(
                  child: TextField(
                    controller: _inputController,
                    onSubmitted: (_) => _handleSend(),
                    textInputAction: TextInputAction.send,
                    decoration: InputDecoration(
                      hintText: tr('پاسخ خود را بنویس...', context),
                      filled: true,
                      fillColor: AppColors.lavender,
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(12),
                        borderSide: BorderSide.none,
                      ),
                      contentPadding: const EdgeInsets.symmetric(
                          horizontal: 14, vertical: 10),
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                IconButton(
                  icon:
                      const Icon(Icons.send_rounded, color: AppColors.purple),
                  onPressed: _loading ? null : _handleSend,
                ),
              ],
            ),
          )
        else if (_canStart)
          Container(
            padding: const EdgeInsets.all(14),
            color: Colors.white,
            child: AppText(
              'وقتی آماده بودی، دکمه‌ی «ادامه» را بزن 🌱',
              textAlign: TextAlign.center,
              style: TextStyle(
                  fontSize: 14, color: AppColors.navy.withOpacity(0.7)),
            ),
          ),
        // Escape hatch — disappears for good once the episode is submitted
        // (through either path), since the two are mutually exclusive.
        if (!_canStart)
          Container(
            width: double.infinity,
            color: Colors.white,
            padding: const EdgeInsets.only(bottom: 10, left: 10, right: 10),
            child: Center(
              child: TextButton(
                onPressed: _loading ? null : _openManualEntry,
                style: TextButton.styleFrom(
                  padding: const EdgeInsets.symmetric(
                      horizontal: 10, vertical: 4),
                  minimumSize: Size.zero,
                  tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                ),
                child: AppText(
                  'گفتگو کمکت نمی‌کنه؟ پاسخ‌ها رو دستی بنویس ',
                  style: TextStyle(
                    fontSize: 12.5,
                    color: AppColors.purple.withOpacity(0.85),
                    decoration: TextDecoration.underline,
                  ),
                ),
              ),
            ),
          ),
      ],
    );
  }
}
