import 'package:flutter/material.dart';
// import '../screens/baseline_profile_page.dart';
import '../screens/pdf_upload_page.dart';
import '../screens/done_page.dart';
import '../screens/eft_chat_page.dart';
// import '../screens/extension_setup_page.dart';
// import '../data/study_steps.dart';
// import '../screens/measures_page.dart';
import '../screens/prepare_page.dart';
// import '../screens/study_session_page.dart';
import '../screens/visualization_page.dart';
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
      // The goal comes BEFORE the pre-questionnaire: the instrumentality
      // items ask about "this future goal", so without it they have no
      // referent on the page.
      /* Research questionnaire routes paused for the product.
      case 'future_goal':
        return MeasuresPage(
          userId: userId,
          timepoint: 'future_goal',
          title: 'هدف آینده‌ی تو',
          step: StudyStep.questionnaire,
          nextPage: () => FlowGate(userId: userId),
        );

      case 'pre':
        return MeasuresPage(
          userId: userId,
          timepoint: 'pre',
          title: 'چند سوال کوتاه قبل از شروع',
          step: StudyStep.questionnaire,
          nextPage: () => FlowGate(userId: userId),
        );

      */
      case 'eft_chat':
        return EFTChatPage(userId: userId);

      // Text and image generation. Unchanged from the existing pipeline —
      // this page starts the job and waits.
      case 'generate':
        return PreparePage(userId: userId);

      case 'visualize':
        return VisualizationPage(userId: userId);

      /* Research post-questionnaire paused.
      case 'post':
        return MeasuresPage(
          userId: userId,
          timepoint: 'post',
          title: 'چند سوال پایانی',
          step: StudyStep.finish,
          nextPage: () => const DonePage(),
        );

      */
      case 'reading':
        return PdfUploadPage(userId: userId);

      case 'done':
        return const DonePage();
      case 'profile':
      default:
        // New participant, or state fetch failed: start from the questionnaire.
        // return BaselineProfilePage(userId: userId);
        return EFTChatPage(userId: userId);
    }
  }
}

/// Re-asks the server where the participant should go next.
///
/// The v3 flow has several short questionnaire steps in a row, and each arm
/// takes a different route through them. Hard-coding "what comes after this
/// page" in each page would put the protocol in two places at once — the
/// stage machine and the client — which is exactly how the two drift apart.
/// Every step therefore hands control back here and the server decides.
class FlowGate extends StatelessWidget {
  const FlowGate({super.key, required this.userId});

  final int userId;

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<Widget>(
      future: FlowRouter.resolveNextScreen(userId),
      builder: (context, snap) {
        if (snap.connectionState != ConnectionState.done) {
          return const Scaffold(
            body: Center(child: CircularProgressIndicator()),
          );
        }
        return snap.data ?? const DonePage();
      },
    );
  }
}
