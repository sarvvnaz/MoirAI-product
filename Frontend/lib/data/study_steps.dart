/// The ordered steps of the study flow, defined once so the stepper,
/// router and pages all agree.
enum StudyStep {
  start, // login / first-time entry
  intro, // fun research intro
  consent, // short consent + anonymity
  account, // anonymous account creation (code + password)
  questionnaire, // profile, future goal, pre-questionnaire
  chat, // EFT chat
  prepare, // text + image generation, then the visualization screen
  study, // reading session + quiz — NOT used in this version
  finish, // post-questionnaire + done
}

/// The steps a participant actually walks through.
///
/// `study` is the reading session, which this version of the study does not
/// use. Its screens, routes and telemetry all still exist and are still
/// tested — they are simply not on the participant's path, so showing a
/// «مطالعه» box nobody will ever reach would misrepresent how long the study
/// is and imply a step that never arrives.
///
/// `studyGroup` is accepted and ignored: there is one path for everyone in
/// this version. The parameter stays so existing callers keep working.
List<StudyStep> visibleStepsFor(String? studyGroup) {
  // Research questionnaire step is paused, not deleted.
  return StudyStep.values
      .where((s) => s != StudyStep.questionnaire && s != StudyStep.start && s != StudyStep.consent)
      .toList();
}

const Map<StudyStep, String> studyStepLabels = {
  StudyStep.start: 'شروع',
  StudyStep.intro: 'آشنایی',
  StudyStep.consent: 'حریم خصوصی',
  StudyStep.account: 'حساب',
  StudyStep.questionnaire: 'پرسشنامه',
  StudyStep.chat: 'گفتگو',
  StudyStep.prepare: 'آماده‌سازی',
  StudyStep.study: 'مطالعه',
  StudyStep.finish: 'پایان',
};
