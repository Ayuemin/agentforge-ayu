"""Regression: Dzen must not mutate a comparison assignment into a checklist."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from contentforge.core.config import ContentForgeConfig, LLMConfig, PipelineConfig
from contentforge.core.mimo_client import ChatResponse, TokenUsage
from contentforge.dzen_editorial import stage_guidance
from contentforge.pipeline.orchestrator import PipelineOrchestrator


def _answer(content: str) -> ChatResponse:
    return ChatResponse(content=content, usage=TokenUsage(
        prompt_tokens=30, completion_tokens=45, total_tokens=75,
    ))


def test_stage_guidance_keeps_comparative_coverage_and_factual_guardrails():
    research = stage_guidance("research", 4000, 6000, 8000, 147)
    outline = stage_guidance("outline", 4000, 6000, 8000, 147)
    writer = stage_guidance("writer", 4000, 6000, 8000, 147)
    editor = stage_guidance("editor", 4000, 6000, 8000, 147)
    quality = stage_guidance("quality", 4000, 6000, 8000, 147)
    assert "не подменяй запрошенный обзор" in research
    assert "не заменяй материал чек-листом" in outline
    assert "Не заменяй сравнительный обзор" in writer
    assert "восстанови сравнение" in editor
    assert "исходное задание" in quality
    assert "Нельзя выдумывать" in writer
    # The outline must pick comparison/listicle for a comparison brief,
    # the writer must let the brief win over the outline, and Quality must
    # score incompleteness below the acceptance threshold.
    assert "content_type определяй строго по исходному заданию" in outline
    assert "ставь comparison или listicle" in outline
    assert "Исходное задание важнее плана" in writer
    assert "ниже порога приёмки" in quality
    # Editor must be told the maximum is a hard cap so an over-long draft is
    # shortened instead of growing on the next pass.
    assert "Жёсткий максимум — 8000" in editor
    assert "повторный проход не должен увеличивать объём" in editor


@pytest.mark.asyncio
async def test_exact_assignment_survives_outline_writer_editor_quality_and_publisher(tmp_path):
    brief = (
        "Найди лучшие файловые менеджеры Android за 2025–2026 год. "
        "Сравни приложения по приватности, архивам, облакам и домашней сети; "
        "объясни конкретные преимущества."
    )
    published_title = "Какие файловые менеджеры Android удобнее: сравниваем варианты"
    article = "# " + published_title + "\n\n" + "Полезное сравнение. " * 300
    responses = [
        _answer('{"topic": "Android", "key_subtopics": []}'),
        _answer('{"title": "Выбор", "sections": []}'),
        _answer(article),
        _answer('{"seo_score": 90}'),
        _answer(article),
        _answer('{"overall_score": 92}'),
        _answer('{"metadata": {}}'),
    ]
    calls = []

    async def mock_chat(messages, **kwargs):
        calls.append(messages)
        return responses[len(calls) - 1]

    client = AsyncMock()
    client.chat = AsyncMock(side_effect=mock_chat)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    config = ContentForgeConfig(
        llm=LLMConfig(provider="openrouter", api_key="fake-key"),
        pipeline=PipelineConfig(editorial_profile="dzen", language="ru", max_iterations=3),
        output_dir=str(tmp_path),
    )

    with patch("contentforge.pipeline.orchestrator.MiMoClient", return_value=client):
        result = await PipelineOrchestrator(config).run(brief)

    assert result.ok, result.summary()
    assert client.chat.await_count == 7
    assert "ИЗНАЧАЛЬНОЕ ЗАДАНИЕ АВТОРА" not in calls[0][-1].content  # Research sees topic
    for index in (1, 2, 3, 4, 5, 6):
        assert brief in calls[index][-1].content, index
        assert "Нельзя подменять запрошенный жанр" in calls[index][-1].content
    assert "Title: " + published_title in calls[5][-1].content
    assert "Title: " + brief not in calls[5][-1].content
    assert "Title: " + published_title in calls[6][-1].content
    assert config._article_brief == brief
    assert "_article_brief" not in config.model_dump()


@pytest.mark.asyncio
async def test_general_profile_does_not_receive_dzen_brief(tmp_path):
    reply = [
        _answer('{"topic": "x"}'),
        _answer('{"sections": []}'),
        _answer("# General\n\nNormal text."),
        _answer('{"seo_score": 90}'),
        _answer("# General\n\nNormal text."),
        _answer('{"overall_score": 90}'),
        _answer('{"metadata": {}}'),
    ]
    seen = []

    async def mock_chat(messages, **kwargs):
        seen.append(messages)
        return reply[len(seen) - 1]

    client = AsyncMock()
    client.chat = AsyncMock(side_effect=mock_chat)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    config = ContentForgeConfig(
        llm=LLMConfig(api_key="fake"),
        pipeline=PipelineConfig(editorial_profile="general", max_iterations=1),
        output_dir=str(tmp_path),
    )
    with patch("contentforge.pipeline.orchestrator.MiMoClient", return_value=client):
        result = await PipelineOrchestrator(config).run("Original request")
    assert result.ok
    assert not config._article_brief
    assert all("ИЗНАЧАЛЬНОЕ ЗАДАНИЕ АВТОРА" not in msg[-1].content for msg in seen)
