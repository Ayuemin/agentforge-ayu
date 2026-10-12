# AgentForge — статьи через Termux (Android)

Русскоязычное меню для исходного 8-агентного проекта ContentForge. **Запуск одной командой `forge` из Termux:** тема → исследование → план → статья → редактура → файл в «Загрузках» Android. Интерфейс работает внутри Ubuntu/PRoot; **root-права Android не требуются**.

> **Статус:** экспериментальная версия в ветке `work/termux-terminal-app`. Автотесты не заменяют проверку реального запуска на конкретном телефоне. Основной `main` не изменён. Не трать кредиты на первый запуск, пока не проверишь модель и ключ.

## Экспериментальная редакция для Дзена

Ветка `work/dzen-editorial-v1` развивает исходный восьмиагентный конвейер **без замены его исходных промптов и JSON-схем**. Это отдельная экспериментальная ветка, не стабильный `main` и не `work/termux-terminal-app`.

Для Дзена установлен ориентир **4000–8000 знаков с пробелами**, цель **6000**, заголовок **до 147 символов**. При несоответствии статья получает статус «Требуется редактура», а не обрезается программой.

**Новая возможность: подключение полного навыка `nikitina-text`.** Полные файлы остаются только в приватной папке Ubuntu; ни Python, ни модель не создают для них сокращённую версию. Навык выключен, пока не установлен пользователем. Writer и Editor при включении получают все семь исходных справочников на каждый вызов, а Outline/Quality — выбранные целые файлы. Меню: **`forge` → «Система» → «Методика Никитиной»**. Здесь можно установить архив ZIP из Android «Загрузок», включить, выключить или заменить архив без изменения кода.

Восстановленный полный ZIP поставляется **лично пользователю**, а не размещается в публичном репозитории. Сохрани `nikitina-text-full-private.zip` в Android «Загрузки» и выбери «Установить / заменить навык из ZIP». Если пользовательского архива нет, AgentForge продолжит работать по прежним инструкциям.

Подробнее: [адаптация для Дзена и безопасность исходного конвейера](docs/DZEN_ADAPTATION_RU.md).

## Возможности

- Русское меню с цифрами: «Написать статью», «Модели», «Интернет-поиск», «Промпты», «Расширенные настройки», «Готовые статьи», «Система».
- **MiMo V2.5 Pro через OpenRouter** используется по умолчанию на всех этапах. Можно выбрать любую модель OpenRouter, либо свою модель для каждого агента.
- Статья **сразу на русском**, ориентир **1500 слов**, температура 0,7, top-p 0,9, SEO включён.
- **Таблицы в статье по умолчанию выключены.** Для Writer и Editor добавляется правило оформлять сравнения абзацами или списками, без правки исходных промптов. Обычные Markdown-таблицы при экспорте превращаются в списки с сохранением значений. Для нестандартных или HTML-таблиц показывается предупреждение: данные не удаляются автоматически. Переключатель — **«Расширенные настройки → Статья и конвейер → Таблицы в статье»**.
- **До трёх** проходов «Редактор → Проверка качества» с порогом 80%; если оценка достигнута раньше, конвейер остановит редактуру досрочно. Это изначальная логика проекта.
- Ограничение `max_tokens` приложением **не передаётся** (ограничения провайдера остаются). Reasoning и дополнительные параметры доступны в расширенных настройках, но зависят от выбранной модели.
- До **3 поисковых запросов** по умолчанию. Сначала бесплатный Bing RSS, при отсутствии результатов — попытка поиска OpenRouter; для ссылок GitHub дополнительно читаются README и последний релиз. **Поиск OpenRouter может быть платным**, а бесплатная поисковая лента — недоступной. Факты, пришедшие от модели, не равны проверенным источникам.
- Готовая статья `СТАТЬЯ.md` сохраняется в Linux и **копируется отдельно** в папку **«Загрузки» Android**. В файле нет технических логов и JSON. Данные исследования и промежуточные версии хранятся только в Linux.
- Обслуживание файлов спрятано внутри **«Система → Хранилище»**: очистка временного кэша и управление числом сохранённых запусков. Копии в Android «Загрузках» при очистке не затрагиваются.
- Просмотр промптов, свои системные инструкции и дополнительные инструкции к заданиям. **Исходный шаблон задания пока доступен только для просмотра**, а не для прямого редактирования; это ещё не полноценный редактор обоих типов промптов.

## Если AgentForge уже установлен (без переустановки Termux)

**Важно:** установка команды `forge` создаёт только ярлык запуска. Она **не скачивает новое меню в Ubuntu**, **не переключает Git-ветку** и не обновляет Python-пакет. Если ярлык установлен раньше обновления проекта, получится ошибка `No module named contentforge.terminal_app`.

Обновляй в следующем порядке: **код AgentForge → Python-пакет → проверка меню → команда `forge`**.

**1. В обычном Termux** (`~ $`) войди в Ubuntu:

```sh
proot-distro login ubuntu
```

**2. В Ubuntu** (`root@localhost`) проверь рабочее дерево и ветку:

```sh
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
hash -r
cd /root/agentforge-ayu
git status --short
git branch --show-current
```

Если `git status --short` вывел изменения, **остановись и проверь их**: не переключай ветку, чтобы не затереть собственные правки. Если вывод пустой, продолжай:

```sh
git fetch origin work/termux-terminal-app:refs/remotes/origin/work/termux-terminal-app
git switch --track origin/work/termux-terminal-app
```

Команда `git switch --track` нужна **только при первом переходе** со старой ветки. Если ответ `fatal: a branch named 'work/termux-terminal-app' already exists`, вместо неё выполни `git switch work/termux-terminal-app`. Для следующих обновлений уже этой ветки достаточно `git pull --ff-only`.

**3. В Ubuntu** установи обновлённый пакет и проверь наличие меню:

```sh
apt update
apt install -y nano
. .venv/bin/activate
python -m pip install --only-binary=:all: -e .
python -c "import contentforge.terminal_app; print('AgentForge OK')"
```

Ожидаемый результат проверки — `AgentForge OK`. Если получена ошибка, **не переходи к запуску платной генерации**: сначала разберись с обновлением.

Выйди из Ubuntu (после активации venv команда `exit` завершает текущую оболочку Ubuntu):

```sh
exit
```

**4. Снова в обычном Termux** установи или переустанови короткую команду:

```sh
curl -fL https://raw.githubusercontent.com/Ayuemin/agentforge-ayu/work/termux-terminal-app/scripts/install-forge-termux.sh -o "$HOME/install-forge-termux.sh"
sh "$HOME/install-forge-termux.sh"
forge
```

Теперь в дальнейшем используй одну команду — `forge`. Если API-ключ раньше был задан только временной командой `export OPENROUTER_API_KEY`, открой «Система» и сохрани его для следующих запусков.

---

## Установка с нуля (чистый Termux)

Установи актуальный **Termux из F-Droid или официальных релизов GitHub**. Понадобятся интернет, свободное место для Ubuntu и разрешение на доступ к памяти телефона. Не смешивай APK Termux и его плагинов из разных источников.

**Шаг 1. В обычном Termux** (там, где приглашение `$`, а не `root@localhost`):

```sh
pkg update -y && pkg upgrade -y
pkg install -y proot-distro curl git
termux-setup-storage
proot-distro install ubuntu
proot-distro login ubuntu
```

При `termux-setup-storage` разреши доступ к файлам Android. Последняя команда откроет Ubuntu.

**Шаг 2. В Ubuntu** (приглашение вида `root@localhost:~#`). Важно: исправляем PATH, чтобы использовался системный Python Ubuntu, а не Python Termux.

```sh
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
hash -r
apt update
apt install -y git python3 python3-venv python3-pip nano ca-certificates
cd /root
git clone --branch work/termux-terminal-app --single-branch https://github.com/Ayuemin/agentforge-ayu.git agentforge-ayu
cd /root/agentforge-ayu
/usr/bin/python3 -m venv .venv
. .venv/bin/activate
python -m pip install --only-binary=:all: -e .
python -m contentforge.terminal_app
```

Откроется русское меню. Для начала **не запускай генерацию**: зайди в «Система → Добавить или заменить API-ключ OpenRouter», вставь ключ (он вводится скрыто). Модель и число поисков уже выбраны по умолчанию. Затем выйди из меню и **из Ubuntu**:

```sh
exit
```

Если ты сначала открыл меню с активной средой, после выхода из меню и `exit` должен вернуться в обычный Termux. Если остаёшься в Ubuntu, введи `exit` ещё раз.

**Шаг 3. Снова в обычном Termux:** установи короткую команду `forge`.

```sh
curl -fL https://raw.githubusercontent.com/Ayuemin/agentforge-ayu/work/termux-terminal-app/scripts/install-forge-termux.sh -o "$HOME/install-forge-termux.sh"
sh "$HOME/install-forge-termux.sh"
forge
```

Готово. **В дальнейшем открывай Termux и просто вводи `forge`.** Ubuntu, правильный Python и виртуальная среда будут запущены автоматически. Утилита рассчитана на обычный Termux с пакетом приложения `com.termux`.

**Настройка таблиц:** в меню `forge` выбери «Расширенные настройки», затем «Статья и конвейер», затем «Таблицы в статье». По умолчанию стоит «нет». Для сравнения со старой версией можно снова разрешить таблицы.

### Как написать первую статью

1. Введи `forge` (позднее только эту команду).
2. Выбери **1. Написать статью**.
3. Введи тему или вставь ссылку, например `https://github.com/mokshablr/gander`. Для большого задания введи `/много`: откроется редактор nano; сохранение в nano — **Ctrl+O, Enter**, выход — **Ctrl+X**.
4. Подтверди запуск словом **да**. До подтверждения платных вызовов модели нет.
5. После успешной генерации открой **«Файлы» → «Загрузки»**. Там будет файл `AgentForge_...md` только со статьёй.

Подробности, отчёты и промежуточные тексты остаются в Ubuntu:

```text
/root/agentforge-ayu/output/runs/<дата-и-время>/
    СТАТЬЯ.md
    sources.md
    sources.json
    01_research.json
    02_outline.json
    03_writer.md
    04_seo.json
    05_editor_1.md       (и другие проходы, если были)
    06_quality_1.json    (и другие проходы, если были)
    08_publisher.json
    metrics/
```

**Примечание:** переводчик — восьмой агент — в русскоязычном профиле отключён: статья сразу пишется по-русски, без дополнительного перевода.

### Обновление установленной версии

Из обычного Termux можно снова войти в Ubuntu:

```sh
proot-distro login ubuntu
```

Затем в Ubuntu:

```sh
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
cd /root/agentforge-ayu
git status --short
git pull --ff-only
. .venv/bin/activate
python -m pip install --only-binary=:all: -e .
exit
```

Если `git status --short` выводит локальные изменения, **не делай `git pull` до их проверки**. Настройки интерфейса и API-ключ сохраняются отдельно от репозитория: в `/root/.config/agentforge/`.

### Частые проблемы

| Проблема | Что делать |
| --- | --- |
| `forge: command not found` | Выполни шаг 3 именно **в обычном Termux**, не в Ubuntu |
| `No module named contentforge.terminal_app` | Команда `forge` установлена, но в Ubuntu осталась старая ветка. Выполни весь раздел **«Если AgentForge уже установлен»**: переключение ветки, `pip install` и проверку импорта. Одной переустановки ярлыка недостаточно |
| `proot-distro: command not found` | В обычном Termux: `pkg install proot-distro` |
| Python не может импортировать `_posixsubprocess` | В Ubuntu восстанови `PATH` как в шаге 2, используй `/usr/bin/python3` |
| Нет статей в Android «Загрузках» | В обычном Termux выполни `termux-setup-storage`, разреши доступ; убедись, что доступен `/sdcard/Download` |
| OpenRouter возвращает 401 | Проверь API-ключ через «Система → Проверить ключ» |
| Ошибка недоступной модели | Выбери другое ID в «Модели»; названия и наличие моделей OpenRouter могут изменяться |
| Поиск не дал результатов | Проверь интернет, попробуй другой поисковый движок, но учти стоимость OpenRouter |
| Нехватка места | В приложении открой «Система → Хранилище»; это не удалит Android-копии статей |

### Что ещё ограничено

Текущий поиск не является полноценным браузером и не гарантирует прочтение всех найденных страниц: обычные результаты Bing RSS в основном содержат названия, URL и выдержки. Источник может быть устаревшим или неполным. Инструмент OpenRouter web-plugin зависит от актуальной поддержки сервиса. Стоимость в долларах пока нужно сверять с историей OpenRouter; внутренний отчёт надёжно показывает токены, а не счёт.

Для проверки кода и истории изменений см. [рабочий PR](https://github.com/Ayuemin/agentforge-ayu/pull/2). Старый командный интерфейс `contentforge --config ... generate` сохранён.

---

## Оригинальная документация ContentForge

# ContentForge

> **8-Agent AI Content Pipeline for any OpenAI-compatible LLM**
>
> From topic to published article in minutes — research, write, optimize, translate, and publish with 8 specialized AI agents orchestrated through a single pipeline.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Tests: 112](https://img.shields.io/badge/tests-112-brightgreen.svg)](tests/)
[![LOC: 2,900+](https://img.shields.io/badge/LOC-2%2C900%2B-orange.svg)](src/)

Works with **OpenAI, OpenRouter, Ollama, llama.cpp, Xiaomi MiMo**, or any endpoint that speaks the OpenAI `/chat/completions` protocol. Pick a provider with one config line — no code changes.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    ContentForge Pipeline                       │
│              Any OpenAI-compatible LLM backend                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐    │
│  │ 1.Research│──▶│2.Outline │──▶│ 3.Writer │──▶│  4.SEO   │    │
│  │  Agent   │   │  Agent   │   │  Agent   │   │  Agent   │    │
│  └──────────┘   └──────────┘   └──────────┘   └──────────┘    │
│                                                     │          │
│                                                     ▼          │
│  ┌──────────┐   ┌──────────┐        ┌──────────────────┐       │
│  │8.Publisher│◀──│7.Translate│◀───────│ 5.Editor ──▶ 6.Quality │
│  │  Agent   │   │  Agent   │        │  (iterate if < threshold)│
│  └──────────┘   └──────────┘        └──────────────────┘       │
│       │                                                        │
│       ▼                                                        │
│  ┌──────────────────────────────────────────────────────┐      │
│  │              Token Tracker & Metrics                  │      │
│  │  Per-agent consumption · Cache hit rate · Latency    │      │
│  └──────────────────────────────────────────────────────┘      │
│                                                                 │
│  Protocol: OpenAI-compatible /chat/completions                 │
│  Auth: bearer token or api-key header (per provider)           │
│  Streaming SSE · optional reasoning_content support            │
└─────────────────────────────────────────────────────────────────┘
```

## 8 Specialized Agents

| # | Agent | Role | Avg Tokens/Call |
|---|-------|------|-----------------|
| 1 | **Research** | Gathers facts, statistics, expert quotes | ~800 |
| 2 | **Outline** | Structures content with word allocation | ~600 |
| 3 | **Writer** | Generates full article draft | ~2,000 |
| 4 | **SEO** | Analyzes keyword density, meta tags, CTR | ~1,000 |
| 5 | **Editor** | Refines clarity, grammar, tone | ~2,000 |
| 6 | **Quality** | Fact-checks, scores 8 quality dimensions | ~1,000 |
| 7 | **Translator** | Multi-language adaptation (zh/ms/ja/ko/id/th/vi/ar) | ~1,200 |
| 8 | **Publisher** | Formats for markdown/HTML/WordPress/social | ~800 |

**Total per pipeline run: ~9,400 tokens** (single language)

## Supported Providers

ContentForge talks to any OpenAI-compatible `/chat/completions` endpoint. Built-in presets:

| Provider | `provider=` | Default model | Auth | Env vars |
|----------|-------------|---------------|------|----------|
| OpenAI | `openai` | `gpt-4o-mini` | Bearer | `OPENAI_API_KEY`, `OPENAI_BASE_URL` |
| OpenRouter | `openrouter` | `openai/gpt-4o-mini` | Bearer | `OPENROUTER_API_KEY` |
| Ollama (local) | `ollama` | `llama3.1` | Bearer | `OLLAMA_BASE_URL` |
| Groq | `groq` | `llama-3.3-70b-versatile` | Bearer | `GROQ_API_KEY` |
| DeepSeek | `deepseek` | `deepseek-chat` | Bearer | `DEEPSEEK_API_KEY` |
| Together | `together` | `meta-llama/Llama-3.3-70B-Instruct-Turbo` | Bearer | `TOGETHER_API_KEY` |
| Mistral | `mistral` | `mistral-small-latest` | Bearer | `MISTRAL_API_KEY` |
| Xiaomi MiMo | `mimo` | `mimo-v2.5-pro` | api-key | `MIMO_API_KEY` |

Point `base_url` at any other compatible endpoint (llama.cpp, vLLM, LM Studio, a local proxy) and it just works. The pipeline benefits from models that expose a `reasoning_content` field (used by the Quality Agent's 8-dimension scoring) and strong multilingual output (used by the Translator Agent), but neither is required.

## Quick Start

```bash
# Install
pip install -e ".[dev]"

# Pick any provider — set its API key (OpenAI shown here)
export OPENAI_API_KEY="sk-..."

# Generate content (uses the default provider unless overridden in config)
contentforge generate "AI in Healthcare" --words 2000 --output ./output

# With translation
contentforge generate "AI Ethics" --translate zh --translate ms

# View token consumption
contentforge report output/metrics/*.json

# List agents
contentforge agents
```

## Usage as Library

```python
import asyncio
from contentforge.core.config import ContentForgeConfig
from contentforge.pipeline.orchestrator import PipelineOrchestrator

async def main():
    config = ContentForgeConfig.from_env()
    config.pipeline.target_word_count = 3000
    config.pipeline.enable_translation = True
    config.pipeline.target_languages = ["zh", "ms"]

    orchestrator = PipelineOrchestrator(config)
    result = await orchestrator.run("The Future of AI Agents")

    print(f"Article: {len(result.article.split())} words")
    print(f"Tokens: {result.total_tokens:,}")
    print(f"Duration: {result.pipeline_duration_s:.1f}s")
    print(f"Translations: {list(result.translations.keys())}")

    # Token consumption report
    print(orchestrator.tracker.report())

asyncio.run(main())
```

## Token Consumption

Average pipeline run consumes **~9,400 tokens** across 8 agents:

```
============================================================
  ContentForge Token Consumption Report
  Run: 20260526_143022
============================================================

  Pipeline Duration: 12.3s
  Total Tokens: 9,420
    Prompt: 4,800 | Completion: 4,620
    Cache Hit: 1,200 (25.0%)
  Total API Calls: 8

  Agent                Calls     Tokens    Avg/call   Latency
  ----------------------------------------------------------
  writer                    1      2,100      2,100     2500ms
  editor                    1      2,050      2,050     2200ms
  translator                1      1,200      1,200     1800ms
  quality                   1      1,000      1,000     1500ms
  seo                       1        980        980     1200ms
  research                  1        820        820     1100ms
  publisher                 1        780        780      900ms
  outline                   1        590        590      800ms
  ----------------------------------------------------------
  TOTAL                     8      9,520
============================================================
```

Daily estimate: **50-100 pipeline runs** = ~500K–1M tokens/day

## Configuration

```yaml
# contentforge.yaml
llm:
  provider: openai          # openai | openrouter | ollama | mimo
  api_key: ${OPENAI_API_KEY}
  # base_url and model default from the provider preset; override if needed
  # base_url: https://api.openai.com/v1
  # model: gpt-4o-mini
  max_tokens: 4096
  temperature: 0.7
  max_retries: 3

pipeline:
  target_word_count: 2000
  language: en
  seo_enabled: true
  quality_threshold: 0.8
  max_iterations: 3
  enable_translation: false
  target_languages: [zh, ms]
  publish_targets: [markdown, html]

agents:
  - name: writer
    temperature_override: 0.8
    max_tokens_override: 8192
  - name: quality
    system_prompt_override: "Custom quality rules..."
```

## Testing

```bash
# Run all tests
pytest

# With coverage
pytest --cov=contentforge --cov-report=term-missing

# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration

# Verbose output
pytest -v
```

**112 tests** covering:
- Configuration management (17 tests)
- Multi-backend LLM config: presets, auth styles, env resolution (16 tests)
- Token tracking & reporting (14 tests)
- Text utilities (12 tests)
- Export utilities (4 tests)
- Agent base class & all 8 agents (34 tests)
- Pipeline orchestration (8 tests)
- Error handling & edge cases (7 tests)

## Project Structure

```
contentforge/
├── src/contentforge/
│   ├── __init__.py
│   ├── cli.py                    # Click CLI with Rich output
│   ├── agents/
│   │   ├── __init__.py           # Agent registry
│   │   ├── base.py               # BaseAgent abstract class
│   │   ├── research.py           # Agent 1: Research
│   │   ├── outline.py            # Agent 2: Outline
│   │   ├── writer.py             # Agent 3: Writer
│   │   ├── seo.py                # Agent 4: SEO
│   │   ├── editor.py             # Agent 5: Editor
│   │   ├── translator.py         # Agent 6: Translator
│   │   ├── quality.py            # Agent 7: Quality
│   │   └── publisher.py          # Agent 8: Publisher
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py             # Pydantic config (multi-provider presets)
│   │   ├── llm_client.py         # OpenAI-compatible client (SSE streaming)
│   │   ├── mimo_client.py        # Backward-compat shim → llm_client
│   │   └── token_tracker.py      # Per-agent token metrics
│   ├── pipeline/
│   │   ├── __init__.py
│   │   └── orchestrator.py       # 8-agent pipeline coordinator
│   └── utils/
│       ├── __init__.py
│       ├── text.py               # Word count, slugify, reading time
│       └── export.py             # Markdown/HTML export
├── tests/
│   ├── conftest.py               # Shared fixtures
│   ├── unit/
│   │   ├── test_config.py
│   │   ├── test_token_tracker.py
│   │   ├── test_utils.py
│   │   └── test_agents.py
│   └── integration/
│       └── test_pipeline.py
├── docs/
│   └── api-reference.md
├── examples/
│   ├── basic_usage.py
│   └── custom_pipeline.py
├── scripts/
│   └── run_benchmark.py
├── pyproject.toml
├── LICENSE
└── README.md
```

## API Reference

### LLMClient

```python
from contentforge.core.llm_client import LLMClient, ChatMessage

async with LLMClient(config) as client:
    # Non-streaming
    response = await client.chat([
        ChatMessage(role="system", content="You are helpful."),
        ChatMessage(role="user", content="Explain AI agents."),
    ])
    print(response.content)
    print(f"Tokens: {response.usage.total_tokens}")

    # Streaming
    async for chunk in client.stream_chunks(messages):
        print(chunk.delta, end="", flush=True)
```

**Auth styles**: `provider="openai"` (and openrouter/ollama) use `Authorization: Bearer`; `provider="mimo"` uses the `api-key` header. The right style is selected automatically from the provider preset. `MiMoClient` remains importable as a backward-compatible alias of `LLMClient`.

### TokenTracker

```python
from contentforge.core.token_tracker import TokenTracker

tracker = TokenTracker()
tracker.start_pipeline()
# ... run agents ...
tracker.end_pipeline()

print(tracker.report())  # Human-readable report
tracker.save()           # Persist to JSON
```

## License

MIT License — see [LICENSE](LICENSE) for details.

---

**Provider-agnostic** — works with OpenAI, OpenRouter, Ollama, llama.cpp, Xiaomi MiMo, or any OpenAI-compatible `/chat/completions` endpoint.
