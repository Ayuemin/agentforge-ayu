"""Dzen editorial adaptation regressions. All tests use mocked models."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from contentforge.agents import AGENT_REGISTRY
from contentforge.agents.research import ResearchAgent
from contentforge.core.config import ContentForgeConfig, LLMConfig, PipelineConfig
from contentforge.core.mimo_client import ChatResponse, TokenUsage
from contentforge.core.token_tracker import TokenTracker
from contentforge.dzen_editorial import article_audit, stage_guidance
from contentforge.pipeline.orchestrator import PipelineOrchestrator
from contentforge import terminal_settings


def _reply(text: str) -> ChatResponse:
    return ChatResponse(
        content=text, usage=TokenUsage(prompt_tokens=100, completion_tokens=200, total_tokens=300)
    )


def test_default_engine_stays_general_and_original_agents_preserved():
    config = ContentForgeConfig()
    assert config.pipeline.editorial_profile == "general"
    assert len(AGENT_REGISTRY) == 8
    assert "research" in AGENT_REGISTRY and "publisher" in AGENT_REGISTRY


def test_terminal_profile_defaults_to_dzen_without_changing_original_prompts(tmp_path, monkeypatch):
    monkeypatch.setattr(terminal_settings, "key_get", lambda: "test-key")
    settings = terminal_settings.defaults()
    config = terminal_settings.make_config(settings, tmp_path)
    assert config.pipeline.editorial_profile == "dzen"
    assert config.pipeline.min_chars == 4000
    assert config.pipeline.target_chars == 6000
    assert config.pipeline.max_chars == 8000
    assert config.pipeline.title_max_chars == 147
    assert config.pipeline.language == "ru"
    assert config.llm.model == "xiaomi/mimo-v2.5-pro"


def test_dzen_guide_does_not_rewrite_json_contracts():
    for name in AGENT_REGISTRY:
        text = stage_guidance(name, 4000, 6000, 8000, 147)
        assert "ДЗЕН" in text
    assert "3–5" in stage_guidance("outline", 4000, 6000, 8000, 147)
    assert "статистику" not in stage_guidance("publisher", 4000, 6000, 8000, 147)


@pytest.mark.asyncio
async def test_research_retains_original_json_schema_and_receives_dzen_policy(tmp_path):
    config = ContentForgeConfig(
        llm=LLMConfig(api_key="test"),
        pipeline=PipelineConfig(editorial_profile="dzen", language="ru"),
        output_dir=str(tmp_path),
    )
    client = AsyncMock()
    client.chat = AsyncMock(return_value=_reply('{"topic": "test"}'))
    agent = ResearchAgent(config=config, client=client, tracker=TokenTracker(str(tmp_path)))
    await agent.execute(topic="test")
    args, _ = client.chat.call_args
    system = args[0][0].content
    assert system.startswith(ResearchAgent.system_prompt)
    assert '"key_subtopics"' in system  # Original hand-off JSON format is intact.
    assert "ЭКСПЕРИМЕНТАЛЬНЫЙ РЕДАКЦИОННЫЙ ПРОФИЛЬ ДЗЕН" in system


def test_character_audit_counts_text_not_markdown_or_title():
    good = "# Короткий заголовок\n\n" + "Простая мысль. " * 410
    report = article_audit(good)
    assert report["passed"] is True
    assert 4000 <= report["body_chars"] <= 8000
    short = article_audit("# Заголовок\n\nДва слова.")
    assert short["passed"] is False
    assert any("короткий" in issue for issue in short["issues"])
    long_title = article_audit("# " + "А" * 148 + "\n\n" + "Текст. " * 1000)
    assert "Заголовок" in " ".join(long_title["issues"])


@pytest.mark.asyncio
async def test_length_feedback_reaches_editor_and_incomplete_article_not_exported(tmp_path):
    config = ContentForgeConfig(
        llm=LLMConfig(provider="openrouter", model="xiaomi/mimo-v2.5-pro", api_key="test"),
        pipeline=PipelineConfig(editorial_profile="dzen", language="ru",
                                max_iterations=2, quality_threshold=0.8),
        output_dir=str(tmp_path),
    )
    responses = [
        _reply(json.dumps({"topic": "test", "key_subtopics": []})),
        _reply(json.dumps({"title": "test", "sections": []})),
        _reply("# Заголовок\n\nКороткий черновик."),
        _reply(json.dumps({"seo_score": 80})),
        _reply("# Заголовок\n\nКороткая статья номер один."),
        _reply(json.dumps({"overall_score": 90, "improvement_suggestions": ["Упростить термин"]})),
        _reply("# Заголовок\n\nКороткая статья номер два."),
        _reply(json.dumps({"overall_score": 90, "improvement_suggestions": []})),
        _reply(json.dumps({"metadata": {"title": "test"}})),
    ]
    seen = []

    async def fake_chat(messages, **kwargs):
        seen.append(messages)
        return responses[len(seen) - 1]

    with patch("contentforge.pipeline.orchestrator.MiMoClient") as client_factory:
        mock = AsyncMock()
        mock.chat = AsyncMock(side_effect=fake_chat)
        mock.__aenter__ = AsyncMock(return_value=mock)
        mock.__aexit__ = AsyncMock(return_value=None)
        client_factory.return_value = mock
        result = await PipelineOrchestrator(config).run("test")

    assert len(seen) == 9
    assert result.status == "needs_review"
    assert result.editorial_audit["passed"] is False
    assert (tmp_path / "НЕГОТОВО_требует_правки.md").exists()
    # Editor call 2 receives actual deterministic audit plus quality suggestions.
    assert "Текст слишком короткий" in seen[6][-1].content
    assert "Упростить термин" in seen[6][-1].content


@pytest.mark.asyncio
async def test_fitting_article_keeps_original_one_pass_exit(tmp_path):
    config = ContentForgeConfig(
        llm=LLMConfig(api_key="test"),
        pipeline=PipelineConfig(editorial_profile="dzen", language="ru",
                                max_iterations=3),
        output_dir=str(tmp_path),
    )
    article = "# Полезный заголовок\n\n" + "Понятная полезная информация. " * 220
    responses = [
        _reply('{"key_subtopics": []}'),
        _reply('{"sections": []}'),
        _reply(article),
        _reply('{"seo_score": 90}'),
        _reply(article),
        _reply('{"overall_score": 92}'),
        _reply('{"metadata": {}}'),
    ]
    mock = AsyncMock()
    mock.chat = AsyncMock(side_effect=responses)
    mock.__aenter__ = AsyncMock(return_value=mock)
    mock.__aexit__ = AsyncMock(return_value=None)
    with patch("contentforge.pipeline.orchestrator.MiMoClient", return_value=mock):
        result = await PipelineOrchestrator(config).run("test")
    assert result.ok is True
    assert result.editorial_audit["passed"] is True
    assert mock.chat.await_count == 7
