import '../l10n/app_language.dart';
import 'dart:convert';
import 'package:flutter/material.dart';
import '../data/study_steps.dart';
import '../services/api_service.dart';
import '../theme/app_colors.dart';
import '../widgets/study_scaffold.dart';
import '../services/flow_router.dart';

/// Anonymous account creation. The user picks any unique ID (they can write
/// something anonymous if they don't want to be recognized) plus a simple
/// password and an optional first name. Internally all data is keyed on the
/// numeric user id, so the chosen ID is only a login handle.
class SignUpPage extends StatefulWidget {
  const SignUpPage({super.key});

  @override
  State<SignUpPage> createState() => _SignUpPageState();
}

class _SignUpPageState extends State<SignUpPage> {
  final _formKey = GlobalKey<FormState>();
  final TextEditingController _idController = TextEditingController();
  final TextEditingController _passwordController = TextEditingController();
  final TextEditingController _nameController = TextEditingController();

  bool _loading = false;
  String? _idError; // server-side uniqueness error

  @override
  void dispose() {
    _idController.dispose();
    _passwordController.dispose();
    _nameController.dispose();
    super.dispose();
  }

  Future<void> _signup() async {
    setState(() => _idError = null);
    if (!_formKey.currentState!.validate()) return;
    setState(() => _loading = true);
    try {
      final response = await ApiService.signup({
        'participant_id': _idController.text.trim(),
        'password': _passwordController.text.trim(),
        'first_name': _nameController.text.trim().isEmpty
            ? null
            : _nameController.text.trim(),
      });

      if (response.statusCode == 200 || response.statusCode == 201) {
        final body = jsonDecode(response.body) as Map<String, dynamic>;
        final token = body['access_token'] as String?;
        final userId = (body['user']?['id'] as num?)?.toInt();

        if (token != null && userId != null) {
          await ApiService.storeAuth(token, userId);
          if (!mounted) return;
          Navigator.pushReplacement(
            context,
            MaterialPageRoute(
              builder: (_) => FlowGate(userId: userId),
            ),
          );
          return;
        }
      } else if (response.statusCode == 409) {
        setState(() => _idError = 'این شناسه قبلاً انتخاب شده — یکی دیگر امتحان کن');
        _formKey.currentState!.validate();
        return;
      }
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: AppText('مشکلی پیش آمد (${response.statusCode})')),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: AppText('مشکل در اتصال به سرور')),
      );
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  InputDecoration _decoration(String label, {String? hint}) {
    return InputDecoration(
      labelText: tr(label, context),
      hintText: hint == null ? null : tr(hint, context),
      filled: true,
      fillColor: Colors.white,
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: BorderSide.none,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return StudyScaffold(
      currentStep: StudyStep.account,
      bottomBar: Row(
        children: [
          TextButton(
            onPressed: () => Navigator.pushReplacementNamed(context, '/login'),
            child: const AppText('حساب داری؟ وارد شو',
                style: TextStyle(color: AppColors.purple)),
          ),
          const Spacer(),
          SizedBox(
            width: 170,
            child: StudyPrimaryButton(
              label: 'بساز و ادامه بده',
              busy: _loading,
              onPressed: _signup,
            ),
          ),
        ],
      ),
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Form(
          key: _formKey,
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const AppText(
                'ایجاد حساب کاربری ',
                style: TextStyle(
                    fontSize: 22,
                    fontWeight: FontWeight.bold,
                    color: AppColors.navy),
              ),
              const SizedBox(height: 10),
              const AppText(
                'برای ذخیره‌ی گفتگو و یادآورت، یک حساب بساز.',
                style:
                    TextStyle(fontSize: 15, height: 1.9, color: AppColors.navy),
              ),
              const SizedBox(height: 24),
              TextFormField(
                controller: _idController,
                textDirection: TextDirection.ltr,
                validator: (v) {
                  if (_idError != null) return tr(_idError!, context);
                  final t = (v ?? '').trim();
                  if (t.length < 3) return tr('شناسه حداقل ۳ حرف باشد', context);
                  if (t.length > 32) return tr('شناسه حداکثر ۳۲ حرف باشد', context);
                  return null;
                },
                decoration: _decoration('یک شناسه برای خودت انتخاب کن',
                    hint: 'مثلاً sara123'),
              ),
              const SizedBox(height: 14),
              TextFormField(
                controller: _passwordController,
                obscureText: true,
                validator: (v) => (v == null || v.trim().length < 4)
                    ? tr('رمز حداقل ۴ حرف باشد', context)
                    : null,
                decoration: _decoration('یک رمز ساده (حداقل ۴ حرف)'),
              ),


            ],
          ),
        ),
      ),
    );
  }
}
