"""Regression tests for the Android/OpenRouter opt-in profile.

No API key or network connection is needed.
"""

import json

import httpx
import pytest
from click.testing import CliRunner

from contentforge.agents.research import ResearchAgent
from contentforge.cli import main
from contentforge.core.config import ContentForgeConfig, LLMConfig, PipelineConfig
from contentforge.core.llm_client import ChatMessage, ChatResponse, LLMClient
from contentforge.core.token_tracker import TokenTracker
from contentforge.pipeline.orchestrator import PipelineResult


@pytest.mark.asyncio
@pytest.mark.parametrize("omit,expected_cap", [(True, None), (False, 8192)])
async def test_non_streaming_request_token_limit(omit, expected_cap):
    payloads = []

    def handler(request):
        payloads.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "Готово"}, "finish_reason": "stop"}],
                "model": "test-model",
                "usage": {"prompt_tokens": 5, "completion_tokens": 10, "total_tokens": 15},
            },
        )

    config = LLMConfig(provider="openrouter", api_key="test", omit_max_tokens=omit)
    async with LLMClient(config) as client:
        await client._client.aclose()
        client._client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url=config.base_url
        )
        response = await client.chat(
            [ChatMessage(role="user", content="Тест")], max_tokens=8192
        )
        assert response.content == "Готово"

    assert len(payloads) == 1
    assert payloads[0].get("max_tokens") == expected_cap
    assert ("max_tokens" in payloads[0]) is (not omit)


@pytest.mark.asyncio
@pytest.mark.parametrize("omit,expected_cap", [(True, None), (False, 8192)])
async def test_streaming_request_token_limit(omit, expected_cap):
    payloads = []

    def handler(request):
        payloads.append(json.loads(request.content))
        stream_data = (
            'data: {"choices":[{"delta":{"content":"Готово"},"finish_reason":"stop"}]}\\n\\n'
            "data: [DONE]\\n\\n"
        ).replace("\\n", "\n")
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=stream_data.encode(),
        )

    config = LLMConfig(provider="openrouter", api_key="test", omit_max_tokens=omit)
    async with LLMClient(config) as client:
        await client._client.aclose()
        client._client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url=config.base_url
        )
        chunks = [
            c async for c in client.stream_chunks(
                [ChatMessage(role="user", content="Тест")], max_tokens=8192
            )
        ]
        assert any(c.delta == "Готово" for c in chunks)

    assert len(payloads) == 1
    assert payloads[0].get("max_tokens") == expected_cap
    assert ("max_tokens" in payloads[0]) is (not omit)


@pytest.mark.asyncio
async def test_legacy_stream_chat_obeys_no_cap():
    payloads = []

    def handler(request):
        payloads.append(json.loads(request.content))
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=b'data: {"choices":[{"delta":{"content":"ok"}}]}\n\ndata: [DONE]\n\n',
        )

    config = LLMConfig(provider="openrouter", api_key="test", omit_max_tokens=True)
    async with LLMClient(config) as client:
        await client._client.aclose()
        client._client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url=config.base_url
        )
        response = await client.chat(
            [ChatMessage(role="user", content="Test")], max_tokens=8192, stream=True
        )
        assert response.content == "ok"

    assert "max_tokens" not in payloads[0]


@pytest.mark.asyncio
async def test_russian_instructions_are_additive(tmp_path):
    config = ContentForgeConfig(pipeline=PipelineConfig(language="ru"))
    calls = []

    class FakeClient:
        async def chat(self, messages, **kwargs):
            calls.append((messages, kwargs))
            return ChatResponse(content="{}", model="test")

    agent = ResearchAgent(
        config=config, client=FakeClient(), tracker=TokenTracker(output_dir=tmp_path)
    )
    original = agent.system_prompt
    await agent.execute(topic="Тестовая тема")
    assert agent.system_prompt == original
    assert calls[0][0][0].content.startswith(original)
    assert "Russian (ru)" in calls[0][0][0].content


def test_cli_preserves_yaml_defaults(tmp_path, monkeypatch):
    cfg_path = tmp_path / "contentforge.android.yaml"
    cfg_path.write_text(
        "llm:\n  provider: openrouter\n"
        "  model: deepseek/deepseek-v4.1-flash\n  omit_max_tokens: true\n"
        "pipeline:\n  language: ru\n  target_word_count: 1500\n",
        encoding="utf-8",
    )
    used = []

    async def fake_pipeline(config, topic):
        used.append((config, topic))
        return PipelineResult(status="success")

    monkeypatch.setattr("contentforge.cli._run_pipeline", fake_pipeline)
    result = CliRunner().invoke(
        main, ["--config", str(cfg_path), "generate", "Тестовая тема"]
    )
    assert result.exit_code == 0, result.output
    assert len(used) == 1
    assert used[0][0].pipeline.language == "ru"
    assert used[0][0].pipeline.target_word_count == 1500
    assert used[0][0].llm.model == "deepseek/deepseek-v4.1-flash"
    assert used[0][0].llm.omit_max_tokens is True
