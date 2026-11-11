import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'translations.dart';

class AppLanguage extends ChangeNotifier {
  static final instance = AppLanguage._();
  AppLanguage._();
  String code = 'fa';
  bool get isEnglish => code == 'en';
  TextDirection get direction =>
      isEnglish ? TextDirection.ltr : TextDirection.rtl;
  Future<void> load() async {
    final saved = (await SharedPreferences.getInstance()).getString(
      'moirai.language',
    );
    code = saved == 'en' ? 'en' : 'fa';
  }

  Future<void> toggle() async {
    code = isEnglish ? 'fa' : 'en';
    notifyListeners();
    await (await SharedPreferences.getInstance()).setString(
      'moirai.language',
      code,
    );
  }

  static AppLanguage of(BuildContext context) =>
      context.dependOnInheritedWidgetOfExactType<LanguageScope>()?.notifier ??
      instance;
}

class LanguageScope extends InheritedNotifier<AppLanguage> {
  LanguageScope({super.key, required super.child})
    : super(notifier: AppLanguage.instance);
}

String tr(String value, BuildContext context) {
  if (!AppLanguage.of(context).isEnglish) return value;
  final direct = englishText[value];
  if (direct != null) return direct;
  if (value.endsWith(' = خیلی کم')) return value.split(' = ')[0] + ' = very little';
  if (value.endsWith(' = خیلی زیاد')) return value.split(' = ')[0] + ' = very much';
  final completed = RegExp(r'^تکمیل‌شده: (\d+) از (\d+)$').firstMatch(value);
  if (completed != null) return 'Completed: ${completed[1]} of ${completed[2]}';
  if (value.startsWith('ثبت نشد (')) return 'Could not save. Please try again.';
  if (value.startsWith('مشکلی پیش آمد ('))
    return 'Something went wrong. Please try again.';
  if (value.startsWith('هنوز داریم تلاش'))
    return 'Your image is still being prepared…';
  return value;
}

/// Resolves product copy at build time, retaining the existing Text styling.
class AppText extends StatelessWidget {
  final String data;
  final bool translate;
  final TextStyle? style;
  final TextAlign? textAlign;
  final TextDirection? textDirection;
  final int? maxLines;
  final TextOverflow? overflow;
  final bool? softWrap;
  final String? semanticsLabel;
  const AppText(
    this.data, {
    super.key,
    this.translate = true,
    this.style,
    this.textAlign,
    this.textDirection,
    this.maxLines,
    this.overflow,
    this.softWrap,
    this.semanticsLabel,
  });
  @override
  Widget build(BuildContext context) => Text(
    translate ? tr(data, context) : data,
    style: style,
    textAlign: textAlign,
    textDirection: textDirection,
    maxLines: maxLines,
    overflow: overflow,
    softWrap: softWrap,
    semanticsLabel: semanticsLabel,
  );
}
