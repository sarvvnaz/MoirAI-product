import 'package:flutter/material.dart';
import '../screens/baseline_profile_page.dart';
import '../screens/done_page.dart';
import '../screens/eft_chat_page.dart';
import '../screens/final_feedback_page.dart';
import '../screens/extension_setup_page.dart';
import '../data/study_steps.dart';
import '../screens/measures_page.dart';
import '../screens/prepare_page.dart';
import '../screens/study_session_page.dart';
import 'api_service.dart';

/// Maps the backend participant state (GET /api/participant/state) to the
/// screen the participant should resume at after logging in.
///
/// The backend decides the stage, including the two arms: a control
/// participant is never given an 'eft_chat' stage, because they do not do
/// the chat. Keeping that decision server-side means the route cannot
/// disagree with the arm recorded in the data.
class FlowRouter {
  static Future<Widget> resolveNextScreen(int userId) async {
    final state = await ApiService.getParticipantState();
    final stage = state?['stage'] as String?;

    switch (stage) {
      case 'eft_chat':
        return EFTChatPage(userId: userId);
      case 'session1':
      case 'session2':
        // BOTH arms need the extension: it is what shows any reminder at all
        // and what records tab-switching, so a participant without it
        // produces a session that looks normal and measured nothing. The
        // control arm reaches it here, since it never passes through the
        // prepare page where the eft arm installs it.
        if (!await ApiService.connectExtension()) {
          return ExtensionSetupPage(userId: userId);
        }
        // Resuming otherwise jumps straight into a session, bypassing the
        // gate. `isReminderReady` is arm-aware server-side: the eft arm waits
        // for its own generated image, the control arm for the shared generic
        // set — so this one check is correct for both.
        if (!await ApiService.isReminderReady()) {
          return ExtensionSetupPage(userId: userId);
        }
        return StudySessionPage(userId: userId);
      case 'feedback':
        // Closing measures first, then the feedback page. fsc and intention
        // are repeated from baseline here — the analysis is the CHANGE, so a
        // participant who stops before this point contributes no change score
        // and this must not be buried behind anything optional.
        return MeasuresPage(
          userId: userId,
          timepoint: 'closing',
          title: 'آخرین چند سوال',
          step: StudyStep.finish,
          nextPage: () => FinalFeedbackPage(userId: userId),
        );
      case 'done':
        return const DonePage();
      case 'profile':
      default:
        // New participant, or state fetch failed: start from the questionnaire.
        return BaselineProfilePage(userId: userId);
    }
  }
}
