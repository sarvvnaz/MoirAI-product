import 'dart:typed_data';

/// Validates size and signature before a document reaches the PDF renderer.
void validatePdf(Uint8List? bytes) {
  if (bytes == null || bytes.length > 30 * 1024 * 1024) {
    throw const FormatException('فایل PDF باید کمتر از ۳۰ مگابایت باشد.');
  }
  if (bytes.length < 5 || String.fromCharCodes(bytes.take(5)) != '%PDF-') {
    throw const FormatException('لطفاً یک فایل PDF معتبر انتخاب کن.');
  }
}
