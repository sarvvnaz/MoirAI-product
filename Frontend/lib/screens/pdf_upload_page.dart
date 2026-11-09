import '../l10n/app_language.dart';
import 'dart:typed_data';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import '../data/study_steps.dart';
import '../services/pdf_validation.dart';
import '../theme/app_colors.dart';
import '../widgets/study_scaffold.dart';
import 'extension_setup_page.dart';

class PdfUploadPage extends StatefulWidget {
  const PdfUploadPage({super.key, required this.userId});
  final int userId;
  @override
  State<PdfUploadPage> createState() => _PdfUploadPageState();
}

class _PdfUploadPageState extends State<PdfUploadPage> {
  Uint8List? _bytes;
  String? _name;
  String? _error;
  bool _busy = false;

  Future<void> _pick() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final result = await FilePicker.platform.pickFiles(
        type: FileType.custom,
        allowedExtensions: ['pdf'],
        withData: true,
      );
      if (!mounted || result == null) return;
      final file = result.files.single;
      final bytes = file.bytes;
      validatePdf(bytes);
      setState(() {
        _bytes = bytes;
        _name = file.name;
      });
    } on FormatException catch (e) {
      if (mounted) {
        setState(() {
          _error = e.message;
        });
      }
    } catch (_) {
      if (mounted) {
        setState(() {
          _error = 'انتخاب فایل انجام نشد. دوباره تلاش کن.';
        });
      }
    } finally {
      if (mounted) {
        setState(() {
          _busy = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) => StudyScaffold(
    currentStep: StudyStep.study,
    child: Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(32),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Icon(
              Icons.picture_as_pdf_outlined,
              size: 56,
              color: AppColors.purple,
            ),
            const SizedBox(height: 20),
            const AppText(
              'فایلت رو انتخاب کن',
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: 26,
                fontWeight: FontWeight.bold,
                color: AppColors.navy,
              ),
            ),
            const SizedBox(height: 16),
            const AppText(
              'PDF تا ۳۰ مگابایت',
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 24),
            OutlinedButton.icon(
              onPressed: _busy ? null : _pick,
              icon: const Icon(Icons.upload_file),
              label: Padding(
                padding: const EdgeInsets.all(14),
                child: AppText(_busy ? 'در حال انتخاب…' : _name ?? 'انتخاب PDF'),
              ),
            ),
            const SizedBox(height: 12),
            const AppText(
              'فقط در مرورگر باز می‌شه؛ بعد از تازه‌سازی، دوباره انتخابش کن.',
              textAlign: TextAlign.center,
              style: TextStyle(height: 1.8),
            ),
            if (_error != null)
              Padding(
                padding: const EdgeInsets.only(top: 16),
                child: AppText(
                  _error!,
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
              ),
            const SizedBox(height: 24),
            StudyPrimaryButton(
              label: 'ادامه',
              onPressed: _bytes == null || _busy
                  ? null
                  : () => Navigator.of(context).pushReplacement(
                      MaterialPageRoute(
                        builder: (_) => ExtensionSetupPage(
                          userId: widget.userId,
                          pdfBytes: _bytes,
                          pdfName: _name,
                        ),
                      ),
                    ),
            ),
          ],
        ),
      ),
    ),
  );
}
