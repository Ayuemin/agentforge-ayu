"""Local, persistent settings for AgentForge in Termux."""
from __future__ import annotations
import json
import os
from pathlib import Path

from .core.config import AgentConfig, ContentForgeConfig, LLMConfig, PipelineConfig

HOME = Path.home() / ".config" / "agentforge"
SETTINGS = HOME / "terminal.json"
KEY = HOME / "openrouter.txt"
RUNS = Path.home() / "agentforge-ayu" / "output" / "runs"
CACHE = HOME / "cache"
AGENTS = ("research", "outline", "writer", "seo", "editor", "quality", "translator", "publisher")
LABELS = ("Исследование", "План", "Автор", "SEO", "Редактор", "Качество", "Перевод", "Публикация")
MODELS = [
    ("MiMo 2.5 Pro", "xiaomi/mimo-v2.5-pro"),
    ("DeepSeek V4.1 Flash", "deepseek/deepseek-v4.1-flash"),
    ("GLM 5.2", "z-ai/glm-5.2"),
    ("Claude Opus 5.5", "anthropic/claude-opus-5.5"),
]
DEFAULTS = {
    "model": "xiaomi/mimo-v2.5-pro",
    "mode": "single",
    "models": {},
    "reasoning": "auto",
    "agent_reasoning": {},
    "prompts": {},
    "user_instructions": {},
    "temperature": 0.7,
    "top_p": 0.9,
    "uncapped": True,
    "max_tokens": 4096,
    "timeout": 120,
    "retries": 3,
    "extra": {},
    "search": {"enabled": True, "calls": 3, "results": 3, "engine": "auto"},
    "pipeline": {"language": "ru", "words": 1000, "passes": 3, "quality": 0.8, "allow_tables": False, "editorial_profile": "dzen", "min_chars": 4000, "target_chars": 6000, "max_chars": 8000, "title_max_chars": 147},
    "download": True,
    "skill": {"enabled": False},
}


def defaults() -> dict:
    return json.loads(json.dumps(DEFAULTS))


def load() -> dict:
    settings = defaults()
    if SETTINGS.is_file():
        user = json.loads(SETTINGS.read_text(encoding="utf-8"))
        for key, value in user.items():
            if key in settings:
                if isinstance(value, dict) and isinstance(settings[key], dict):
                    settings[key].update(value)
                else:
                    settings[key] = value
    return settings


def save(settings: dict) -> None:
    HOME.mkdir(mode=0o700, parents=True, exist_ok=True)
    tmp = SETTINGS.with_suffix(".tmp")
    tmp.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.chmod(0o600)
    tmp.replace(SETTINGS)


def key_get() -> str:
    return os.environ.get("OPENROUTER_API_KEY", "") or (
        KEY.read_text(encoding="utf-8").strip() if KEY.exists() else ""
    )


def key_save(value: str) -> None:
    if not value.strip() or "\n" in value:
        raise ValueError("Некорректный ключ")
    HOME.mkdir(mode=0o700, parents=True, exist_ok=True)
    KEY.write_text(value.strip(), encoding="utf-8")
    KEY.chmod(0o600)


def make_config(data: dict, directory: Path) -> ContentForgeConfig:
    extra = data.get("extra") or {}
    if not isinstance(extra, dict) or set(extra) & {
        "model", "messages", "tools", "plugins", "stream", "temperature", "max_tokens", "top_p"
    }:
        raise ValueError("Дополнительные параметры конфликтуют с основными")
    effort = data.get("reasoning", "auto")
    llm = LLMConfig(
        provider="openrouter", api_key=key_get(), model=data["model"],
        omit_max_tokens=data["uncapped"], max_tokens=data["max_tokens"],
        temperature=data["temperature"], top_p=data["top_p"],
        timeout=data["timeout"], max_retries=data["retries"],
        reasoning_effort=None if effort == "auto" else effort,
        extra_parameters=extra,
    )
    if not llm.api_key:
        raise ValueError("Не задан ключ OpenRouter. Открой раздел «Система».")
    agents = []
    for name in AGENTS:
        changes = {}
        if data["mode"] == "per_agent" and data["models"].get(name):
            changes["model_override"] = data["models"][name]
        if data["agent_reasoning"].get(name):
            changes["reasoning_effort_override"] = data["agent_reasoning"][name]
        if data["prompts"].get(name):
            changes["system_prompt_override"] = data["prompts"][name]
        custom_instruction = data["user_instructions"].get(name, "")
        if name in {"writer", "editor"} and not data["pipeline"].get("allow_tables", False):
            custom_instruction += (
                "\n\nТребования к оформлению статьи: не создавай таблицы "
                "ни в Markdown, ни в HTML. Все сравнения, числовые данные "
                "и характеристики раскрывай обычными абзацами или списками. "
                "Сохраняй все существенные факты и значения."
            )
        if custom_instruction.strip():
            changes["user_prompt_addition"] = custom_instruction.strip()
        if changes:
            agents.append(AgentConfig(name=name, **changes))
    pipeline = data["pipeline"]
    config = ContentForgeConfig(
        llm=llm, agents=agents,
        pipeline=PipelineConfig(
            language=pipeline["language"],
            target_word_count=(
                max(200, round(pipeline["target_chars"] / 6))
                if pipeline.get("editorial_profile") == "dzen" else pipeline["words"]
            ),
            editorial_profile=pipeline.get("editorial_profile", "general"),
            min_chars=pipeline.get("min_chars", 4000),
            target_chars=pipeline.get("target_chars", 6000),
            max_chars=pipeline.get("max_chars", 8000),
            title_max_chars=pipeline.get("title_max_chars", 147),
            max_iterations=pipeline["passes"], quality_threshold=pipeline["quality"],
            enable_translation=False,
        ), output_dir=str(directory),
    )
    if data.get("skill", {}).get("enabled") and config.pipeline.editorial_profile == "dzen":
        from .skill_loader import read_skill

        bundle = read_skill()
        config._skill_texts = {
            name: bundle.context_for(name)
            for name in ("outline", "writer", "editor", "quality")
        }
        config._skill_digest = bundle.digest
    return config
