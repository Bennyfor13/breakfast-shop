import pytest
from backend.bot.nlu import parse_intent, Intent
from backend.bot.llm_nlu import classify_intent, parse_intent_llm, INTENT_MAP


@pytest.mark.asyncio
async def test_classify_intent_returns_none_without_key():
    """Without API key, classify_intent returns None immediately."""
    result = await classify_intent("排班", api_key="")
    assert result is None


@pytest.mark.asyncio
async def test_parse_intent_llm_falls_back_to_regex():
    """Without API key, parse_intent_llm falls back to regex NLU."""
    result = await parse_intent_llm("排班", api_key="")
    assert result.intent == Intent.SHOW_SCHEDULE


@pytest.mark.asyncio
async def test_parse_intent_llm_regex_edit_single_shift():
    """Regex fallback can match EDIT_SINGLE_SHIFT."""
    result = await parse_intent_llm("把张三换成李四", api_key="")
    assert result.intent == Intent.EDIT_SINGLE_SHIFT


@pytest.mark.asyncio
async def test_parse_intent_llm_regex_find_replacement():
    """Regex fallback can match FIND_REPLACEMENT."""
    result = await parse_intent_llm("找谁替张三", api_key="")
    assert result.intent == Intent.FIND_REPLACEMENT


def test_regex_edit_single_shift():
    result = parse_intent("把张三周三早班换成李四")
    assert result.intent == Intent.EDIT_SINGLE_SHIFT


def test_regex_find_replacement():
    result = parse_intent("李四请假找谁替")
    assert result.intent in (Intent.FIND_REPLACEMENT, Intent.MARK_ABSENT)  # could match either


def test_intent_map_covers_all():
    """All regex Intents (except UNKNOWN) are mapped in INTENT_MAP."""
    for intent in Intent:
        if intent == Intent.UNKNOWN:
            continue
        name = intent.name
        assert name in INTENT_MAP, f"Missing {name} in INTENT_MAP"
        assert INTENT_MAP[name] == intent


def test_parse_intent_returns_unknown_for_gibberish():
    result = parse_intent("asdfghjkl")
    assert result.intent == Intent.UNKNOWN
