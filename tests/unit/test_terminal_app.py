"""Offline checks for the Termux terminal app (never spends credits)."""
from __future__ import annotations

import copy
import json

from contentforge import terminal_app, terminal_search, terminal_settings


def test_initial_settings_match_requested_defaults():
    data = terminal_settings.defaults()
    assert data["model"] == "xiaomi/mimo-v2.5-pro"
    assert data["search"]["enabled"] is True
    assert data["search"]["calls"] == 3
    assert data["pipeline"]["language"] == "ru"
    assert data["pipeline"]["passes"] == 3
    assert data["uncapped"] is True
    assert data["mode"] == "single"


def test_save_load_settings_uses_private_file(tmp_path, monkeypatch):
    path = tmp_path / "settings.json"
    monkeypatch.setattr(terminal_settings, "SETTINGS", path)
    data = terminal_settings.defaults()
    data["model"] = "deepseek/deepseek-v4.1-flash"
    terminal_settings.save(data)
    assert terminal_settings.load()["model"] == data["model"]
    assert path.stat().st_mode & 0o777 == 0o600


def test_all_agents_inherit_mimo_by_default(tmp_path, monkeypatch):
    monkeypatch.setattr(terminal_settings, "key_get", lambda: "fake-example-key")
    data = terminal_settings.defaults()
    config = terminal_settings.make_config(data, tmp_path)
    assert config.llm.model == "xiaomi/mimo-v2.5-pro"
    assert config.pipeline.language == "ru"
    assert config.pipeline.max_iterations == 3
    assert config.llm.omit_max_tokens
    for name in terminal_settings.AGENTS:
        assert config.get_agent_config(name).model_override is None


def test_per_agent_models_do_not_leak_into_single_mode(tmp_path, monkeypatch):
    monkeypatch.setattr(terminal_settings, "key_get", lambda: "fake-example-key")
    data = terminal_settings.defaults()
    data["models"]["editor"] = "anthropic/claude-opus-5.5"
    assert terminal_settings.make_config(data, tmp_path).get_agent_config("editor").model_override is None
    data["mode"] = "per_agent"
    config = terminal_settings.make_config(data, tmp_path)
    assert config.get_agent_config("editor").model_override == "anthropic/claude-opus-5.5"
    assert config.get_agent_config("writer").model_override is None


def test_openrouter_search_max_three_paid_calls(monkeypatch):
    posts = []
    class FakeResponse:
        def raise_for_status(self):
            return None
        def json(self):
            return {"choices": [{"message": {"content": "Result with URL https://example.com"}}]}
    class FakeClient:
        def __init__(self, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return None
        def post(self, url, **kwargs):
            posts.append((url, kwargs["json"]))
            return FakeResponse()
    monkeypatch.setattr(terminal_search.httpx, "Client", FakeClient)
    settings = terminal_settings.defaults()
    settings["search"]["engine"] = "openrouter"
    report = terminal_search.gather("Example of Android software", settings, "test-key")
    assert report.paid_calls == 3
    assert len(posts) == 3
    assert all(request["plugins"] == [{"id": "web", "max_results": 3}]
               for _, request in posts)


def test_zero_search_never_contacts_network(monkeypatch):
    def no_network(*args, **kwargs):
        raise AssertionError("network must not be reached")
    monkeypatch.setattr(terminal_search.httpx, "Client", no_network)
    settings = terminal_settings.defaults()
    settings["search"]["calls"] = 0
    result = terminal_search.gather("Example", settings, "irrelevant")
    assert result.paid_calls == 0
    assert result.sources == []


def test_clean_export_has_no_comments_or_frontmatter():
    content = "---\ntitle: internal\n---\n# Article\n\nText.\n<!-- edit changes -->"
    result = terminal_app.clean_article(content)
    assert result == "# Article\n\nText.\n"


def test_user_extra_parameters_cannot_replace_model(tmp_path, monkeypatch):
    monkeypatch.setattr(terminal_settings, "key_get", lambda: "test-key")
    data = terminal_settings.defaults()
    data["extra"] = {"model": "another/provider"}
    try:
        terminal_settings.make_config(data, tmp_path)
    except ValueError:
        pass
    else:
        raise AssertionError("model must remain controlled by dedicated setting")
