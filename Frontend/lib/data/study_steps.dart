/// The ordered steps of the study flow, defined once so the stepper,
/// router and pages all agree.
enum StudyStep {
  start, // login / first-time entry
  intro, // fun research intro
  consent, // short consent + anonymity
  account, // anonymous account creation (code + password)
  questionnaire, // baseline profile + baseline measures
  chat, // EFT chat
  prepare, // reminder generation + extension setup
  study, // reading session + quiz
  finish, // closing measures + final feedback + done
}

/// The steps a given arm actually walks through.
///
/// The control arm never does the EFT chat, so showing it a «گفتگو» box it
/// will never reach is both confusing and a small leak about the other
/// condition. Everything else is shared.
///
/// Defaults to the full list when the arm is unknown — an extra box is a
/// lesser evil than a progress bar that jumps as the arm loads.
List<StudyStep> visibleStepsFor(String? studyGroup) {
  if (studyGroup == 'control') {
    return StudyStep.values.where((s) => s != StudyStep.chat).toList();
  }
  return StudyStep.values;
}

const Map<StudyStep, String> studyStepLabels = {
  StudyStep.start: 'شروع',
  StudyStep.intro: 'آشنایی',
  StudyStep.consent: 'رضایت',
  StudyStep.account: 'حساب',
  StudyStep.questionnaire: 'پرسشنامه',
  StudyStep.chat: 'گفتگو',
  StudyStep.prepare: 'آماده‌سازی',
  StudyStep.study: 'مطالعه',
  StudyStep.finish: 'پایان',
};
