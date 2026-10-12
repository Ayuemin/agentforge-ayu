"""Offline verification: full skill files, safe ZIP import, and optional prompt use."""
from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from contentforge import skill_loader, terminal_settings
from contentforge.agents.writer import WriterAgent
from contentforge.core.mimo_client import ChatResponse, TokenUsage
from contentforge.core.token_tracker import TokenTracker


@pytest.fixture
def skill_archive(tmp_path):
    path = tmp_path / "nikitina-text.zip"
    data = {"SKILL.md": "---\nname: nikitina-text\n---\nRead all seven references."}
    for num, name in enumerate(skill_loader.REFERENCE_FILES):
        data[name] = "Верный полный текст №" + str(num) + "\n" + ("Правило. " * (100 + num))
    with zipfile.ZipFile(path, "w") as archive:
        for name, content in data.items():
            archive.writestr("nikitina-text/" + name, content)
    return path, data


def test_full_skill_no_summarization(skill_archive, tmp_path):
    path, original = skill_archive
    folder = tmp_path / "private-skills" / "nikitina-text"
    installed = skill_loader.install_zip(path, folder)
    loaded = skill_loader.read_skill(folder)
    assert loaded.files == original
    assert installed.digest == loaded.digest
    for name in skill_loader.REFERENCE_FILES:
        assert original[name] in loaded.context_for("writer")
        assert original[name] in loaded.context_for("editor")
    assert skill_loader.REFERENCE_FILES[0] not in loaded.context_for("outline")
    assert "Заголовок" not in loaded.files["SKILL.md"]
    assert len(loaded.context_for("writer")) > sum(map(len, original.values()))


def test_selected_stages_get_complete_original_files(skill_archive, tmp_path):
    path, files = skill_archive
    bundle = skill_loader.install_zip(path, tmp_path / "s")
    outline = bundle.context_for("outline")
    quality = bundle.context_for("quality")
    assert files["references/headlines-and-openings.md"] in outline
    assert files["references/structure-and-clarity.md"] in outline
    assert files["references/editing-checklist.md"] in quality
    assert bundle.context_for("research") == ""
    assert bundle.context_for("publisher") == ""


def test_missing_reference_does_not_replace_installed_skill(skill_archive, tmp_path):
    path, _ = skill_archive
    folder = tmp_path / "skill"
    existing = skill_loader.install_zip(path, folder)
    invalid = tmp_path / "incomplete.zip"
    with zipfile.ZipFile(invalid, "w") as archive:
        archive.writestr("SKILL.md", "nikitina-text")
    with pytest.raises(ValueError, match="неполный"):
        skill_loader.install_zip(invalid, folder)
    assert skill_loader.read_skill(folder).digest == existing.digest


def test_zip_path_traversal_rejected(skill_archive, tmp_path):
    zip_path = tmp_path / "malicious.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("../../secret", "payload")
    with pytest.raises(ValueError, match="опасный|структура"):
        skill_loader.install_zip(zip_path, tmp_path / "skill")
    assert not (tmp_path / "secret").exists()


def test_when_disabled_no_skill_files_are_read(tmp_path, monkeypatch):
    monkeypatch.setattr(terminal_settings, "key_get", lambda: "fake-test-key")
    settings = terminal_settings.defaults()
    assert settings["skill"]["enabled"] is False
    result = terminal_settings.make_config(settings, tmp_path)
    assert not result._skill_texts
    assert not result._skill_digest


@pytest.mark.asyncio
async def test_enabled_skill_is_attached_without_overwriting_original_prompt(
    skill_archive, tmp_path, monkeypatch
):
    path, original = skill_archive
    bundle = skill_loader.install_zip(path, tmp_path / "local")
    monkeypatch.setattr(skill_loader, "read_skill", lambda: bundle)
    monkeypatch.setattr(terminal_settings, "key_get", lambda: "fake-test-key")
    settings = terminal_settings.defaults()
    settings["skill"]["enabled"] = True
    config = terminal_settings.make_config(settings, tmp_path)
    assert config._skill_digest == bundle.digest
    assert "_skill_texts" not in config.model_dump()
    assert "nikitina-text" not in json.dumps(config.model_dump(), ensure_ascii=False)

    client = AsyncMock()
    client.chat = AsyncMock(return_value=ChatResponse(
        content="# Статья\n\nТекст.", usage=TokenUsage(total_tokens=12),
    ))
    agent = WriterAgent(config, client, TokenTracker(str(tmp_path)))
    result = await agent.run(outline="Plan", research_data="Facts", language="ru")
    assert result.ok
    messages = client.chat.call_args.args[0]
    system_text = messages[0].content
    assert system_text.startswith(WriterAgent.system_prompt)
    for content in original.values():
        assert content in system_text


def test_general_profile_keeps_skill_disabled_even_if_requested(tmp_path, monkeypatch):
    monkeypatch.setattr(terminal_settings, "key_get", lambda: "fake-test-key")
    settings = terminal_settings.defaults()
    settings["pipeline"]["editorial_profile"] = "general"
    settings["skill"]["enabled"] = True
    config = terminal_settings.make_config(settings, tmp_path)
    assert not config._skill_texts
