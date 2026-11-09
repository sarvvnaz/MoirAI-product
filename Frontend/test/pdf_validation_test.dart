import 'dart:typed_data';
import 'package:flutter_test/flutter_test.dart';
import 'package:moirai/services/pdf_validation.dart';

void main() {
  test('accepts PDF data regardless of its document topic', () {
    expect(() => validatePdf(Uint8List.fromList('%PDF-1.7'.codeUnits)), returnsNormally);
  });
  test('rejects empty, unavailable, and disguised non-PDF data', () {
    for (final bytes in [null, Uint8List(0), Uint8List.fromList('hello.pdf'.codeUnits)]) {
      expect(() => validatePdf(bytes), throwsFormatException);
    }
  });
  test('rejects a PDF larger than 30 MB', () {
    final bytes = Uint8List(30 * 1024 * 1024 + 1)..setAll(0, '%PDF-'.codeUnits);
    expect(() => validatePdf(bytes), throwsFormatException);
  });
}
