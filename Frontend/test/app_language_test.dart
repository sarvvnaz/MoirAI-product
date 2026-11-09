import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:moirai/l10n/app_language.dart';

void main() {
  setUp(() async {
    SharedPreferences.setMockInitialValues({});
    await AppLanguage.instance.load();
  });

  testWidgets('switch translates copy and direction while keeping entered text', (tester) async {
    final controller = TextEditingController();
    await tester.pumpWidget(LanguageScope(child: MaterialApp(home: Builder(builder: (context) {
      final language = AppLanguage.of(context);
      return Directionality(textDirection: language.direction, child: Scaffold(body: Column(children: [
        const AppText('شروع'),
        const AppText('هدف', translate: false),
        TextField(controller: controller),
        TextButton(onPressed: language.toggle, child: const Text('Switch')),
      ])));
    }))));
    await tester.enterText(find.byType(TextField), 'My own answer');
    await tester.tap(find.text('Switch'));
    await tester.pumpAndSettle();
    expect(find.text('Start'), findsOneWidget);
    expect(find.text('هدف'), findsOneWidget);
    expect(controller.text, 'My own answer');
    expect(AppLanguage.instance.direction, TextDirection.ltr);
    expect((await SharedPreferences.getInstance()).getString('moirai.language'), 'en');
    await tester.tap(find.text('Switch'));
    await tester.pumpAndSettle();
    expect(find.text('شروع'), findsOneWidget);
    expect(AppLanguage.instance.direction, TextDirection.rtl);
    expect(controller.text, 'My own answer');
    await tester.pumpWidget(const SizedBox());
    controller.dispose();
  });

  test('saved language is restored', () async {
    SharedPreferences.setMockInitialValues({'moirai.language': 'en'});
    await AppLanguage.instance.load();
    expect(AppLanguage.instance.code, 'en');
  });
}
