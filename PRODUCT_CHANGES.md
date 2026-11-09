# Product branch: first checkpoint

Generalize goal wording beyond English learning while retaining the existing UI and chatbot flow.

- Remove the English-learning goal dropdown, its required validation, and its submission field from baseline profile.
- Ask for a general long-term goal in manual and debug goal-entry forms.
- Generalize introductory copy to a task that matters to the user.

The chatbot, study session, original colors, navigation, and database schema are unchanged. Existing English proficiency and study-frequency questions are outside this checkpoint.

Validation: the equivalent local changes passed a Flutter release web build. The changes were applied to the current GitHub main while preserving its newer code and documentation; this branch has not had a full integration test.

Upcoming checkpoints: English interface translation, user-selected PDFs, fewer research questionnaires with brief feedback, and subtle UI cleanup.
