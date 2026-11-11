import json
from types import SimpleNamespace
from app.services import chat_translation as translation
from app.services.eft_chat_service_v2 import QUESTIONS, INTRO, FALLBACK_INSPIRE


def test_fixed_messages_are_translations_of_the_original_words(monkeypatch):
    monkeypatch.setattr(translation, '_translate_dynamic', lambda _: (_ for _ in ()).throw(AssertionError('No API needed')))
    for index, question in enumerate(QUESTIONS):
        original = {'bot': question['text'], 'question_index': index, 'collected': [False] * 7}
        english = translation.translate_display(original, 'en')
        assert english['bot'] == translation.QUESTIONS_EN[index]
        assert english['question_index'] == index
        assert english['collected'] == original['collected']
        assert original['bot'] == question['text']
    assert translation.translate_display({'bot': INTRO}, 'en')['bot'] == translation.INTRO_EN
    assert 'long-term goal' in translation.QUESTIONS_EN[0]
    assert 'research-methods course' not in translation.QUESTIONS_EN[0]
    assert 'personal project' in translation.QUESTIONS_EN[0]
    assert 'projector' in translation.QUESTIONS_EN[4]
    for key, suggestions in FALLBACK_INSPIRE.items():
        result = translation.translate_display({'suggestions': suggestions}, 'en')
        assert result['suggestions'] == translation.IDEAS_EN[key]


def test_dynamic_translation_is_one_request_and_does_not_change_flow(monkeypatch):
    calls = []
    def translate(payload):
        calls.append(json.loads(payload))
        return {'bot': 'The same follow-up in English.', 'episode_summary': 'The same summary in English.'}
    monkeypatch.setattr(translation, '_translate_dynamic', translate)
    original = {'bot': 'پرسش تکمیلی', 'episode_summary': 'خلاصه', 'question_index': 3,
                'collected': [True, True, True, False, False, False, False], 'can_start_session': False}
    result = translation.translate_display(original, 'en')
    assert len(calls) == 1
    assert result['question_index'] == original['question_index']
    assert result['collected'] == original['collected']
    assert result['can_start_session'] is False
    assert original['bot'] == 'پرسش تکمیلی'


def test_translation_failure_preserves_original_message_and_state(monkeypatch):
    monkeypatch.setattr(translation, '_translate_dynamic', lambda _: (_ for _ in ()).throw(TimeoutError()))
    original = {'bot': 'پاسخ اصلی', 'question_index': 2, 'needs_user': True}
    result = translation.translate_display(original, 'en')
    assert result == {**original, 'translation_unavailable': True}
    assert translation.translate_display(original, 'fa') is original


def test_only_confirmation_commands_are_normalized_after_the_last_step():
    assert translation.normalize_confirmation('confirm', SimpleNamespace(current_step=2), 'en') == 'confirm'
    assert translation.normalize_confirmation('confirm', SimpleNamespace(current_step=7), 'en') == 'تایید'
    assert translation.normalize_confirmation('place', SimpleNamespace(current_step=7), 'en') == 'where'
    assert translation.normalize_confirmation('confirm', SimpleNamespace(current_step=7), 'fa') == 'confirm'
