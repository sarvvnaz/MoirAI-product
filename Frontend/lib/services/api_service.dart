import '../l10n/app_language.dart';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart' show kIsWeb; // 🔹 added
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
// ignore: deprecated_member_use
import 'dart:html' as html;
import 'dart:async';
import 'dart:js_interop';
import 'dart:js_interop_unsafe';

// ⬅️ keep using LocalBackend for non-web (local dev / native)
import '../main.dart' show LocalBackend;

@JS('chrome.runtime.sendMessage')
external void chromeRuntimeSendMessage(
  String extensionId,
  JSObject message,
  JSFunction callback,
);

@JS('chrome.runtime.lastError')
external JSObject? get chromeRuntimeLastError;

class ApiService {
  static const _timeout = Duration(seconds: 60);

  /// The participant's arm, cached from /api/participant/state.
  ///
  /// The progress bar has to decide synchronously whether to draw the
  /// «گفتگو» step, and an async lookup there would make the bar flicker or
  /// change shape mid-study. Null until the first state fetch, which the
  /// stepper treats as "show everything".
  static String? cachedStudyGroup;
  // Stable ID pinned by the "key" field in extensionTest/manifest.json —
  // identical on every machine regardless of install folder.
  static const String extensionId = 'kpkfnoihiigfebpojgabfkbippafdhah';

  //choose base URL depending on platform
  static Uri get _base {
    if (kIsWeb) {
      // On web: use same origin as the loaded page
      final uri = Uri.base;
      return Uri(
        scheme: uri.scheme,
        host: uri.host,
        port: uri.hasPort ? uri.port : null,
      );
    } else {
      // On desktop/mobile/local dev: use your LocalBackend (127.0.0.1:8765 etc.)
      return LocalBackend.baseUrl;
    }
  }

  // Build every request URL off _base. On web that is whatever origin served
  // the page, so the same build works on localhost and on the deployed
  // domain with no rebuild-per-environment.
  // resolve() rather than replace(path:) — reminder image URLs arrive with a
  // ?v= cache-buster attached, and replace() would escape the '?' into the
  // path and 404.
  static Uri _u(String path) => _base.resolve(path);

  // ───────────────────────────────
  // Auth (anonymous: participant code + password)
  // ───────────────────────────────
  /// Signup: server generates the participant code; returns it with a token.
  /// Body: {password, first_name?}
  static Future<http.Response> signup(Map<String, String?> data) {
    return http
        .post(
          _u('/api/auth/signup'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode(data),
        )
        .timeout(_timeout);
  }

  /// Login with {participant_code, password}.
  static Future<http.Response> login(Map<String, String> credentials) {
    return http
        .post(
          _u('/api/auth/login'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode(credentials),
        )
        .timeout(_timeout);
  }

  /// Stores the auth token + user id after a successful signup/login.
  static Future<void> storeAuth(String token, int userId) async {
    if (kIsWeb) {
      html.window.localStorage['access_token'] = token;
      html.window.localStorage['user_id'] = userId.toString();
    } else {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString('access_token', token);
      await prefs.setInt('user_id', userId);
    }
  }

  // ───────────────────────────────
  // EFT
  // ───────────────────────────────
  static Future<http.Response> submitProfile(
    Map<String, dynamic> profileData,
  ) async {
    final token = await getToken();
    if (token == null) {
      throw Exception('No access token');
    }

    return http
        .post(
          _u('/api/participant/profile'),
          headers: {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer $token',
          },
          body: jsonEncode(profileData),
        )
        .timeout(_timeout);
  }

  // ───────────────────────────────
  // EFT Episode submission
  // ───────────────────────────────
  /// Persists a structured EFT episode on the backend.
  static Future<http.Response> submitEpisode(
    Map<String, dynamic> episode,
  ) async {
    final token = await getToken();
    if (token == null) {
      throw Exception('No access token');
    }
    final body = {'episode': episode};
    return http
        .post(
          _u('/api/eft/episode'),
          headers: {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer $token',
          },
          body: jsonEncode(body),
        )
        .timeout(_timeout);
  }

  /// Which path the participant already submitted their episode with:
  /// 'chat', 'manual', or null if neither yet. The two are mutually
  /// exclusive — whichever is submitted first locks the other out.
  static Future<String?> eftLockStatus() async {
    final token = await getToken();
    if (token == null) return null;
    try {
      final res = await http
          .get(
            _u('/api/eft/lock-status'),
            headers: {'Authorization': 'Bearer $token'},
          )
          .timeout(_timeout);
      if (res.statusCode == 200) {
        final body = jsonDecode(res.body) as Map<String, dynamic>;
        return body['locked_by'] as String?;
      }
    } catch (e) {
      debugPrint('⚠️ eft lock-status failed: $e');
    }
    return null;
  }

  /// Manual fallback entry of the 7 EFT answers. Returns null on success,
  /// or a human-readable error message (Persian) on failure.
  static Future<String?> submitManualEpisode(
    Map<String, String> answers,
  ) async {
    final token = await getToken();
    if (token == null) return 'ابتدا باید وارد شوی.';
    try {
      final res = await http
          .post(
            _u('/api/eft/manual'),
            headers: {
              'Content-Type': 'application/json',
              'Authorization': 'Bearer $token',
            },
            body: jsonEncode({'answers': answers}),
          )
          .timeout(_timeout);
      if (res.statusCode == 200) return null;
      if (res.statusCode == 409) {
        return 'قبلاً از راه گفتگو ثبت کردی؛ دیگه نمی‌شه دستی ثبت کرد.';
      }
      return 'ثبت نشد (خطای ${res.statusCode}). دوباره تلاش کن.';
    } catch (e) {
      debugPrint('⚠️ manual episode submit failed: $e');
      return 'مشکلی در ارتباط با سرور پیش اومد. دوباره تلاش کن.';
    }
  }

  // ───────────────────────────────
  // EFT Chat
  // ───────────────────────────────
  static Future<Map<String, dynamic>?> eftChat(
    Map<String, dynamic> payload,
  ) async {
    final token = await getToken();
    if (token == null) {
      return null;
    }
    final res = await http
        .post(
          _u('/api/eft/chat'),
          headers: {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer $token',
          },
          body: jsonEncode({...payload, 'language': AppLanguage.instance.code}),
        )
        .timeout(_timeout);
    if (res.statusCode == 200) {
      try {
        return jsonDecode(res.body) as Map<String, dynamic>;
      } catch (_) {
        return null;
      }
    }
    return null;
  }

  /// Short example scenarios for the participant's CURRENT chat step, for when
  /// they can't picture anything. Returns suggestions only — they land in the
  /// input box as editable text and are never submitted as an answer on the
  /// participant's behalf.
  static Future<List<String>> eftInspire() async {
    final token = await getToken();
    if (token == null) return [];
    try {
      final res = await http
          .post(
            _u('/api/eft/inspire').replace(queryParameters: {'language': AppLanguage.instance.code}),
            headers: {'Authorization': 'Bearer $token'},
          )
          .timeout(_timeout);
      if (res.statusCode != 200) return [];
      final body = jsonDecode(res.body) as Map<String, dynamic>;
      return (body['suggestions'] as List?)?.whereType<String>().toList() ?? [];
    } catch (_) {
      // Inspire is optional help; failing to fetch it must never interrupt
      // the conversation.
      return [];
    }
  }

  /// Whether this participant's personalized reminder image exists yet.
  /// Returns false on any error, which keeps the study-session gate closed —
  /// the safe direction, since a session without an image collects nothing.
  /// Turn a server-relative asset path into something Image.network can
  /// load. Generated images come back as "/static/reminders/x.png", which is
  /// only meaningful against the API origin.
  static String absoluteUrl(String path) =>
      path.startsWith('http') ? path : _u(path).toString();

  /// The participant's own generated future — image and text.
  ///
  /// Not `getReminderSet()`: that endpoint withholds personalized assets from
  /// the control arm of the reminder study, so half of this study's
  /// participants would be shown the shared generic image instead of theirs.
  static Future<Map<String, dynamic>?> getGeneratedFuture() async {
    final token = await getToken();
    if (token == null) return null;
    try {
      final res = await http
          .get(
            _u('/api/eft/generated-future'),
            headers: {'Authorization': 'Bearer $token'},
          )
          .timeout(_timeout);
      if (res.statusCode == 200) {
        return jsonDecode(res.body) as Map<String, dynamic>;
      }
      debugPrint('⚠️ generated future: ${res.statusCode}');
    } catch (e) {
      debugPrint('⚠️ generated future failed: $e');
    }
    return null;
  }

  /// Record that the participant reached the end of the visualization screen.
  static Future<bool> markVisualizationSeen(int userId) async {
    final token = await getToken();
    if (token == null) return false;
    try {
      final res = await http
          .post(
            _u('/api/participant/visualization-seen'),
            headers: {'Authorization': 'Bearer $token'},
          )
          .timeout(const Duration(seconds: 12));
      return res.statusCode >= 200 && res.statusCode < 300;
    } catch (e) {
      // Never trap a participant on this screen because the network blinked.
      debugPrint('⚠️ markVisualizationSeen failed: $e');
      return false;
    }
  }

  static Future<bool> isReminderReady() async {
    final token = await getToken();
    if (token == null) return false;
    try {
      final res = await http
          .get(
            _u('/api/extension/reminder-status'),
            headers: {'Authorization': 'Bearer $token'},
          )
          .timeout(_timeout);
      if (res.statusCode != 200) return false;
      final body = jsonDecode(res.body) as Map<String, dynamic>;
      return (body['ready'] as bool?) ?? false;
    } catch (_) {
      return false;
    }
  }

  // ───────────────────────────────
  // Extension setup
  // ───────────────────────────────
  static Future<http.Response> ensureExtensionReminder() async {
    final token = await getToken();

    if (token == null) {
      throw Exception('No access token');
    }

    // The backend stores the participant's reminder image keyed to their id.
    // With placeholder=true a bundled image is used (no AI cost) — used only
    // for work-step-8 pipeline debugging.
    return http
        .post(
          _u('/api/extension/ensure-reminder'),
          headers: {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer $token',
          },
          body: jsonEncode(<String, dynamic>{'placeholder': true}),
        )
        .timeout(const Duration(seconds: 120));
  }

  /// Real reminder generation (work step 10 connected to the study flow):
  /// generates `count` AI images + cues from the participant's confirmed EFT
  /// episode. Returns the parsed response body, or null on failure — the
  /// study must never be blocked by generation trouble.
  static Future<Map<String, dynamic>?> generateReminderSet({
    int count = 3,
  }) async {
    final token = await getToken();
    if (token == null) return null;
    try {
      final res = await http
          .post(
            _u('/api/extension/ensure-reminder'),
            headers: {
              'Content-Type': 'application/json',
              'Authorization': 'Bearer $token',
            },
            body: jsonEncode({'generate_set': true, 'count': count}),
          )
          .timeout(const Duration(minutes: 5));
      if (res.statusCode == 200) {
        return jsonDecode(res.body) as Map<String, dynamic>;
      }
      debugPrint(
        '⚠️ generateReminderSet failed: ${res.statusCode} ${res.body}',
      );
    } catch (e) {
      debugPrint('⚠️ generateReminderSet error: $e');
    }
    return null;
  }

  /// Resolves a backend-relative path (e.g. /static/reminders/user_1.png)
  /// to a full URL.
  static String resolveBackendUrl(String path) {
    if (path.startsWith('http')) return path;
    return _u(path).toString();
  }

  /// Fetches all reminder assets (image URL + cue) for rotation.
  static Future<List<Map<String, dynamic>>> getReminderSet() async {
    final token = await getToken();
    if (token == null) return [];
    try {
      final res = await http
          .get(
            _u('/api/extension/reminder-set'),
            headers: {'Authorization': 'Bearer $token'},
          )
          .timeout(_timeout);
      if (res.statusCode == 200) {
        final body = jsonDecode(res.body) as Map<String, dynamic>;
        return (body['assets'] as List? ?? []).cast<Map<String, dynamic>>();
      }
    } catch (e) {
      debugPrint('⚠️ Failed to fetch reminder set: $e');
    }
    return [];
  }

  /// Fetches the participant's active reminder (image URL + cue).
  static Future<Map<String, dynamic>?> getActiveReminder() async {
    final token = await getToken();
    if (token == null) return null;
    try {
      final res = await http
          .get(
            _u('/api/extension/active-reminder'),
            headers: {'Authorization': 'Bearer $token'},
          )
          .timeout(_timeout);
      if (res.statusCode == 200) {
        return jsonDecode(res.body) as Map<String, dynamic>;
      }
    } catch (e) {
      debugPrint('⚠️ Failed to fetch active reminder: $e');
    }
    return null;
  }

  /// Tells the study system the session started/ended. The backend flag is the
  /// SOURCE OF TRUTH the extension polls (independent of extension-ID messaging);
  /// the direct message is a best-effort fast-path to refresh its cache.
  static Future<bool> notifyExtensionSessionState(bool active) async {
    // 1) Backend flag (reliable — the extension polls /api/extension/status).
    try {
      final token = await getToken();
      if (token != null) {
        await http
            .post(
              _u('/api/extension/session'),
              headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer $token',
              },
              body: jsonEncode({'active': active}),
            )
            .timeout(_timeout);
      }
    } catch (e) {
      debugPrint('⚠️ set session-active failed: $e');
    }
    // 2) Best-effort direct message (prompts an immediate cache refresh).
    return _sendExtensionMessage(active ? 'SESSION_STARTED' : 'SESSION_ENDED');
  }

  static Future<bool> connectExtension() {
    return _sendExtensionMessage('CONNECT_EFT_USER');
  }

  static Future<bool> _sendExtensionMessage(String action) async {
    if (!kIsWeb) {
      debugPrint('⚠️ Extension messaging only works on web.');
      return false;
    }

    final token = await getToken();

    if (token == null) {
      debugPrint('⚠️ No access token found for extension messaging.');
      return false;
    }

    final completer = Completer<bool>();

    try {
      final message = JSObject();

      message.setProperty('action'.toJS, action.toJS);
      message.setProperty('accessToken'.toJS, token.toJS);

      chromeRuntimeSendMessage(
        extensionId,
        message,
        ((JSAny? response) {
          final lastError = chromeRuntimeLastError;

          if (lastError != null) {
            final errorMessage =
                lastError.getProperty<JSString?>('message'.toJS)?.toDart ??
                'Unknown extension error';

            debugPrint('⚠️ Extension connection error: $errorMessage');

            if (!completer.isCompleted) {
              completer.complete(false);
            }
            return;
          }

          bool success = false;

          if (response != null) {
            final responseObject = response as JSObject;
            success =
                responseObject
                    .getProperty<JSBoolean?>('success'.toJS)
                    ?.toDart ==
                true;
          }

          debugPrint('🔌 Extension connected? $success');

          if (!completer.isCompleted) {
            completer.complete(success);
          }
        }).toJS,
      );

      return await completer.future.timeout(
        const Duration(seconds: 3),
        onTimeout: () {
          debugPrint('⚠️ Extension connection timed out.');
          return false;
        },
      );
    } catch (e) {
      debugPrint('⚠️ Failed to connect extension: $e');
      return false;
    }
  }

  // ───────────────────────────────
  // Participant flow state (resume after login)
  // ───────────────────────────────
  // ───────────────────────────────
  // Study session feedback
  // ───────────────────────────────
  /// Sends post-session feedback to the backend.
  static Future<http.Response> submitStudyFeedback(
    Map<String, dynamic> feedbackData,
  ) async {
    final token = await getToken();
    if (token == null) {
      throw Exception('No access token');
    }
    return http
        .post(
          _u('/api/study/feedback'),
          headers: {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer $token',
          },
          body: jsonEncode(feedbackData),
        )
        .timeout(_timeout);
  }

  // ───────────────────────────────
  // Token helper
  // ───────────────────────────────
  static Future<String?> getToken() async {
    if (kIsWeb) {
      // Flutter Web → use browser localStorage
      return html.window.localStorage['access_token'];
    }
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString('access_token');
  }

  /// Logs the consent recorded on the consent page (before auth existed).
  /// Called once right after the first successful login.
  static Future<void> logStoredConsent(int userId) async {
    String? ts;
    if (kIsWeb) {
      ts = html.window.localStorage['moirai:consent_at'];
      if (ts != null) html.window.localStorage.remove('moirai:consent_at');
    } else {
      final prefs = await SharedPreferences.getInstance();
      ts = prefs.getString('moirai:consent_at');
      if (ts != null) await prefs.remove('moirai:consent_at');
    }
    if (ts != null) {
      await logEvent(userId, 'consent_given', {'consented_at': ts});
    }
  }

  // ───────────────────────────────
  // Research events (step 11: one row per trigger)
  // ───────────────────────────────
  static Future<void> _researchPost(
    String path,
    Map<String, dynamic> body,
  ) async {
    final token = await getToken();
    if (token == null) return;
    try {
      final res = await http
          .post(
            _u(path),
            headers: {
              'Content-Type': 'application/json',
              'Authorization': 'Bearer $token',
            },
            body: jsonEncode(body),
          )
          .timeout(_timeout);
      debugPrint('🧪 $path → ${res.statusCode} ${res.body}');
    } catch (e) {
      debugPrint('⚠️ research post $path failed: $e');
    }
  }

  /// FROZEN — the reactive protocol. The server accepts these and writes
  /// nothing; they are kept only so a half-updated client cannot crash a
  /// session mid-run. Cues are scheduled now, so nothing should call them.
  @Deprecated('Reactive protocol. Use the scheduled-cue methods below.')
  static Future<void> researchTrigger(
    String eventType, {
    bool reminderShown = false,
  }) {
    return _researchPost('/api/research/event', {
      'event_type': eventType,
      'reminder_shown': reminderShown,
    });
  }

  @Deprecated('Reactive protocol. Use disengagementEnd().')
  static Future<void> researchReturn({
    bool dismissed = false,
    bool clickedReturn = false,
  }) {
    return _researchPost('/api/research/event/return', {
      'dismissed': dismissed,
      'clicked_return': clickedReturn,
    });
  }

  @Deprecated('Reactive protocol. Use endReading().')
  static Future<void> researchSessionClosed() {
    return _researchPost('/api/research/session-closed', {});
  }

  // ───────────────────────────────
  // Scheduled cues — THE SERVER OWNS THE CLOCK
  // ───────────────────────────────
  // The app never decides when a cue is due. Its own timers are throttled the
  // moment its tab is hidden, which is exactly the state that matters most,
  // so it asks and renders; the server decides and grants.

  static Future<Map<String, dynamic>?> _studyPost(
    String path,
    Map<String, dynamic> body,
  ) async {
    final token = await getToken();
    if (token == null) return null;
    try {
      final res = await http
          .post(
            _u(path),
            headers: {
              'Content-Type': 'application/json',
              'Authorization': 'Bearer $token',
            },
            body: jsonEncode(body),
          )
          .timeout(_timeout);
      if (res.statusCode >= 200 && res.statusCode < 300) {
        return jsonDecode(res.body) as Map<String, dynamic>;
      }
      debugPrint('⚠️ $path → ${res.statusCode} ${res.body}');
    } catch (e) {
      debugPrint('⚠️ study post $path failed: $e');
    }
    return null;
  }

  /// Opens the reading window and schedules both cues. Idempotent server-side,
  /// so a reload cannot restart the clock or hand out extra cues.
  static Future<Map<String, dynamic>?> startReading() =>
      _studyPost('/api/study/session/start-reading', {});

  /// Closes the window: any open disengagement episode is ended and any slot
  /// that never delivered is written off with a reason.
  static Future<Map<String, dynamic>?> endReading() =>
      _studyPost('/api/study/session/end-reading', {});

  /// Is a cue slot open right now? Returns `due_slot: null` almost always.
  static Future<Map<String, dynamic>?> cueDue() async {
    final token = await getToken();
    if (token == null) return null;
    try {
      final res = await http
          .get(
            _u('/api/study/cue/due'),
            headers: {'Authorization': 'Bearer $token'},
          )
          .timeout(_timeout);
      if (res.statusCode == 200) {
        return jsonDecode(res.body) as Map<String, dynamic>;
      }
    } catch (e) {
      debugPrint('⚠️ cue/due failed: $e');
    }
    return null;
  }

  /// Claims the open slot. [state] is the one thing only this client can
  /// observe; the condition is decided server-side from the participant's arm
  /// and is never reported from here.
  static Future<Map<String, dynamic>?> claimCue(String state) =>
      _studyPost('/api/study/cue/claim', {'state': state, 'claimed_by': 'app'});

  /// The cue is on screen. Stamps delivery time and how late it was.
  static Future<Map<String, dynamic>?> cueShown(int deliveryId) =>
      _studyPost('/api/study/cue/$deliveryId/shown', {});

  static Future<Map<String, dynamic>?> cueInteraction(
    int deliveryId, {
    bool dismissed = false,
    bool clickedReturn = false,
  }) => _studyPost('/api/study/cue/$deliveryId/interaction', {
    'dismissed': dismissed,
    'clicked_return': clickedReturn,
  });

  /// Opens a disengagement episode. Recorded whether or not a cue is nearby —
  /// disengagement is the OUTCOME now, not the trigger.
  static Future<Map<String, dynamic>?> disengagementStart(String type) =>
      _studyPost('/api/study/disengagement/start', {'type': type});

  /// Closes the open episode, and resolves return latency if the cue that is
  /// still open was delivered while the participant was away.
  static Future<Map<String, dynamic>?> disengagementEnd({
    String endedBy = 'return',
  }) => _studyPost('/api/study/disengagement/end', {'ended_by': endedBy});

  // ───────────────────────────────
  // Events
  // ───────────────────────────────
  static Future<void> saveExperienceRating(int rating) async {
    final token = await getToken();
    if (token == null) throw StateError('Not signed in');
    final response = await http
        .post(
          _u('/api/events/log'),
          headers: {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer $token',
          },
          body: jsonEncode({
            'event_type': 'product_feedback',
            'details': {
              'chat_experience': rating,
              'scale_min': 1,
              'scale_max': 5,
            },
          }),
        )
        .timeout(_timeout);
    if (response.statusCode != 200 && response.statusCode != 201) {
      throw StateError('Feedback was not saved');
    }
    final body = jsonDecode(response.body) as Map<String, dynamic>;
    if (body.containsKey('error')) throw StateError('Feedback was not saved');
  }

  static Future<void> logEvent(
    int userId,
    String eventType,
    Map<String, dynamic> details,
  ) async {
    final token = await getToken();
    if (token == null) {
      debugPrint('⚠️ No token found — user not logged in?');
      return;
    }

    final res = await http
        .post(
          _u('/api/events/log'),
          headers: {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer $token',
          },
          body: jsonEncode({'event_type': eventType, 'details': details}),
        )
        .timeout(_timeout);

    if (res.statusCode == 200 || res.statusCode == 201) {
      debugPrint('✅ Logged event: $eventType');
    } else {
      debugPrint('⚠️ Failed to log event ($eventType): ${res.statusCode}');
    }
  }

  // Nudge support removed. The app no longer fetches or displays nudges.

  // ──────────────────────────────
  // Start Session
  // ──────────────────────────────
  static Future<Map<String, dynamic>?> startSession() async {
    final token = await getToken();
    if (token == null) {
      debugPrint('⚠️ No token found — user not logged in');
      return null;
    }

    final res = await http
        .post(
          _u('/api/events/session/start'),
          headers: {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer $token',
          },
        )
        .timeout(_timeout);

    debugPrint("📌 startSession response: ${res.statusCode} - ${res.body}");

    if (res.statusCode == 200 || res.statusCode == 201) {
      return jsonDecode(res.body) as Map<String, dynamic>;
    } else {
      return null;
    }
  }

  // ──────────────────────────────
  // End Session
  // ──────────────────────────────
  static Future<void> endSession() async {
    final token = await getToken();
    if (token == null) return;

    final res = await http.post(
      _u('/api/events/end_session'),
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer $token',
      },
    );

    if (res.statusCode == 200) {
      debugPrint('🟢 Session ended successfully');
    } else {
      debugPrint('⚠️ Failed to end session: ${res.statusCode}');
    }
  }

  // ── Measurement battery ───────────────────────────────────────────
  /// Items due at a timepoint for THIS participant's arm. Empty list means
  /// nothing is due (e.g. the control arm at post_chat) — not an error.
  /// The FULL items payload: the item list plus the page-level context the
  /// server decides — whether to show the participant's goal, the goal text
  /// itself, and which codes may be left blank.
  ///
  /// `getMeasureItems` below still returns just the list, so existing callers
  /// are unaffected.
  static Future<Map<String, dynamic>?> getMeasurePayload(
    String timepoint,
  ) async {
    final token = await getToken();
    if (token == null) return null;
    try {
      final res = await http
          .get(
            _u('/api/measures/items?timepoint=$timepoint'),
            headers: {'Authorization': 'Bearer $token'},
          )
          .timeout(_timeout);
      if (res.statusCode == 200) {
        final body = jsonDecode(res.body) as Map<String, dynamic>;
        return {
          ...body,
          'items': (body['items'] as List).cast<Map<String, dynamic>>(),
        };
      }
      debugPrint('⚠️ measure payload: ${res.statusCode}');
    } catch (e) {
      debugPrint('⚠️ measure payload failed: $e');
    }
    return null;
  }

  static Future<List<Map<String, dynamic>>?> getMeasureItems(
    String timepoint,
  ) async {
    final token = await getToken();
    if (token == null) return null;
    try {
      final res = await http
          .get(
            _u('/api/measures/items?timepoint=$timepoint'),
            headers: {'Authorization': 'Bearer $token'},
          )
          .timeout(_timeout);
      if (res.statusCode == 200) {
        final body = jsonDecode(res.body) as Map<String, dynamic>;
        return (body['items'] as List).cast<Map<String, dynamic>>();
      }
      debugPrint('⚠️ measure items: ${res.statusCode}');
    } catch (e) {
      debugPrint('⚠️ measure items failed: $e');
    }
    return null;
  }

  /// Saves answers for one timepoint. Returns false on failure so the caller
  /// can let the participant continue rather than stranding them.
  /// `answers` is keyed by item code. Values are int for rated items and
  /// String for open-ended ones — the server stores each in its own column,
  /// so an open answer must not be coerced into a number on the way out.
  static Future<bool> saveMeasureResponses(
    String timepoint,
    Map<String, dynamic> answers,
  ) async {
    final token = await getToken();
    if (token == null) return false;
    try {
      final res = await http
          .post(
            _u('/api/measures/responses'),
            headers: {
              'Content-Type': 'application/json',
              'Authorization': 'Bearer $token',
            },
            body: jsonEncode({'timepoint': timepoint, 'responses': answers}),
          )
          .timeout(_timeout);
      if (res.statusCode == 200) return true;
      debugPrint('⚠️ measure save: ${res.statusCode} ${res.body}');
    } catch (e) {
      debugPrint('⚠️ measure save failed: $e');
    }
    return false;
  }

  static Future<Map<String, dynamic>?> getParticipantState() async {
    final token = await getToken();
    if (token == null) return null;
    try {
      final res = await http
          .get(
            _u('/api/participant/state'),
            headers: {'Authorization': 'Bearer $token'},
          )
          .timeout(_timeout);
      if (res.statusCode == 200) {
        final body = jsonDecode(res.body) as Map<String, dynamic>;
        cachedStudyGroup = body['study_group'] as String?;
        return body;
      }
    } catch (e) {
      debugPrint('⚠️ Failed to fetch participant state: $e');
    }
    return null;
  }
}
