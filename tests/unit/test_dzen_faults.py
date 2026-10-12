"""Regression tests for failures reported by the Android Termux user."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from contentforge.agents.quality import QualityAgent
from contentforge.core.config import ContentForgeConfig, LLMConfig, PipelineConfig
from contentforge.core.mimo_client import ChatResponse, TokenUsage
from contentforge.core.request_errors import describe_error
from contentforge.core.token_tracker import TokenTracker
from contentforge.pipeline.orchestrator import PipelineOrchestrator
from contentforge import terminal_app


def _answer(value: str) -> ChatResponse:
    return ChatResponse(
        content=value, usage=TokenUsage(prompt_tokens=10, completion_tokens=15, total_tokens=25)
    )


def _config(tmp_path: Path) -> ContentForgeConfig:
    return ContentForgeConfig(
        llm=LLMConfig(provider="openrouter", api_key="test-key", model="model/test"),
        pipeline=PipelineConfig(editorial_profile="dzen", language="ru", max_iterations=2),
        output_dir=str(tmp_path),
    )


def test_empty_message_network_exceptions_are_readable():
    assert "ReadTimeout" in describe_error(httpx.ReadTimeout(""), timeout=120)
    assert "120" in describe_error(httpx.ReadTimeout(""), timeout=120)
    assert "401" in describe_error(httpx.HTTPStatusError(
        "", request=httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions"),
        response=httpx.Response(401)
    ))
    assert "ValueError" in describe_error(ValueError(""))


@pytest.mark.asyncio
async def test_research_timeout_stops_pipeline_and_writes_diagnostics(tmp_path):
    mock = AsyncMock()
    mock.chat = AsyncMock(side_effect=httpx.ReadTimeout(""))
    mock.__aenter__ = AsyncMock(return_value=mock)
    mock.__aexit__ = AsyncMock(return_value=None)
    with patch("contentforge.pipeline.orchestrator.MiMoClient", return_value=mock):
        result = await PipelineOrchestrator(_config(tmp_path)).run("Файловые менеджеры")
    assert result.status == "failed"
    assert result.failed_stage == "research"
    assert "ReadTimeout" in result.error_message
    status = json.loads((tmp_path / "run_status.json").read_text(encoding="utf-8"))
    assert status["failed_stage"] == "research"
    assert "test-key" not in json.dumps(status)
    assert mock.chat.await_count == 1  # no downstream agent requests


@pytest.mark.asyncio
async def test_editor_failure_preserves_writer_draft_and_skips_publisher(tmp_path):
    response = [
        _answer('{"topic": "test"}'),
        _answer('{"title": "test", "sections": []}'),
        _answer("# Реальный черновик\n\nЕсть полезные факты."),
        _answer('{"seo_score": 80}'),
        httpx.ReadTimeout(""),
    ]
    mock = AsyncMock()
    mock.chat = AsyncMock(side_effect=response)
    mock.__aenter__ = AsyncMock(return_value=mock)
    mock.__aexit__ = AsyncMock(return_value=None)
    with patch("contentforge.pipeline.orchestrator.MiMoClient", return_value=mock):
        result = await PipelineOrchestrator(_config(tmp_path)).run("Проверка")
    assert result.status == "failed"
    assert result.failed_stage == "editor"
    assert (tmp_path / "03_writer.md").exists()
    assert "полезные факты" in (tmp_path / "03_writer.md").read_text(encoding="utf-8")
    assert mock.chat.await_count == 5
    assert not (tmp_path / "08_publisher.json").exists()


@pytest.mark.asyncio
async def test_quality_score_parses_markdown_fenced_json(tmp_path):
    client = AsyncMock()
    client.chat = AsyncMock(return_value=_answer(
        chr(96) * 3 + 'json\n{"overall_score": 91, "pass_threshold": true}\n' + chr(96) * 3
    ))
    agent = QualityAgent(_config(tmp_path), client, TokenTracker(output_dir=str(tmp_path)))
    result = await agent.execute(content="# Статья\n\nТекст")
    assert result.metadata["overall_score"] == 91
    assert result.metadata["score_parse_error"] == ""


def test_previous_unfinished_run_is_visible_as_draft(tmp_path, monkeypatch):
    runs = tmp_path / "runs"
    old = runs / "20261012_092708_600207"
    old.mkdir(parents=True)
    (old / "topic.txt").write_text("Файловые менеджеры", encoding="utf-8")
    (old / "НЕГОТОВО_требует_правки.md").write_text(
        "# Статья\n\nТекст черновика.", encoding="utf-8"
    )
    (old / "20261012_article.md").write_text("Другая техническая версия.", encoding="utf-8")
    monkeypatch.setattr(terminal_app.cfg, "RUNS", runs)

    selected = []
    def choose(title, options):
        selected.append((title, options))
        return 1 if len(selected) == 1 else 2

    copied = []
    monkeypatch.setattr(terminal_app, "choose", choose)
    monkeypatch.setattr(terminal_app, "ask", lambda *args: "нет")
    monkeypatch.setattr(terminal_app, "download_article",
                        lambda *args, **kwargs: copied.append((args, kwargs)))
    terminal_app.recent_menu({})
    assert "ЧЕРНОВИК" in selected[0][1][0]
    assert "Черновик" in selected[1][0]
    assert copied == []  # must not silently export a failed article

    selected.clear()
    monkeypatch.setattr(terminal_app, "ask", lambda *args: "да")
    terminal_app.recent_menu({})
    assert copied[0][1]["draft"] is True
    assert copied[0][0][0].name == "НЕГОТОВО_требует_правки.md"
