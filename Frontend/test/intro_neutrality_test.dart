// The introduction is shown to every participant BEFORE they are routed into
// a condition, and the two conditions differ in what happens afterwards.
//
// If the intro names personalization, AI-generated cues, motivation or focus,
// it tells the participant what is being tested — which shapes the very
// self-reports the study collects, and does so invisibly. This reads the
// source rather than pumping widgets, because the risk is a WORD reappearing
// in the copy, not a rendering fault.
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  final introFiles = [
    'lib/screens/intro_page.dart',
    'lib/screens/start_page.dart',
  ];

  String source() =>
      introFiles.map((f) => File(f).readAsStringSync()).join('\n');

  group('condition-neutral introduction', () {
    test('never names a condition or the manipulation', () {
      // Backend labels. These belong in exports, never on a participant
      // screen.
      const banned = [
        'EFT',
        'control group',
        'experimental',
        'personalized condition',
        'generic condition',
        'شخصی‌سازی',
        'شخصی‌ساز',
        'گروه کنترل',
        'گروه آزمایش',
      ];
      final text = source();
      for (final term in banned) {
        expect(text.contains(term), isFalse,
            reason: 'intro copy must not contain "$term"');
      }
    });

    test('does not reveal what is being measured', () {
      // Naming the outcome invites the participant to perform it.
      const banned = [
        'انگیزه', // motivation
        'تمرکز', // focus
        'حواس‌پرتی', // distraction
        'اهمال', // procrastination
        'مقایسه', // comparison
        'هوش مصنوعی', // AI
      ];
      final text = source();
      for (final term in banned) {
        expect(text.contains(term), isFalse,
            reason: 'intro copy must not contain "$term"');
      }
    });

    test('keeps the neutral framing that both conditions share', () {
      final text = source();
      // The one line that legitimately prepares every participant for the
      // reminders without explaining them.
      expect(text.contains('چند پیام کوتاه'), isTrue);
      // Routes may differ — said plainly, without implying groups.
      expect(text.contains('ممکنه برای افراد مختلف کمی متفاوت باشه'), isTrue);
    });

    test('still tells the participant their honest answer is what matters',
        () {
      expect(source().contains('پاسخ درست یا غلطی وجود نداره'), isTrue);
    });
  });
}
