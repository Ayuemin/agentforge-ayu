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
from datetime import datetime
from pathlib import Path

import httpx
from rich.console import Console
from rich.panel import Panel

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
        if p.get("editorial_profile") == "dzen":
            say(f"\nПлощадка: Дзен · цель: {p['target_chars']} знаков "
                f"({p['min_chars']}–{p['max_chars']}) · заголовок до {p['title_max_chars']}")
        else:
            say(f"\nЯзык: {p['language']} · слов: {p['words']}")
        say(f"Проходов: до {p['passes']} · таблицы: "
            f"{'да' if p.get('allow_tables', False) else 'нет'}")
        pick = choose("Статья и конвейер", [
            "Целевой объём статьи (слов)", "Максимум проходов редактора",
            "Порог качества (0.0—1.0)", "Язык",
            "Таблицы в статье: включить / выключить",
            "Редакционный профиль: Дзен / общий",
            "Целевой объём Дзена (знаки)",
            "Минимум знаков Дзена",
            "Максимум знаков Дзена",
            "Предел заголовка (символы)",
            "Назад"])
        if not pick or pick == 11:
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
            elif pick == 5:
                p["allow_tables"] = not p.get("allow_tables", False)
                say("Таблицы разрешены." if p["allow_tables"]
                    else "Таблицы запрещены: данные будут представлены текстом или списками.")
            elif pick == 6:
                p["editorial_profile"] = (
                    "general" if p.get("editorial_profile") == "dzen" else "dzen"
                )
            elif pick == 7:
                p["target_chars"] = number(
                    "Желаемый объём (знаки)", p["target_chars"], int, 1000, 20000
                )
            elif pick == 8:
                p["min_chars"] = number("Минимум (знаки)", p["min_chars"], int, 500, 20000)
            elif pick == 9:
                p["max_chars"] = number("Максимум (знаки)", p["max_chars"], int, 500, 20000)
            elif pick == 10:
                p["title_max_chars"] = number(
                    "Заголовок максимум", p["title_max_chars"], int, 20, 300
                )
            if not p["min_chars"] <= p["target_chars"] <= p["max_chars"]:
                say("Ошибка: должно быть минимум ≤ цель ≤ максимум.")
                continue
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
    """General storage maintenance; Android Downloads are never touched."""
    cfg.RUNS.mkdir(parents=True, exist_ok=True)
    while True:
        dirs = sorted((d for d in cfg.RUNS.iterdir() if d.is_dir()), reverse=True)
        cache_size = folder_size(cfg.CACHE)
        runs_size = folder_size(cfg.RUNS)
        say(f"\nИстория: {len(dirs)} запусков, {size_label(runs_size)}")
        say(f"Кэш: {size_label(cache_size)}. Копии в Android загрузках НЕ удаляются.")
        pick = choose("Хранилище", [
            "Очистить временный кэш",
            "Освободить место: оставить последние N запусков",
            "Удалить всю историю запусков",
            "Назад"])
        if pick == 1:
            if ask("Для очистки кэша введи ДА") == "ДА":
                shutil.rmtree(cfg.CACHE, ignore_errors=True)
                say("Кэш очищен.")
        elif pick in (2, 3):
            try:
                keep = 0 if pick == 3 else number(
                    "Сколько последних запусков оставить", 5, int, 0, 100000
                )
            except ValueError as error:
                say(f"Ошибка: {error}")
                continue
            victims = dirs[keep:]
            bytes_to_remove = sum(folder_size(directory) for directory in victims)
            say(f"Будет удалено папок: {len(victims)}; размер: {size_label(bytes_to_remove)}.")
            if victims and ask("Для удаления введи УДАЛИТЬ") == "УДАЛИТЬ":
                for directory in victims:
                    if directory.parent == cfg.RUNS and not directory.is_symlink():
                        shutil.rmtree(directory)
                say("Выбранные результаты удалены из Linux.")
        else:
            return


def clean_article(value: str) -> str:
    """Keep only article text, never publisher JSON, scores or editor comments."""
    value = re.sub(r"<!--[\s\S]*?-->", "", value)
    value = re.sub(r"\A---\n[\s\S]*?\n---\n", "", value)
    return value.strip() + "\n"


def download_article(article: Path, topic: str) -> Path | None:
    """Copy without modifying the Linux original."""
    name = re.sub(r"[^\wа-яА-Я-]+", "_", topic, flags=re.UNICODE).strip("_")[:48]
    name = name or "statya"
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    for folder in (
        Path("/sdcard/Download"),
        Path("/storage/emulated/0/Download"),
        Path("/data/data/com.termux/files/home/storage/downloads"),
    ):
        if folder.is_dir():
            dest = folder / (f"AgentForge_{stamp}_{name}.md")
            try:
                shutil.copyfile(article, dest)
                return dest
            except OSError:
                continue
    return None


class StageDisplay(logging.Handler):
    stages = {
        "Research": "Исследование",
        "Outline": "План статьи",
        "Writer": "Написание",
        "SEO": "SEO-анализ",
        "Editor": "Редактура",
        "Quality": "Контроль качества",
        "Translation": "Перевод",
        "Publisher": "Сохранение",
    }

    def emit(self, record: logging.LogRecord) -> None:
        message = record.getMessage()
        if "[Pipeline] Step" in message:
            for stage, name in self.stages.items():
                if f": {stage}" in message:
                    say("➜ " + name + (" — повторный проход" if "iteration 2" in message
                                             or "iteration 3" in message else ""))
                    break


def run_article(s: dict) -> None:
    from .pipeline.orchestrator import PipelineOrchestrator

    topic = topic_input()
    if not topic:
        say("Пустое задание. Запуск отменён.")
        return
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    folder = cfg.RUNS / stamp
    effective = [s["models"].get(n, s["model"]) if s["mode"] == "per_agent"
                 else s["model"] for n in cfg.AGENTS]
    say("\nПРОВЕРКА ПЕРЕД ЗАПУСКОМ")
    say(f"Задание: {topic[:550]}")
    if len(set(effective)) == 1:
        say(f"Модель на всех этапах: {effective[0]}")
    else:
        for name, model in zip(cfg.LABELS, effective):
            say(f"  {name}: {model}")
    search = s["search"]
    say(f"Поиск: до {search['calls']} запросов" if search["enabled"] else "Поиск: выключен")
    say(f"Язык: {s['pipeline']['language']} · до {s['pipeline']['passes']} проходов редактора")
    if s["pipeline"].get("editorial_profile") == "dzen":
        p = s["pipeline"]
        say(f"Дзен: {p['min_chars']}–{p['max_chars']} знаков; заголовок до "
            f"{p['title_max_chars']} символов")
    say("API и запасной платный поиск могут списывать средства OpenRouter.")
    if ask("Начать? (да/нет)", "нет").lower() not in {"да", "д", "yes", "y"}:
        say("Отменено. Платных запросов не было.")
        return
    config = cfg.make_config(s, folder)
    folder.mkdir(parents=True, exist_ok=False)
    (folder / "settings.json").write_text(
        json.dumps({k: v for k, v in s.items() if k != "api_key"},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    (folder / "topic.txt").write_text(topic, encoding="utf-8")
    say("\nИщу источники…")
    report = gather(topic, s, config.llm.api_key, announce=say)
    (folder / "sources.json").write_text(report_to_json(report), encoding="utf-8")
    listing = []
    for i, source in enumerate(report.sources, 1):
        listing.append(f"{i}. {source['title']}\n{source['url']}\n{source['excerpt']}\n")
    (folder / "sources.md").write_text(
        "# Собранные материалы\n\n" + "\n".join(listing), encoding="utf-8")
    say(f"Источников: {len(report.sources)}. Платных поисковых запросов: {report.paid_calls}")
    if report.problems:
        say("Предупреждения поиска: " + "; ".join(report.problems[:4]))
    if search["enabled"] and not report.sources:
        if ask("Источников нет. Писать без них? (да/нет)", "нет").lower() != "да":
            say("Остановлено до запуска агентов.")
            return
    say("\nЗапущен конвейер агентов. Это может занять несколько минут.")
    handler = StageDisplay()
    logger = logging.getLogger("contentforge.pipeline.orchestrator")
    previous_level = logger.level
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    try:
        result = asyncio.run(PipelineOrchestrator(config).run(
            topic=topic, research_context=report.text))
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous_level)

    if result.status == "needs_review":
        say("Статья пока НЕ ГОТОВА для Дзена: после редакторских проходов "
            "остались замечания по объёму или качеству.")
        if result.editorial_audit.get("issues"):
            for issue in result.editorial_audit["issues"]:
                say("• " + issue)
        say("Черновик и отчёты сохранены в Linux, в Android Загрузки он не копируется.")
        say(str(folder))
        return
    if not result.ok:
        say("Конвейер завершился с ошибкой. Уже созданные файлы сохранены:")
        say(str(folder))
        return

    from .article_format import format_article

    article_file = folder / "СТАТЬЯ.md"
    article_text = clean_article(result.article)
    article_text, remaining_tables = format_article(
        article_text, allow_tables=s["pipeline"].get("allow_tables", False)
    )
    article_file.write_text(article_text, encoding="utf-8")
    if remaining_tables:
        say("Внимание: в статье осталась нестандартная таблица. "
            "Она сохранена без удаления данных, проверь файл перед публикацией.")
    say("\nСТАТЬЯ ГОТОВА")
    say(f"Linux: {article_file}")
    if s.get("download", True):
        exported = download_article(article_file, topic)
        if exported:
            say(f"Android Загрузки: {exported}")
        else:
            say("Не удалось открыть папку Android. В Termux выполни termux-setup-storage.")
    say(f"Слов: {len(result.article.split())}, токенов: {result.total_tokens:,}")
    say("Стоимость в долларах смотри в истории OpenRouter (счётчик показывает токены).")


def recent_menu(s: dict) -> None:
    cfg.RUNS.mkdir(parents=True, exist_ok=True)
    dirs = sorted((p for p in cfg.RUNS.iterdir() if p.is_dir()), reverse=True)[:30]
    if not dirs:
        say("История пока пуста.")
        return
    names = []
    for path in dirs:
        try:
            topic = (path / "topic.txt").read_text(encoding="utf-8").strip()
        except OSError:
            topic = "неизвестное задание"
        names.append(f"{path.name[:15]} · {topic[:45]}")
    choice = choose("Последние запуски", names + ["Назад"])
    if not choice or choice > len(dirs):
        return
    selected = dirs[choice - 1]
    article = selected / "СТАТЬЯ.md"
    if not article.exists():
        article = next(iter(sorted(selected.glob("*_article.md"))), None)
    if article is None or not article.is_file():
        say("Итоговая статья отсутствует. Возможно, запуск прервался.")
        say("Файлы: " + ", ".join(x.name for x in selected.iterdir()))
        return
    option = choose("Готовая статья", ["Прочитать начало", "Повторно в Загрузки", "Показать путь"])
    if option == 1:
        console.print(Panel(article.read_text(encoding="utf-8")[:7500], title=article.name))
    elif option == 2:
        topic = (selected / "topic.txt").read_text(encoding="utf-8")
        result = download_article(article, topic)
        say(f"Экспорт: {result}" if result else "Папка загрузок недоступна.")
    elif option == 3:
        say(str(article))


def system_menu(s: dict) -> None:
    while True:
        pick = choose("Система", [
            "Добавить или заменить API-ключ OpenRouter",
            "Проверить ключ (без генерации)",
            "Копировать настройки в файл JSON",
            "Включить / выключить копию статьи в Загрузках",
            "Хранилище (кэш и история)",
            "Вернуть настройки по умолчанию",
            "Назад"])
        if pick == 1:
            try:
                key = getpass.getpass("Вставь ключ OpenRouter (ввод скрыт): ")
                if key:
                    cfg.key_save(key)
                    say("Ключ сохранён в приватной папке Linux (chmod 600).")
                    if "OPENROUTER_API_KEY" in __import__("os").environ:
                        say("Внимание: переменная окружения OPENROUTER_API_KEY имеет приоритет.")
            except ValueError as error:
                say(str(error))
        elif pick == 2:
            key = cfg.key_get()
            if not key:
                say("Ключ не задан.")
                continue
            try:
                r = httpx.get("https://openrouter.ai/api/v1/auth/key",
                              headers={"Authorization": "Bearer " + key}, timeout=20)
                say("Авторизация успешна." if r.status_code == 200 else
                    f"Проверка не пройдена (HTTP {r.status_code}).")
            except httpx.HTTPError as error:
                say("Ошибка сети: " + type(error).__name__)
        elif pick == 3:
            destination = cfg.HOME / "export-settings.json"
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")
            say(f"Экспортировано без ключа: {destination}")
        elif pick == 4:
            s["download"] = not s["download"]
            cfg.save(s)
            say(f"Копия в Загрузки: {'да' if s['download'] else 'нет'}")
        elif pick == 5:
            cleanup_menu()
        elif pick == 6:
            if ask("Для сброса настроек введи СБРОС") == "СБРОС":
                s.clear()
                s.update(cfg.defaults())
                cfg.save(s)
                say("Настройки сброшены. Статьи и API-ключ не затронуты.")
        else:
            return


def main() -> None:
    try:
        s = cfg.load()
    except (ValueError, OSError) as error:
        say(str(error))
        return
    while True:
        try:
            title = ("[bold cyan]AgentForge — управление статьями[/]\n"
                     f"Модель: [green]{s['model']}[/]\n"
                     f"Язык: {s['pipeline']['language']} | "
                     f"поиск: {'вкл' if s['search']['enabled'] else 'выкл'} "
                     f"({s['search']['calls']} запроса) | "
                     f"редактура: до {s['pipeline']['passes']}")
            console.print(Panel(title, border_style="cyan"))
            index = choose("Главное меню", [
                "Написать статью", "Выбрать модели и агентов",
                "Интернет-поиск", "Промпты", "Расширенные настройки",
                "Готовые статьи", "Система, API и очистка", "Выход"])
            if index == 1:
                run_article(s)
            elif index == 2:
                model_menu(s)
            elif index == 3:
                search_menu(s)
            elif index == 4:
                prompt_menu(s)
            elif index == 5:
                advanced_menu(s)
            elif index == 6:
                recent_menu(s)
            elif index == 7:
                system_menu(s)
            else:
                say("Завершено.")
                return
        except (KeyboardInterrupt, EOFError):
            say("\nВозврат в меню.")
        except (ValueError, OSError, httpx.HTTPError) as error:
            say(f"Ошибка: {error}")


if __name__ == "__main__":
    main()
