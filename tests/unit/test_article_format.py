"""Offline checks: suppress article tables without losing their values."""
from __future__ import annotations

from contentforge.article_format import format_article
from contentforge import terminal_settings


def test_pipe_table_converts_to_prose_list_preserving_cells():
    original = (
        "# Сравнение\n\n"
        "| Модель | Цена | Вывод |\n"
        "| :--- | ---: | --- |\n"
        "| MiMo | $0.30 | Хорошо |\n"
        "| DeepSeek | $0.13 | Быстро |\n\n"
        "После сравнения.\n"
    )
    actual, remaining = format_article(original)
    assert not remaining
    assert "| ---" not in actual and "| :---" not in actual
    for item in ("MiMo", "$0.30", "Хорошо", "DeepSeek", "$0.13",
                 "Быстро", "После сравнения"):
        assert item in actual


def test_table_in_code_fence_is_not_modified():
    fence = chr(96) * 3
    original = f"{fence}markdown\n| A | B |\n| --- | --- |\n| 1 | 2 |\n{fence}\n"
    actual, remaining = format_article(original)
    assert actual == original
    assert not remaining


def test_html_table_preserved_and_flagged_not_deleted():
    original = "<table><tr><td>Важное число: 17</td></tr></table>"
    actual, remaining = format_article(original)
    assert actual == original
    assert remaining is True


def test_tables_allowed_does_not_reformat():
    original = "| A | B |\n| --- | --- |\n| 1 | 2 |\n"
    assert format_article(original, allow_tables=True) == (original, False)


def test_default_prohibits_tables_for_writer_and_editor(tmp_path, monkeypatch):
    monkeypatch.setattr(terminal_settings, "key_get", lambda: "fake-key")
    settings = terminal_settings.defaults()
    assert settings["pipeline"]["allow_tables"] is False
    config = terminal_settings.make_config(settings, tmp_path)
    for agent in ("writer", "editor"):
        instruction = config.get_agent_config(agent).user_prompt_addition
        assert "не создавай таблицы" in instruction
        assert "списками" in instruction
    assert config.get_agent_config("outline").user_prompt_addition is None


def test_existing_custom_instructions_are_preserved(tmp_path, monkeypatch):
    monkeypatch.setattr(terminal_settings, "key_get", lambda: "fake-key")
    settings = terminal_settings.defaults()
    settings["user_instructions"]["writer"] = "Пиши от первого лица."
    config = terminal_settings.make_config(settings, tmp_path)
    instruction = config.get_agent_config("writer").user_prompt_addition
    assert "Пиши от первого лица." in instruction
    assert "не создавай таблицы" in instruction


def test_allowing_tables_disables_extra_prompt(tmp_path, monkeypatch):
    monkeypatch.setattr(terminal_settings, "key_get", lambda: "fake-key")
    settings = terminal_settings.defaults()
    settings["pipeline"]["allow_tables"] = True
    config = terminal_settings.make_config(settings, tmp_path)
    for agent in ("writer", "editor"):
        assert config.get_agent_config(agent).user_prompt_addition is None
