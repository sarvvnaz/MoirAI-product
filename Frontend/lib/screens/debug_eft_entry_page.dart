import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import '../services/api_service.dart';
import '../theme/app_colors.dart';

/// DEBUG-ONLY (work step 10): manual EFT episode entry, replacing the chat
/// while we iterate on image generation. Fill the episode fields, save, then
/// generate the 3 reminder images and inspect them right here.
/// TODO(remove-before-pilot): superseded by the chat page (work step 12).
class DebugEftEntryPage extends StatefulWidget {
  const DebugEftEntryPage({super.key});

  @override
  State<DebugEftEntryPage> createState() => _DebugEftEntryPageState();
}

class _DebugEftEntryPageState extends State<DebugEftEntryPage> {
  // The 7 EFT questions (work-step-10 format), prefilled with the
  // "talking to my professor at UBC" sample so testing is one click.
  final _goal = TextEditingController(
      text: 'می‌خواهم بتوانم با استادم با اعتماد به نفس به انگلیسی صحبت کنم');
  final _where = TextEditingController(
      text: 'در دفتر استاد در دانشگاه UBC ونکوور، با پنجره‌ای رو به کوه‌ها');
  final _when = TextEditingController(text: 'یک سال دیگر، اوایل ترم پاییز، صبح');
  final _action = TextEditingController(
      text: 'دارم یافته‌های پروژه‌ام را به انگلیسی برای استادم توضیح می‌دهم');
  final _objects = TextEditingController(
      text: 'لپ‌تاپم باز است، روی میز کاغذ و ماژیک هست و تخته‌ی وایت‌برد پر از نمودار');
  final _who = TextEditingController(text: 'استاد راهنمایم و یکی از هم‌گروهی‌هایم');
  final _feeling = TextEditingController(
      text: 'اعتماد به نفس دارم و آرامم؛ حس غرور و تعلق می‌کنم');

  bool _saving = false;
  bool _generating = false;
  String _status = '';
  List<Map<String, dynamic>> _assets = [];

  @override
  void initState() {
    super.initState();
    _ensureAuth();
  }

  /// The debug page is reached directly (no login flow), so make sure a valid
  /// token exists: log in with a debug account, or sign one up if needed.
  Future<void> _ensureAuth() async {
    final existing = await ApiService.getToken();
    if (existing != null) return;
    setState(() => _status = 'در حال ورود با حساب دیباگ...');
    try {
      const id = 'debug-user';
      const pw = 'debug1234';
      var res = await ApiService.login({'participant_id': id, 'password': pw});
      if (res.statusCode != 200) {
        // No such account yet — create it, then it's logged in.
        await ApiService.signup({'participant_id': id, 'password': pw});
        res = await ApiService.login({'participant_id': id, 'password': pw});
      }
      if (res.statusCode == 200) {
        final body = jsonDecode(res.body) as Map<String, dynamic>;
        final token = body['access_token'] as String?;
        final uid = (body['user']?['id'] as num?)?.toInt();
        if (token != null && uid != null) {
          await ApiService.storeAuth(token, uid);
          setState(() => _status = 'وارد شدی (debug-user) ✅ حالا ذخیره/ساخت را بزن');
          return;
        }
      }
      setState(() => _status = 'ورود دیباگ ناموفق (${res.statusCode})');
    } catch (e) {
      setState(() => _status = 'خطا در ورود دیباگ: $e');
    }
  }

  @override
  void dispose() {
    for (final c in [_goal, _where, _when, _action, _objects, _who, _feeling]) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _saveEpisode() async {
    setState(() {
      _saving = true;
      _status = 'در حال ذخیره اپیزود...';
    });
    try {
      final res = await ApiService.submitEpisode({
        'goal': _goal.text.trim(),
        'where': _where.text.trim(),
        'when': _when.text.trim(),
        'action': _action.text.trim(),
        'objects': _objects.text.trim(),
        'who': _who.text.trim(),
        'feeling': _feeling.text.trim(),
      });
      setState(() => _status = 'اپیزود ذخیره شد (${res.statusCode}) ✅');
    } catch (e) {
      setState(() => _status = 'خطا در ذخیره: $e');
    } finally {
      setState(() => _saving = false);
    }
  }

  Future<void> _generate({bool regenerate = false}) async {
    setState(() {
      _generating = true;
      _assets = [];
      _status = 'در حال ساخت تصویر... (تا ~۱ دقیقه)';
    });
    try {
      final token = await ApiService.getToken();
      final res = await http
          .post(
            Uri.parse(ApiService.resolveBackendUrl('/api/extension/ensure-reminder')),
            headers: {
              'Content-Type': 'application/json',
              'Authorization': 'Bearer $token',
            },
            // Debug: 1 image. For the study set count to 3 (rotation).
            body: jsonEncode(
                {'generate_set': true, 'regenerate': regenerate, 'count': 1}),
          )
          .timeout(const Duration(minutes: 5));
      final body = jsonDecode(res.body) as Map<String, dynamic>;
      final assets = (body['assets'] as List? ?? [])
          .cast<Map<String, dynamic>>();
      setState(() {
        _assets = assets;
        _status = assets.isEmpty
            ? 'چیزی ساخته نشد — لاگ سرور را ببین'
            : '${assets.length} تصویر ساخته شد ✅';
      });
    } catch (e) {
      setState(() => _status = 'خطا در ساخت: $e');
    } finally {
      setState(() => _generating = false);
    }
  }

  Widget _field(String label, TextEditingController c) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: TextField(
        controller: c,
        minLines: 1,
        maxLines: 3,
        decoration: InputDecoration(
          labelText: label,
          filled: true,
          fillColor: Colors.white,
          border: OutlineInputBorder(
            borderRadius: BorderRadius.circular(10),
            borderSide: BorderSide.none,
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Directionality(
      textDirection: TextDirection.rtl,
      child: Scaffold(
        backgroundColor: AppColors.navy,
        appBar: AppBar(
          title: const Text('DEBUG: ورود دستی اپیزود + ساخت تصویر'),
          backgroundColor: AppColors.purple,
          foregroundColor: Colors.white,
        ),
        body: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 860),
            child: ListView(
              padding: const EdgeInsets.all(20),
              children: [
                Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: AppColors.lavender,
                    borderRadius: BorderRadius.circular(14),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      _field('۱. چه هدفی در یادگیری انگلیسی داری؟', _goal),
                      _field('۲. در آن لحظه‌ی موفقیت کجا هستی؟', _where),
                      _field('۳. کی این اتفاق می‌افتد؟', _when),
                      _field('۴. دقیقاً چه کاری انجام می‌دهی؟', _action),
                      _field('۵. دور و برت چه چیزهایی هست؟', _objects),
                      _field('۶. تنهایی یا چه کسانی با تو هستند؟', _who),
                      _field('۷. در آن لحظه چه حسی داری؟', _feeling),
                      const SizedBox(height: 8),
                      Row(
                        children: [
                          ElevatedButton(
                            onPressed: _saving ? null : _saveEpisode,
                            style: ElevatedButton.styleFrom(
                                backgroundColor: AppColors.navy),
                            child: const Text('۱) ذخیره اپیزود',
                                style: TextStyle(color: Colors.white)),
                          ),
                          const SizedBox(width: 10),
                          ElevatedButton(
                            onPressed: _generating ? null : () => _generate(regenerate: true),
                            style: ElevatedButton.styleFrom(
                                backgroundColor: AppColors.purple),
                            child: _generating
                                ? const SizedBox(
                                    width: 18,
                                    height: 18,
                                    child: CircularProgressIndicator(
                                        color: Colors.white, strokeWidth: 2))
                                : const Text('۲) ساخت تصویر',
                                    style: TextStyle(color: Colors.white)),
                          ),
                          const SizedBox(width: 14),
                          Expanded(
                            child: Text(_status,
                                style: const TextStyle(
                                    fontSize: 13, color: AppColors.navy)),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 16),
                ..._assets.map((a) {
                  final url = ApiService.resolveBackendUrl(
                      (a['image_url'] as String?) ?? '');
                  return Container(
                    margin: const EdgeInsets.only(bottom: 16),
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: Colors.white,
                      borderRadius: BorderRadius.circular(14),
                    ),
                    child: Column(
                      children: [
                        Image.network(url, height: 320, fit: BoxFit.contain),
                        const SizedBox(height: 8),
                        Text('${a['index']}: ${a['cue'] ?? ''}',
                            textAlign: TextAlign.center,
                            style: const TextStyle(
                                fontSize: 15, color: AppColors.navy)),
                      ],
                    ),
                  );
                }),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
