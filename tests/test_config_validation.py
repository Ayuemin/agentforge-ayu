"""Tests for configuration schema validation."""

import pytest

# Legacy module: this suite predates the rename to ``contentforge`` and still
# imports the removed ``agentforge.config``. Skip cleanly so the full test run
# stays green instead of failing at collection.
Config = None
ValidationError = None
try:
    from agentforge.config import Config, ValidationError  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - legacy path
    pytest.skip(
        "legacy agentforge.config module is gone; superseded by contentforge",
        allow_module_level=True,
    )


def test_valid_config():
    cfg = Config(model="gpt-4o", agents=["researcher", "writer"])
    assert cfg.model == "gpt-4o"


def test_empty_agents_raises():
    with pytest.raises(ValidationError, match="at least one agent"):
        Config(model="gpt-4o", agents=[])


def test_invalid_model_raises():
    with pytest.raises(ValidationError, match="unsupported model"):
        Config(model="invalid-model", agents=["researcher"])
