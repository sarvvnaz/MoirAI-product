import 'dart:async';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
// ignore: deprecated_member_use
import 'dart:html' as html;
import '../data/study_steps.dart';
import '../services/api_service.dart';
import '../theme/app_colors.dart';
import '../widgets/study_scaffold.dart';
import 'study_session_page.dart';

/// Minimal extension-setup step (after the prep/feedback page, right before
/// the study session — the extension is needed from the session onward).
class ExtensionSetupPage extends StatefulWidget {
  final int userId;
  final Uint8List? pdfBytes;
  final String? pdfName;
  const ExtensionSetupPage({
    super.key,
    required this.userId,
    this.pdfBytes,
    this.pdfName,
  });

  @override
  State<ExtensionSetupPage> createState() => _ExtensionSetupPageState();
}

class _ExtensionSetupPageState extends State<ExtensionSetupPage> {
  bool? _connected;
  bool _checking = false;

  // Auto-detects the install: polls until the extension answers, so the
  // participant only downloads + loads it and the page confirms by itself.
  Timer? _autoCheck;

  // This is the LAST hop into the study session, so the image gate is
  // re-checked here as well as on the prepare page. A participant who
  // reloaded, resumed, or navigated back would otherwise walk straight past
  // the prepare-page check into a session with no reminder to show.
  bool _reminderReady = true;
  Timer? _reminderPoll;

  @override
  void initState() {
    super.initState();
    _autoCheck = Timer.periodic(
      const Duration(seconds: 4),
      (_) => _check(silent: true),
    );
    _checkReminder();
    _reminderPoll = Timer.periodic(
      const Duration(seconds: 4),
      (_) => _checkReminder(),
    );
  }

  /// Polls attempted before asking the server to generate again.
  /// ~10 x 4s, comfortably longer than a normal 30-60s generation, so a
  /// retry only fires when the first attempt really did fail.
  static const int _pollsBeforeRetry = 10;
  int _reminderPolls = 0;
  bool _retrying = false;

  Future<void> _checkReminder() async {
    final ready = await ApiService.isReminderReady();
    if (!mounted) return;
    setState(() => _reminderReady = ready);
    if (ready) {
      _reminderPoll?.cancel();
      return;
    }

    // Entry to the session is now hard-gated on the image, so a failed
    // generation would strand the participant here forever — the prepare page
    // no longer waits, and nothing else would ever try again. Re-trigger
    // periodically so the gate can be satisfied rather than just enforced.
    _reminderPolls++;
    if (_reminderPolls % _pollsBeforeRetry == 0 && !_retrying) {
      _retrying = true;
      try {
        await ApiService.generateReminderSet(count: 1);
      } catch (_) {
        // Next poll tries again; nothing useful to show the participant.
      } finally {
        _retrying = false;
      }
    }
  }

  @override
  void dispose() {
    _autoCheck?.cancel();
    _reminderPoll?.cancel();
    super.dispose();
  }

  Future<void> _check({bool silent = false}) async {
    if (_checking || _connected == true) return;
    if (!silent) setState(() => _checking = true);
    bool ok = false;
    try {
      ok = await ApiService.connectExtension();
    } catch (e) {
      debugPrint('⚠️ extension connect failed: $e');
    }
    if (mounted) {
      setState(() {
        // Silent polls only ever upgrade to connected — they never flash
        // the red "not connected" error while the participant is mid-setup.
        if (!silent || ok) _connected = ok;
        _checking = false;
      });
      if (ok) _autoCheck?.cancel();
    }
  }

  void _download() {
    if (kIsWeb) {
      html.window.open(
        ApiService.resolveBackendUrl('/static/moirai-extension.zip'),
        '_blank',
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return StudyScaffold(
      currentStep: StudyStep.prepare,
      // This is the LAST hop into a session, so BOTH preconditions are
      // enforced here rather than earlier. A session needs the extension (it
      // is what shows the reminder) and it needs an image (a reminder with
      // nothing to show is not an intervention). Missing either produces a
      // session that looks normal in the data and measured nothing.
      bottomBar: Builder(
        builder: (_) {
          final extensionOk = _connected == true;
          final ready = _reminderReady;
          final blocker = !extensionOk
              ? 'می‌تونی بدون افزونه ادامه بدی.'
              : (!_reminderReady
                    ? 'تصویر آینده‌ات هنوز آماده نشده — چند لحظه صبر کن 🌱'
                    : null);
          return Row(
            children: [
              if (blocker != null)
                Expanded(
                  child: Text(
                    blocker,
                    style: TextStyle(
                      fontSize: 13,
                      color: AppColors.navy.withOpacity(0.75),
                    ),
                  ),
                )
              else
                const Spacer(),
              SizedBox(
                width: 200,
                child: StudyPrimaryButton(
                  label: 'باز کردن فایل',
                  onPressed: !ready
                      ? null
                      : () => Navigator.of(context).pushReplacement(
                          MaterialPageRoute(
                            builder: (_) => StudySessionPage(
                              userId: widget.userId,
                              pdfBytes: widget.pdfBytes,
                              pdfName: widget.pdfName,
                            ),
                          ),
                        ),
                ),
              ),
            ],
          );
        },
      ),
      child: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(28),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 560),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const Text(
                  'افزونه‌ی یادآور',
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    fontSize: 20,
                    fontWeight: FontWeight.bold,
                    color: AppColors.navy,
                  ),
                ),
                const SizedBox(height: 10),
                const Text(
                  'یادآوری بیرون از مویرای؛ نصب اختیاری.',
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    fontSize: 14.5,
                    height: 1.8,
                    color: AppColors.navy,
                  ),
                ),
                const SizedBox(height: 12),
                // Sets expectations for the two-condition design WITHOUT
                // priming: participants are told the reminder varies, but not
                // which one is "the real one" and not when to expect which.
                // Knowing a given image is the personalized one would change
                // how they react to it, and that reaction is the measurement.
                const Text(
                  'یادآورهای داخل مویرای به افزونه نیاز ندارن.',
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    fontSize: 13.5,
                    height: 1.9,
                    color: AppColors.navy,
                  ),
                ),
                const SizedBox(height: 18),
                Container(
                  padding: const EdgeInsets.all(18),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(14),
                    border: Border.all(
                      color: _connected == true
                          ? AppColors.mint
                          : AppColors.purple.withOpacity(0.3),
                      width: 1.5,
                    ),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        '۱. دانلود و خارج کردن فایل از حالت فشرده\n'
                        '۲. باز کردن chrome://extensions و روشن کردن Developer mode\n'
                        '۳. زدن Load unpacked و انتخاب پوشه‌ی افزونه\n'
                        '۴. برگرد اینجا و «بررسی اتصال» رو بزن',
                        textDirection: TextDirection.rtl,
                        style: TextStyle(
                          fontSize: 13.5,
                          height: 2.1,
                          color: AppColors.navy,
                        ),
                      ),
                      const SizedBox(height: 14),
                      Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          OutlinedButton.icon(
                            onPressed: _download,
                            style: OutlinedButton.styleFrom(
                              side: const BorderSide(color: AppColors.purple),
                              shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(10),
                              ),
                            ),
                            icon: const Icon(
                              Icons.download_rounded,
                              size: 18,
                              color: AppColors.purple,
                            ),
                            label: const Text(
                              'دانلود افزونه',
                              style: TextStyle(
                                fontSize: 13.5,
                                color: AppColors.purple,
                              ),
                            ),
                          ),
                          const SizedBox(width: 10),
                          ElevatedButton.icon(
                            onPressed: _checking ? null : _check,
                            style: ElevatedButton.styleFrom(
                              backgroundColor: _connected == true
                                  ? AppColors.mint
                                  : AppColors.purple,
                              shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(10),
                              ),
                            ),
                            icon: _checking
                                ? const SizedBox(
                                    width: 16,
                                    height: 16,
                                    child: CircularProgressIndicator(
                                      strokeWidth: 2,
                                      color: Colors.white,
                                    ),
                                  )
                                : Icon(
                                    _connected == true
                                        ? Icons.check_rounded
                                        : Icons.link_rounded,
                                    size: 18,
                                    color: _connected == true
                                        ? AppColors.navy
                                        : Colors.white,
                                  ),
                            label: Text(
                              _connected == true ? 'متصل شد ✅' : 'بررسی اتصال',
                              style: TextStyle(
                                fontSize: 13.5,
                                color: _connected == true
                                    ? AppColors.navy
                                    : Colors.white,
                              ),
                            ),
                          ),
                        ],
                      ),
                      if (_connected == false) ...[
                        const SizedBox(height: 10),
                        const Text(
                          'متصل نشد — مطمئن شو افزونه نصب و فعاله، بعد دوباره امتحان کن.',
                          style: TextStyle(
                            fontSize: 12.5,
                            color: Colors.redAccent,
                          ),
                        ),
                      ],
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
