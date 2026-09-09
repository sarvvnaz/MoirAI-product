// main.dart — FULLY FIXED FOR WEB + DESKTOP
import 'dart:async';
import 'dart:convert';
// ignore_for_file: avoid_web_libraries_in_flutter, deprecated_member_use

// IMPORTANT: Only import dart:io on non-web platforms
import 'package:flutter/foundation.dart' show kDebugMode, kIsWeb;
import 'package:flutter/material.dart';
// Remove HomePage import; we no longer use the old home screen for EFT
import 'package:path/path.dart' as p;
import 'screens/consent_page.dart';
import 'screens/intro_page.dart';
import 'screens/login_page.dart';
import 'screens/signup_page.dart';
import 'screens/start_page.dart';
// Debug-only imports (see debug routes below).
import 'screens/baseline_profile_page.dart';
import 'screens/debug_eft_entry_page.dart';
import 'screens/eft_chat_page.dart';
import 'screens/final_feedback_page.dart';
import 'screens/prepare_page.dart';
import 'screens/study_session_page.dart';
import 'theme/app_colors.dart';

import 'dart:ui_web' as ui;
import 'dart:html' as html;
// Remove unused reflection page import

// Conditionally import dart:io
// ignore: avoid_web_libraries_in_flutter
import 'dart:io' show

  Platform,
  Process,
  Directory,
  File,
  ProcessStartMode,
  HttpClient;

/// BACKEND HANDLER — disabled entirely on Web
class LocalBackend {
  static const int _port = 8000;
  static Process? _proc;

  //static Uri get baseUrl => Uri.base;
  static Uri get baseUrl => Uri.parse('http://127.0.0.1:$_port');

  /// SAFE START: Only runs on Windows/macOS
  static Future<void> start() async {
    if (kIsWeb) return; // ← MUST-HAVE FIX
    if (!Platform.isMacOS && !Platform.isWindows) return;

    if (_proc != null) return;

    final env = Map<String, String>.from(Platform.environment)
      ..['MOIRAI_PORT'] = '$_port';

    final appDir = Directory.current.path;

    final packagedExe = Platform.isMacOS
        ? p.join(appDir, 'assets', 'bin', 'macos', 'backend')
        : p.join(appDir, 'assets', 'bin', 'windows', 'backend.exe');

    Future<Process> spawnBinary(String exe) async {
      final f = File(exe);
      if (!f.existsSync()) throw Exception('Backend binary not found at $exe');

      if (Platform.isMacOS) {
        await Process.run('chmod', ['+x', exe]);
      }
      return Process.start(exe, [],
          environment: env, mode: ProcessStartMode.detached);
    }

    Future<Process> spawnDev() async {
      final devEntry = p.join(appDir, '..', 'Backend', 'app', 'app.py');
      if (!File(devEntry).existsSync()) {
        throw Exception(
            'No packaged backend and no Python source found at $devEntry');
      }
      final py = Platform.isWindows ? 'python' : 'python3';
      return Process.start(py, [devEntry],
          environment: env, mode: ProcessStartMode.detached);
    }

    try {
      if (File(packagedExe).existsSync()) {
        _proc = await spawnBinary(packagedExe);
      } else {
        _proc = await spawnDev();
      }
    } catch (e) {
      _proc = null;
      rethrow;
    }

    final ok = await _waitForHealth(timeout: const Duration(seconds: 8));
    if (!ok) {
      _proc?.kill();
      _proc = null;
      throw Exception('Backend did not become ready at $baseUrl');
    }
  }

  static Future<bool> _waitForHealth(
      {Duration timeout = const Duration(seconds: 6)}) async {
    if (kIsWeb) return true; // Web never runs backend

    final deadline = DateTime.now().add(timeout);
    final client = HttpClient();

    while (DateTime.now().isBefore(deadline)) {
      try {
        final req = await client.getUrl(baseUrl.replace(path: '/health'));
        final res = await req.close();
        if (res.statusCode == 200) {
          final body = await utf8.decodeStream(res);
          if (body.contains('ok')) return true;
        }
      } catch (_) {}
      await Future.delayed(const Duration(milliseconds: 250));
    }
    return false;
  }

  static Future<void> stop() async {
    if (kIsWeb) return;
    _proc?.kill();
    _proc = null;
  }
}

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();


  runApp(const moiraiApp());
}

class moiraiApp extends StatelessWidget {
  const moiraiApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'MoirAI Demo',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        useMaterial3: true,
        scaffoldBackgroundColor: AppColors.lavender,
        colorScheme: ColorScheme.fromSeed(
          seedColor: AppColors.purple,
          primary: AppColors.purple,
          secondary: AppColors.mint,
          surface: Colors.white,
          onPrimary: Colors.white,
          onSurface: AppColors.navy,
        ),
        appBarTheme: const AppBarTheme(
          backgroundColor: AppColors.purple,
          foregroundColor: Colors.white,
          elevation: 0,
        ),
        elevatedButtonTheme: ElevatedButtonThemeData(
          style: ElevatedButton.styleFrom(
            backgroundColor: AppColors.purple,
            foregroundColor: Colors.white,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12),
            ),
          ),
        ),
        progressIndicatorTheme: const ProgressIndicatorThemeData(
          color: AppColors.purple,
        ),
        inputDecorationTheme: InputDecorationTheme(
          filled: true,
          fillColor: Colors.white,
          border: OutlineInputBorder(
            borderRadius: BorderRadius.circular(12),
          ),
        ),
      ),
      // No initialRoute: on web, Flutter reads the route from the URL
      // (e.g. /#/debug-study), falling back to '/'.
      routes: {
        '/': (_) => const StartPage(),
        '/intro': (_) => const IntroPage(),
        '/consent': (_) => const ConsentPage(),
        '/login': (_) => const LoginPage(),
        '/signup': (_) => const SignUpPage(),

        // ── Debug-only routes for previewing steps directly (dev use).
        // Compiled out of release builds — `flutter build web --release` is
        // what gets deployed, so these cannot be reached by a participant who
        // guesses a URL. /debug-study in particular jumps straight into a
        // session, bypassing the reminder-image gate on the prepare and
        // extension-setup screens.
        if (kDebugMode) ...{
          '/debug-questionnaire': (_) => const BaselineProfilePage(userId: 0),
          '/debug-chat': (_) => const EFTChatPage(userId: 0),
          '/debug-prepare': (_) => const PreparePage(userId: 0),
          '/debug-study': (_) => const StudySessionPage(userId: 0),
          '/debug-final': (_) => const FinalFeedbackPage(userId: 0),
          '/debug-eft-entry': (_) => const DebugEftEntryPage(),
        },

        // Baseline profile and EFT chat routes used in the new study flow
        //'/baseline_profile': (_) => BaselineProfilePage(userId: 0),
        //'/eft_chat': (_) => EFTChatPage(userId: 0),
        //'/break': (_) => BreakPage(
        //      userId: 0,
        //      breakDuration: const Duration(seconds: 10),
        //      sessionId: 0,
        //    ),
        //'/feedback': (_) => FeedbackPage(
        //      userId: 0,
        //      sessionNumber: 0,
        //    ),
        //'/task': (_) => TaskPage(
        //      userId: 0,
        //      sessionId: 0,
        //      sessionNumber: 0,
        //    ),
      },
    );
  }
}
