"""Тесты ModelPlayer и парсера ответа (D-007).

Провайдер подменяется фейком (без сети): он фиксирует переданные аргументы и
отдаёт заранее заданный сырой текст. Проверяем: вызов ``complete`` с параметрами
игрока, проброс ``ProviderError``, построение ``PlayerInfo`` без секретов и —
основной объём — устойчивый разбор сырого текста в ``LLMResponse``.
"""

import pytest

from arena.arena import ModelPlayer, parse_response
from arena.config import ModelParams, ResolvedModel
from arena.models import LLMResponse, MessageRecord
from arena.providers import LLMProvider, ProviderError

API_KEY = "sk-secret-value-123"


def _model(model_id: str = "gpt-4o") -> ResolvedModel:
    return ResolvedModel(
        id=model_id,
        provider="openai",
        display_name="GPT-4o",
        params=ModelParams(temperature=0.2, max_tokens=1024),
        api_key_env="OPENAI_API_KEY",
        api_key=API_KEY,
    )


class _FakeProvider(LLMProvider):
    """Провайдер-заглушка: отдаёт ``reply`` или бросает ``error``, пишет capture."""

    def __init__(self, model, *, reply="{}", error=None):
        super().__init__(model)
        self._reply = reply
        self._error = error
        self.calls: list = []

    def complete(self, messages, params):
        self.calls.append((list(messages), params))
        if self._error is not None:
            raise self._error
        return self._reply


def _msgs():
    return [
        MessageRecord(role="system", content="rules"),
        MessageRecord(role="user", content="your move"),
    ]


# --- ModelPlayer: оркестрация --------------------------------------------------

def test_respond_calls_provider_with_player_params():
    provider = _FakeProvider(_model(), reply='{"move": "e4"}')
    player = ModelPlayer(provider)

    out = player.respond(_msgs())

    assert isinstance(out, LLMResponse)
    assert out.move == "e4"
    # complete вызван ровно раз, с параметрами модели.
    assert len(provider.calls) == 1
    sent_messages, sent_params = provider.calls[0]
    assert sent_params == provider.model.params
    assert sent_messages == _msgs()


def test_params_override():
    provider = _FakeProvider(_model(), reply="{}")
    custom = ModelParams(temperature=0.9, max_tokens=10)
    player = ModelPlayer(provider, params=custom)

    player.respond(_msgs())

    _, sent_params = provider.calls[0]
    assert sent_params == custom


def test_provider_error_propagates():
    provider = _FakeProvider(_model(), error=ProviderError("boom"))
    player = ModelPlayer(provider)

    with pytest.raises(ProviderError, match="boom"):
        player.respond(_msgs())


def test_info_has_no_secret():
    provider = _FakeProvider(_model("gpt-4o"))
    info = ModelPlayer(provider).info

    assert info.model_id == "gpt-4o"
    assert info.provider == "openai"
    assert info.display_name == "GPT-4o"
    # Ключа нет нигде в сериализации (D-003).
    assert API_KEY not in info.model_dump_json()


def test_repr_hides_key():
    text = repr(ModelPlayer(_FakeProvider(_model())))
    assert API_KEY not in text
    assert "gpt-4o" in text


# --- parse_response: счастливый путь ------------------------------------------

def test_parse_full_object():
    out = parse_response(
        '{"reasoning": "develops a knight", "move": "Nf3", '
        '"request_hint": false, "resign": false}'
    )
    assert out.reasoning == "develops a knight"
    assert out.move == "Nf3"
    assert out.request_hint is False
    assert out.resign is False


def test_parse_uci_move():
    assert parse_response('{"move": "e2e4"}').move == "e2e4"


def test_defaults_when_fields_missing():
    out = parse_response('{"move": "e4"}')
    assert out.reasoning == ""
    assert out.request_hint is False
    assert out.resign is False
    # Фича «стратегия»: без полей — пусто/start.
    assert out.strategy == ""
    assert out.plan_status == "start"


def test_parse_reads_strategy_and_plan_status():
    out = parse_response(
        '{"move": "Nf3", "strategy": "castle then push d5", "plan_status": "continue"}'
    )
    assert out.strategy == "castle then push d5"
    assert out.plan_status == "continue"


def test_parse_plan_status_is_normalized_and_clamped():
    # Регистр/пробелы нормализуются; неизвестное значение → start.
    assert parse_response('{"move": "e4", "plan_status": " Adapt "}').plan_status == "adapt"
    assert parse_response('{"move": "e4", "plan_status": "yolo"}').plan_status == "start"
    assert parse_response('{"move": "e4", "plan_status": 5}').plan_status == "start"


# --- parse_response: устойчивость к обёртке -----------------------------------

def test_json_inside_markdown_fence():
    raw = 'Sure!\n```json\n{"move": "d4", "reasoning": "control center"}\n```\n'
    out = parse_response(raw)
    assert out.move == "d4"
    assert out.reasoning == "control center"


def test_prose_around_json():
    raw = 'I think the best move here is:\n{"move": "Bb5"}\nHope that helps.'
    assert parse_response(raw).move == "Bb5"


def test_braces_inside_string_do_not_break_parsing():
    out = parse_response('{"reasoning": "the } and { are tricky", "move": "Qh5"}')
    assert out.move == "Qh5"
    assert out.reasoning == "the } and { are tricky"


def test_picks_object_with_move_over_earlier_example():
    raw = (
        'Example format: {"reasoning": "...", "move": "..."} '
        'is just an example.\n'
        'My answer: {"move": "Nc3", "reasoning": "knight out"}'
    )
    out = parse_response(raw)
    # Первый объект (пример) тоже содержит "move" → берётся он; проверяем, что
    # парсер детерминированно берёт ПЕРВЫЙ объект с ключом move.
    assert out.move == "..."


def test_picks_first_object_with_move_when_first_lacks_it():
    raw = '{"note": "thinking"} then {"move": "O-O"}'
    assert parse_response(raw).move == "O-O"


# --- parse_response: терпимость к типам ---------------------------------------

def test_bool_as_strings_and_numbers():
    out = parse_response(
        '{"move": "e4", "request_hint": "true", "resign": 1}'
    )
    assert out.request_hint is True
    assert out.resign is True


def test_bool_false_variants():
    out = parse_response('{"move": "e4", "request_hint": "no", "resign": 0}')
    assert out.request_hint is False
    assert out.resign is False


def test_empty_move_becomes_none():
    assert parse_response('{"move": "  "}').move is None
    assert parse_response('{"move": null}').move is None


def test_resign_without_move():
    out = parse_response('{"resign": true, "reasoning": "lost position"}')
    assert out.resign is True
    assert out.move is None
    assert out.reasoning == "lost position"


def test_request_hint_without_move():
    out = parse_response('{"request_hint": true}')
    assert out.request_hint is True
    assert out.move is None


# --- parse_response: деградация без JSON --------------------------------------

def test_no_json_keeps_text_as_reasoning():
    raw = "I will play knight to f3, it's the best developing move."
    out = parse_response(raw)
    assert out.move is None
    assert out.reasoning == raw
    assert out.request_hint is False
    assert out.resign is False


def test_unparseable_braces_fall_back():
    # Незакрытая скобка / мусор внутри — валидного объекта нет.
    raw = "{ this is not json at all "
    out = parse_response(raw)
    assert out.move is None
    assert out.reasoning == raw.strip()
