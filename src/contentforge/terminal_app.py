"""Beginner-friendly terminal control panel for AgentForge.

Run: python -m contentforge.terminal_app
"""
from __future__ import annotations

import asyncio
import getpass
import json
import logging
import re
import shutil
import subprocess
import tempfile
import time
from datetime import datetime
from pathlib import Path

import httpx
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from . import terminal_settings as cfg
from .terminal_search import gather, report_to_json

console = Console()


def say(text: str) -> None:
    console.print(text, markup=False)


def ask(text: str, default: str = "") -> str:
    return input(f"{text}" + (f" [{default}]" if default else "") + ": ").strip() or default


def choose(title: str, options: list[str]) -> int:
    console.print(Panel("\n".join(f"{i}. {label}" for i, label in enumerate(options, 1)),
                        title=title, border_style="cyan"))
    try:
        value = int(ask("Номер", "0"))
        return value if 1 <= value <= len(options) else 0
    except ValueError:
        return 0


def number(message: str, previous, cast=int, lower=None, upper=None):
    raw = ask(message, str(previous)).replace(",", ".")
    value = cast(raw)
    if (lower is not None and value < lower) or (upper is not None and value > upper):
        raise ValueError(f"Допустимые значения: {lower}…{upper}")
    return value


def editor(label: str, initial: str = "") -> str | None:
    """Launch full-screen editor if available; fallback to multi-line input."""
    program = shutil.which("nano") or shutil.which("vi")
    if program:
        with tempfile.TemporaryDirectory(prefix="forge-editor-") as directory:
            destination = Path(directory) / "draft.txt"
            destination.write_text(initial, encoding="utf-8")
            say(f"Открываю редактор: {label}. Сохрани файл и выйди.")
            code = subprocess.call([program, str(destination)])
            if code != 0:
                say("Редактор завершился с ошибкой; изменения не приняты.")
                return None
            return destination.read_text(encoding="utf-8").strip()
    say(f"{label}. Вставь текст построчно. Одна строка /готово — сохранить.")
    say("Для отмены введи /отмена отдельной строкой.")
    lines = []
    while True:
        line = input()
        if line == "/готово":
            return "\n".join(lines).strip()
        if line == "/отмена":
            return None
        lines.append(line)


def topic_input() -> str:
    say("Введи тему или ссылку и нажми Enter.")
    say("Для длинного задания введи /много — откроется многострочный ввод.")
    topic = input("> ").strip()
    if topic == "/много":
        topic = editor("Задание", "") or ""
    return topic


def select_model() -> str | None:
    options = [name + " · " + ident for name, ident in cfg.MODELS]
    options += ["Вставить свой ID модели", "Найти модель в каталоге OpenRouter"]
    pick = choose("Модель OpenRouter", options)
    if 1 <= pick <= len(cfg.MODELS):
        return cfg.MODELS[pick - 1][1]
    if pick == len(cfg.MODELS) + 1:
        value = ask("ID (provider/model)")
        if not re.fullmatch(r"[A-Za-z0-9_.:/+-]{3,160}", value) or "/" not in value:
            say("Некорректный ID модели.")
            return None
        return value
    if pick == len(cfg.MODELS) + 2:
        query = ask("Название или часть ID").lower()
        try:
            response = httpx.get("https://openrouter.ai/api/v1/models", timeout=18)
            response.raise_for_status()
            options = [m for m in response.json().get("data", [])
                       if query in str(m.get("id", "")).lower()
                       or query in str(m.get("name", "")).lower()]
            matches = options[:20]
            if not matches:
                say("Совпадений не найдено.")
                return None
            pick = choose("Каталог (первые 20 совпадений)",
                          [m.get("name", "") + " · " + m["id"] for m in matches])
            return matches[pick - 1]["id"] if pick else None
        except (httpx.HTTPError, ValueError, KeyError) as error:
            say(f"Каталог недоступен: {type(error).__name__}")
    return None


def model_menu(s: dict) -> None:
    while True:
        label = "Одна модель на всех" if s["mode"] == "single" else "По каждому агенту"
        say(f"\nОсновная: {s['model']}\nРежим: {label}")
        pick = choose("Модели и агенты", [
            "Сменить основную модель",
            "Переключить режим: одна модель / по агентам",
            "Настроить модель конкретного агента",
            "Настроить reasoning для агента",
            "Назад"])
        if pick == 1:
            model = select_model()
            if model:
                s["model"] = model
                cfg.save(s)
        elif pick == 2:
            s["mode"] = "per_agent" if s["mode"] == "single" else "single"
            cfg.save(s)
        elif pick == 3:
            index = choose("Агент", [f"{lab}: {s['models'].get(n, 'основная')}"
                                      for n, lab in zip(cfg.AGENTS, cfg.LABELS)])
            if index:
                agent = cfg.AGENTS[index - 1]
                if choose("Назначение", ["Выбрать модель", "Наследовать основную"]) == 2:
                    s["models"].pop(agent, None)
                    cfg.save(s)
                else:
                    model = select_model()
                    if model:
                        s["models"][agent] = model
                        s["mode"] = "per_agent"
                        cfg.save(s)
        elif pick == 4:
            index = choose("Агент", list(cfg.LABELS))
            if index:
                name = cfg.AGENTS[index - 1]
                options = ["Наследовать глобальную", "auto (не задавать)", "minimal",
                           "low", "medium", "high", "xhigh", "none"]
                value = choose("Reasoning", options)
                if value == 1:
                    s["agent_reasoning"].pop(name, None)
                elif value:
                    s["agent_reasoning"][name] = options[value - 1].split()[0]
                cfg.save(s)
        else:
            return


def pipeline_menu(s: dict) -> None:
    while True:
        p = s["pipeline"]
        say(f"\nРусский: {p['language']} · слов: {p['words']} · проходов: до {p['passes']}")
        pick = choose("Статья и конвейер", [
            "Целевой объём статьи (слов)", "Максимум проходов редактора",
            "Порог качества (0.0—1.0)", "Язык",
            "Назад"])
        if not pick or pick == 5:
            return
        try:
            if pick == 1:
                p["words"] = number("Количество слов", p["words"], int, 200, 15000)
            elif pick == 2:
                p["passes"] = number("Максимум проходов", p["passes"], int, 1, 20)
            elif pick == 3:
                p["quality"] = number("Порог", p["quality"], float, 0, 1)
            elif pick == 4:
                p["language"] = ask("Код языка", p["language"])[:8]
            cfg.save(s)
        except ValueError as error:
            say(f"Ошибка: {error}")
