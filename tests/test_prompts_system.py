"""Тесты системного промпта (D-007, задача ``feat(prompts): system prompt``).

Проверяем, что промпт: описывает все ключи протокола ответа, подставляет лимиты
партии (подсказки/попытки), не оставляет неподставленных плейсхолдеров, и —
ключевая инвариантность — его пример ответа согласован с ``parse_response``
(тот же парсер, что разбирает реальные ответы моделей).
"""

import json

import pytest

from arena.arena import parse_response
from arena.models import MessageRecord
from arena.prompts import RESPONSE_KEYS, build_system_prompt, system_message


def test_response_keys_are_the_protocol_keys():
    assert RESPONSE_KEYS == ("reasoning", "move", "request_hint", "resign")


def test_prompt_mentions_every_protocol_key():
    prompt = build_system_prompt()
    for key in RESPONSE_KEYS:
        assert f'"{key}"' in prompt


def test_prompt_substitutes_default_limits():
    prompt = build_system_prompt()
    assert "3 engine hints" in prompt
    assert "3 illegal attempts" in prompt


def test_prompt_substitutes_custom_limits():
    prompt = build_system_prompt(hints_per_player=5, illegal_move_retries=2)
    assert "5 engine hints" in prompt
    assert "2 illegal attempts" in prompt


def test_prompt_has_no_unfilled_placeholders():
    # Литеральные фигурные скобки в шаблоне экранированы ({{ }}), а плейсхолдеры
    # подставлены — в готовом тексте не должно остаться `{hints}`/`{retries}`.
    prompt = build_system_prompt()
    assert "{hints}" not in prompt
    assert "{retries}" not in prompt


def test_prompt_mentions_both_notations_and_no_skip():
    prompt = build_system_prompt()
    assert "SAN" in prompt
    assert "UCI" in prompt
    # Запрет на пропуск хода (D-015) должен быть явно проговорён.
    assert "skipping a move is not allowed" in prompt


def test_example_is_valid_json_with_protocol_keys():
    # Вытаскиваем пример-объект из конца промпта и проверяем, что это валидный JSON
    # ровно с ключами протокола.
    prompt = build_system_prompt()
    start = prompt.rindex("{")
    obj = json.loads(prompt[start:])
    assert set(obj) == set(RESPONSE_KEYS)


def test_example_round_trips_through_parse_response():
    # Главная инвариантность: пример из промпта разбирается тем же парсером, что и
    # реальные ответы моделей, и даёт ожидаемый LLMResponse.
    prompt = build_system_prompt()
    parsed = parse_response(prompt)
    assert parsed.move == "Nf3"
    assert parsed.request_hint is False
    assert parsed.resign is False
    assert parsed.reasoning  # непустое рассуждение из примера


def test_system_message_wraps_prompt():
    msg = system_message(hints_per_player=4, illegal_move_retries=2)
    assert isinstance(msg, MessageRecord)
    assert msg.role == "system"
    assert msg.content == build_system_prompt(
        hints_per_player=4, illegal_move_retries=2
    )


def test_prompt_is_stable_for_same_limits():
    # Кэшируемость (D-017) держится на стабильности текста при одинаковых лимитах.
    assert build_system_prompt() == build_system_prompt()
    assert build_system_prompt(hints_per_player=1) != build_system_prompt()


def test_no_secrets_or_keys_leaked():
    # Промпт статичен и не должен содержать ничего секретного (D-003).
    prompt = build_system_prompt().lower()
    assert "api_key" not in prompt
    assert "sk-" not in prompt
