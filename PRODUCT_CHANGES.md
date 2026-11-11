# Current product checkpoint

Moirai retains its original visual style and chatbot conversation mechanics, with a simplified bilingual product flow and user-selected PDFs.

## Latest chatbot update

- Restore the original chatbot tone, follow-up decisions, step handling, and confirmation behavior. Keep the product route directly from chat to image preparation.
- Broaden only the goal framing: studying can support any long-term goal, including work, skills, education, and personal projects. Match the English translation.
- Translate chatbot display text at the API boundary. Fixed questions, introduction, importance wording, and inspiration examples retain the same content and examples in English.
- Translate generated follow-ups and summaries together in one cached request, with an eight-second timeout and no retries. If translation fails, preserve the original text and show an explicit notice.
- Keep stored original messages, answers, step flags, and episode data unchanged by translation. Normalize translated confirm/edit commands only at the confirmation stage.
- Remove the superseded language-specific conversation implementation and its tests.

## Retained product features

- Persistent Persian/English interface switch and automatic text direction.
- Concise onboarding, no privacy screen, and paused research questionnaires.
- Local PDF selection up to 30 MB; no fixed quiz or exam timer for uploaded files.
- Optional 1–5 waiting feedback saved in the database and optional browser extension.
- Reminder image generation, with prompts requesting natural neck-down framing or softly blurred faces.
- Bundled Persian font and refreshed served Flutter build.

Validation: 17 backend product/translation tests pass. The served release web build includes the restored chat screen and translation notices. English translation tests cover paired wording, state preservation, bounded failure fallback, and command boundaries. The pre-existing research-only tests have not all been adapted to the product flow.

Local credentials, runtime databases, personal images, backup archives, caches, and unrelated research documents are excluded from the commit.
