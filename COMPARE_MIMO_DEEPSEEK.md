# MiMo 2.5 Pro vs DeepSeek V4.1 Flash in Android AgentForge

Both profiles run through **OpenRouter** with the same Russian article settings.
The current mixed DeepSeek + Opus profile (`contentforge.android.yaml`) stays untouched.

| Item | MiMo | DeepSeek |
|---|---|---|
| Config | `contentforge.mimo.yaml` | `contentforge.deepseek.yaml` |
| Model in every active agent | `xiaomi/mimo-v2.5-pro` | `deepseek/deepseek-v4.1-flash` |
| Language | Russian | Russian |
| Word target | 1500 | 1500 |
| Output cap in API payload | None | None |
| Editor/Quality iterations | Up to 3 | Up to 3 |
| Translator | Off (writes in Russian directly) | Off |

**Important:** The original pipeline exits the Editor/Quality loop early when Quality scores
the article >= 80/100. So `max_iterations: 3` is a maximum, **not exactly three passes**.
All iterations that actually run use the chosen model. No prompt or stopping logic changed.

## 1. Open Ubuntu via Termux

From the Termux shell:

```sh
proot-distro login ubuntu
```

Inside Ubuntu:

```sh
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
hash -r
cd ~/agentforge-ayu
git status --short
```

If this shows local changes, back them up/reconcile before pulling. If clean:

```sh
git pull --ff-only
source .venv/bin/activate
```

Set your API key in this shell if not already set:

```sh
read -rsp "OpenRouter key: " OPENROUTER_API_KEY
echo
export OPENROUTER_API_KEY
```

## 2. Verify model selection offline

```sh
python - <<'PY'
from contentforge.core.config import ContentForgeConfig
from contentforge.agents import AGENT_REGISTRY

for file in ('contentforge.mimo.yaml', 'contentforge.deepseek.yaml'):
    c = ContentForgeConfig.from_yaml(file)
    print(file, c.llm.model, c.pipeline.language,
          c.llm.omit_max_tokens, c.pipeline.max_iterations)
    assert c.llm.provider == 'openrouter'
    assert c.llm.omit_max_tokens
    assert c.pipeline.language == 'ru'
    assert all(c.get_agent_config(a).model_override is None for a in AGENT_REGISTRY)
PY
```

## 3. Run with the SAME topic

For a fair repeat of the previous experiment, you can use the same prompt as the
earlier DeepSeek article. Choose *one identical topic string* for both runs.

```sh
TOPIC='Я проверил популярные способы ускорить Android: что действительно работает'

contentforge --config contentforge.mimo.yaml generate "$TOPIC" \
    --output ./output/compare-mimo

contentforge --config contentforge.deepseek.yaml generate "$TOPIC" \
    --output ./output/compare-deepseek
```

Each request spends OpenRouter API credits. Two requests are **not** sent in parallel.
To compare only with the existing DeepSeek output, run the MiMo command alone first.

Results:
- `output/compare-mimo/*_article.md`: MiMo article
- `output/compare-deepseek/*_article.md`: DeepSeek article
- `output/compare-mimo/metrics/*.json`: MiMo per-agent usage and timing
- `output/compare-deepseek/metrics/*.json`: DeepSeek per-agent usage and timing

The project logs token usage, not actual USD charges: check OpenRouter activity for
the exact billed amount. Without live GitHub retrieval, **do not use a bare GitHub URL**
as the sole research input and assume the model read README/release details.

## 4. Regression tests (optional; no paid API calls)

```sh
python -m pip install pytest pytest-asyncio
python -m pytest tests/unit/test_model_comparison_profiles.py
```

This work adds two YAML profiles and tests. Original prompts, API request logic,
iteration stopping, and `contentforge.android.yaml` are unchanged.
