import 'dart:convert';
import 'package:flutter/material.dart';
import '../data/study_steps.dart';
import '../services/api_service.dart';
import '../services/flow_router.dart';
import '../theme/app_colors.dart';
import '../widgets/study_scaffold.dart';

/// Login for returning participants: participant code + password.
/// On success, resumes the study at whatever stage they left off.
class LoginPage extends StatefulWidget {
  const LoginPage({super.key});

  @override
  State<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends State<LoginPage> {
  final _formKey = GlobalKey<FormState>();
  final TextEditingController _codeController = TextEditingController();
  final TextEditingController _passwordController = TextEditingController();

  bool _loading = false;

  @override
  void dispose() {
    _codeController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  Future<void> _login() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => _loading = true);
    try {
      final response = await ApiService.login({
        'participant_id': _codeController.text.trim(),
        'password': _passwordController.text.trim(),
      });

      if (response.statusCode == 200) {
        final body = jsonDecode(response.body) as Map<String, dynamic>;
        final token = body['access_token'] as String?;
        final userId = (body['user']?['id'] as num?)?.toInt();
        if (token != null && userId != null) {
          await ApiService.storeAuth(token, userId);
          final next = await FlowRouter.resolveNextScreen(userId);
          if (!mounted) return;
          Navigator.pushReplacement(
            context,
            MaterialPageRoute(builder: (_) => next),
          );
          return;
        }
      }
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('کد یا رمز درست نیست')),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('مشکل در اتصال به سرور')),
      );
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return StudyScaffold(
      currentStep: StudyStep.start,
      bottomBar: Row(
        children: [
          TextButton(
            onPressed: () =>
                Navigator.pushReplacementNamed(context, '/'),
            child: const Text('بازگشت',
                style: TextStyle(color: AppColors.purple)),
          ),
          const Spacer(),
          SizedBox(
            width: 150,
            child: StudyPrimaryButton(
              label: 'ورود',
              busy: _loading,
              onPressed: _login,
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
              const Text(
                'خوش برگشتی 👋',
                style: TextStyle(
                    fontSize: 22,
                    fontWeight: FontWeight.bold,
                    color: AppColors.navy),
              ),
              const SizedBox(height: 10),
              const Text(
                'شناسه و رمزت را وارد کن تا از همان‌جایی که بودی ادامه بدهی.',
                style:
                    TextStyle(fontSize: 15, height: 1.8, color: AppColors.navy),
              ),
              const SizedBox(height: 24),
              TextFormField(
                controller: _codeController,
                textDirection: TextDirection.ltr,
                validator: (v) =>
                    (v == null || v.trim().isEmpty) ? 'شناسه را وارد کن' : null,
                decoration: InputDecoration(
                  labelText: 'شناسه‌ی تو',
                  filled: true,
                  fillColor: Colors.white,
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                    borderSide: BorderSide.none,
                  ),
                ),
              ),
              const SizedBox(height: 14),
              TextFormField(
                controller: _passwordController,
                obscureText: true,
                validator: (v) =>
                    (v == null || v.trim().isEmpty) ? 'رمز را وارد کن' : null,
                onFieldSubmitted: (_) => _login(),
                decoration: InputDecoration(
                  labelText: 'رمز',
                  filled: true,
                  fillColor: Colors.white,
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                    borderSide: BorderSide.none,
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
