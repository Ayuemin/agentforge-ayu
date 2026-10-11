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
    program = shutil.which("nano")
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


def search_menu(s: dict) -> None:
    while True:
        q = s["search"]
        say(f"\nПоиск: {'ВКЛ' if q['enabled'] else 'ВЫКЛ'}"
            f" · максимум {q['calls']} запросов · {q['results']} результатов"
            f" · движок: {q['engine']}")
        pick = choose("Интернет и источники", [
            "Включить / выключить",
            "Сколько поисковых запросов разрешено",
            "Сколько результатов на запрос",
            "Движок: автоматически / бесплатный / OpenRouter",
            "Назад"])
        try:
            if pick == 1:
                q["enabled"] = not q["enabled"]
            elif pick == 2:
                q["calls"] = number("Максимум запросов", q["calls"], int, 0, 30)
            elif pick == 3:
                q["results"] = number("Результатов на запрос", q["results"], int, 1, 10)
            elif pick == 4:
                index = choose("Поисковый движок", [
                    "Авто: бесплатный Bing RSS, при сбое — OpenRouter",
                    "Только бесплатный Bing RSS",
                    "OpenRouter (платный веб-поиск)"])
                if index:
                    q["engine"] = ["auto", "free", "openrouter"][index - 1]
            else:
                return
            cfg.save(s)
        except ValueError as err:
            say(f"Ошибка: {err}")


def prompt_menu(s: dict) -> None:
    from .agents import AGENT_REGISTRY
    import inspect
    while True:
        index = choose("Промпты агентов", list(cfg.LABELS) + ["Назад"])
        if not index or index > len(cfg.AGENTS):
            return
        name = cfg.AGENTS[index - 1]
        cls = AGENT_REGISTRY[name]
        while True:
            selection = choose(f"Промпты — {cfg.LABELS[index - 1]}", [
                "Посмотреть оригинальный системный промпт",
                "Посмотреть оригинальный шаблон задания (исходный код)",
                "Редактировать свой системный промпт",
                "Дополнительные инструкции к заданию",
                "Восстановить оригинальные промпты",
                "Назад"])
            if selection == 1:
                console.print(Panel(cls.system_prompt, title="Оригинальный system prompt"))
            elif selection == 2:
                raw = inspect.getsource(cls.execute)
                pos = raw.find('prompt = f"""')
                if pos >= 0:
                    end = raw.find('"""', pos + len('prompt = f"""'))
                    console.print(Panel(raw[pos + len('prompt = f"""'):end],
                                        title="Оригинальный user template"))
                else:
                    say("Шаблон в этом агенте формируется иначе; смотри исходник.")
            elif selection == 3:
                current = s["prompts"].get(name, cls.system_prompt)
                updated = editor("Системный промпт", current)
                if updated is not None and updated.strip():
                    s["prompts"][name] = updated
                    cfg.save(s)
                    say("Системный промпт сохранён отдельно от исходника.")
            elif selection == 4:
                updated = editor("Дополнительные инструкции к шаблону",
                                 s["user_instructions"].get(name, ""))
                if updated is not None:
                    if updated.strip():
                        s["user_instructions"][name] = updated
                    else:
                        s["user_instructions"].pop(name, None)
                    cfg.save(s)
            elif selection == 5:
                if ask("Введите СБРОС для восстановления", "") == "СБРОС":
                    s["prompts"].pop(name, None)
                    s["user_instructions"].pop(name, None)
                    cfg.save(s)
            else:
                break


def advanced_menu(s: dict) -> None:
    while True:
        pick = choose("Расширенные настройки", [
            f"Температура: {s['temperature']}",
            f"Top-p: {s['top_p']}",
            f"Reasoning: {s['reasoning']}",
            f"Лимит ответа: {'не передавать' if s['uncapped'] else s['max_tokens']}",
            f"Тайм-аут API: {s['timeout']} секунд",
            f"Повторных попыток: {s['retries']}",
            "Дополнительные параметры OpenRouter (JSON)",
            "Статья и конвейер",
            "Назад"])
        try:
            if pick == 1:
                s["temperature"] = number("Температура", s["temperature"], float, 0, 2)
            elif pick == 2:
                s["top_p"] = number("Top-p", s["top_p"], float, 0, 1)
            elif pick == 3:
                index = choose("Уровень рассуждений", [
                    "auto — не передавать", "none", "minimal", "low", "medium", "high", "xhigh"])
                if index:
                    s["reasoning"] = ["auto", "none", "minimal", "low", "medium", "high", "xhigh"][index - 1]
            elif pick == 4:
                s["uncapped"] = not s["uncapped"]
                if not s["uncapped"]:
                    s["max_tokens"] = number("Лимит выходных токенов", s["max_tokens"], int, 16, 200000)
            elif pick == 5:
                s["timeout"] = number("Тайм-аут", s["timeout"], int, 10, 3600)
            elif pick == 6:
                s["retries"] = number("Попыток всего", s["retries"], int, 1, 10)
            elif pick == 7:
                custom = editor("Дополнительные параметры OpenRouter",
                                json.dumps(s["extra"], ensure_ascii=False, indent=2))
                if custom is not None:
                    parsed = json.loads(custom)
                    if not isinstance(parsed, dict):
                        raise ValueError("Требуется JSON-объект")
                    draft = dict(s, extra=parsed)
                    # Validate config without requiring API key.
                    forbidden = {"model", "messages", "tools", "plugins", "stream",
                                 "temperature", "max_tokens", "top_p"}
                    if forbidden.intersection(parsed):
                        raise ValueError("Эти поля управляются отдельными настройками")
                    s["extra"] = parsed
            elif pick == 8:
                pipeline_menu(s)
            else:
                return
            cfg.save(s)
        except (ValueError, json.JSONDecodeError) as err:
            say(f"Ошибка: {err}")


def folder_size(directory: Path) -> int:
    if directory.is_file():
        return directory.stat().st_size
    total = 0
    if directory.exists():
        for file in directory.rglob("*"):
            try:
                if file.is_file() and not file.is_symlink():
                    total += file.stat().st_size
            except OSError:
                continue
    return total


def size_label(n: int) -> str:
    return f"{n / 1048576:.1f} МБ"


def cleanup_menu() -> None:
    cfg.RUNS.mkdir(parents=True, exist_ok=True)
    while True:
        dirs = sorted((d for d in cfg.RUNS.iterdir() if d.is_dir()), reverse=True)
        cache_size = folder_size(cfg.CACHE)
        runs_size = folder_size(cfg.RUNS)
        say(f"\nИстория: {len(dirs)} запусков, {size_label(runs_size)}")
        say(f"Кэш: {size_label(cache_size)}. Копии в Android загрузках НЕ удаляются.")
        pick = choose("Очистка памяти", [
            "Очистить временный кэш",
            "Удалить старые запуски, оставить последние N",
            "Удалить все сохранённые запуски",
            "Назад"])
        if pick == 1:
            if ask("Для очистки кэша введи ДА") == "ДА":
                shutil.rmtree(cfg.CACHE, ignore_errors=True)
                say("Кэш очищен.")
        elif pick in (2, 3):
            keep = 0 if pick == 3 else number("Сколько последних запусков оставить", 5, int, 0, 100000)
            victims = dirs[keep:]
            bytes_to_remove = sum(folder_size(x) for x in victims)
            say(f"Будет удалено папок: {len(victims)}; размер: {size_label(bytes_to_remove)}.")
            if victims and ask("Для удаления введи УДАЛИТЬ") == "УДАЛИТЬ":
                for directory in victims:
                    if directory.parent == cfg.RUNS and not directory.is_symlink():
                        shutil.rmtree(directory)
                say("Старые результаты удалены из Linux.")
        else:
            return
