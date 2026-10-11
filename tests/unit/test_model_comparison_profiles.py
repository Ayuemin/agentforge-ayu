"""Offline regression checks for MiMo-vs-DeepSeek profile comparison."""

from pathlib import Path

import pytest
from click.testing import CliRunner

from contentforge.agents import AGENT_REGISTRY
from contentforge.cli import main
from contentforge.core.config import ContentForgeConfig
from contentforge.pipeline.orchestrator import PipelineResult


ROOT = Path(__file__).resolve().parents[2]
PROFILES = (
    ("contentforge.mimo.yaml", "xiaomi/mimo-v2.5-pro"),
    ("contentforge.deepseek.yaml", "deepseek/deepseek-v4.1-flash"),
)


@pytest.mark.parametrize("filename,model", PROFILES)
def test_every_agent_uses_selected_model(filename, model, monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    config = ContentForgeConfig.from_yaml(ROOT / filename)
    assert config.llm.provider == "openrouter"
    assert config.llm.model == model
    assert config.llm.omit_max_tokens is True
    assert config.pipeline.language == "ru"
    assert config.pipeline.max_iterations == 3
    assert config.pipeline.enable_translation is False
    assert config.agents == []
    assert len(AGENT_REGISTRY) == 8
    for name in AGENT_REGISTRY:
        assert config.get_agent_config(name).model_override is None


def test_profiles_differ_only_by_model(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    first = ContentForgeConfig.from_yaml(ROOT / PROFILES[0][0])
    second = ContentForgeConfig.from_yaml(ROOT / PROFILES[1][0])
    first.llm.model = second.llm.model
    assert first.model_dump() == second.model_dump()


@pytest.mark.parametrize("filename,model", PROFILES)
def test_cli_uses_profile_model_without_network(filename, model, monkeypatch, tmp_path):
    recorded = []

    async def fake_run(config, topic):
        recorded.append((config, topic))
        return PipelineResult(status="success")

    monkeypatch.setattr("contentforge.cli._run_pipeline", fake_run)
    result = CliRunner().invoke(
        main,
        [
            "--config", str(ROOT / filename), "generate",
            "Test topic", "--output", str(tmp_path / "separate-output"),
        ],
    )
    assert result.exit_code == 0, result.output
    assert len(recorded) == 1
    config, topic = recorded[0]
    assert topic == "Test topic"
    assert config.llm.model == model
    assert config.pipeline.language == "ru"
    assert config.pipeline.target_word_count == 1500
    assert config.output_dir == str(tmp_path / "separate-output")
