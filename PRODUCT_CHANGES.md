# Product checkpoint

Compared with the initial product repository:

- Keep the original visual style and add a bundled Persian font.
- Replace research onboarding with a concise product introduction and explain account creation.
- Remove privacy-screen navigation and consent logging. Pause profile, pre/post, and post-chat questionnaires; retain their source.
- Route signup through the shared product router, directly to the chatbot for new users.
- Generalize the goal beyond English learning and academic research. Keep questions conversational and tied to the active step; prevent generated acknowledgments from inventing scene details or asking the wrong next question.
- Remove the importance rating. Add one optional 1–5 conversation-experience rating while the image generates, saved explicitly in the database.
- Support user-selected PDFs up to 30 MB in the existing reader. Files stay in browser memory; fixed quizzes and automatic exam completion do not apply to uploaded PDFs.
- Make extension installation optional. Retain existing reminder generation, visualization, reading-session completion, and storage infrastructure.
- Request natural neck-down or softly blurred faces in future images. Correct the awkward fallback suggestion and show Retry promptly when generation fails.
- Include the current local backend/session/visualization support required by this product version, which differed from the upstream research checkout before this work.
- Refresh the served Flutter build; omit local credentials, databases, caches, backup archives, and unrelated research documents.

Validation: 14 backend product-flow tests, 3 PDF validation tests, and a release web build. One live image generation succeeded with the locally configured `gpt-image-2`. Existing research-only tests have not all been migrated.
