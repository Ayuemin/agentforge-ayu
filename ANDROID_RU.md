# AgentForge on Android (Termux + Ubuntu)

This fork keeps the original eight-agent pipeline and system prompts. It adds an opt-in
OpenRouter / DeepSeek V4.1 Flash profile for Russian articles.

## Start from Termux

```sh
proot-distro login ubuntu
```

Use Ubuntu's own Python and exclude Termux's Python from `PATH`:

```sh
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
hash -r
```

## Fresh installation (does not touch the original checkout)

```sh
cd ~
git clone --branch work/android-deepseek-ru-no-token-limits --single-branch \
  https://github.com/Ayuemin/agentforge-ayu.git agentforge-ayu
cd ~/agentforge-ayu
/usr/bin/python3 -m venv .venv
source .venv/bin/activate
python -m pip install --only-binary=:all: -e .
```

## Set the OpenRouter API key without saving it in a file

```sh
read -rsp 'OpenRouter key: ' OPENROUTER_API_KEY
echo
export OPENROUTER_API_KEY
```

## Run

```sh
contentforge --config contentforge.android.yaml agents
contentforge --config contentforge.android.yaml generate "Почему телефон быстро разряжается"
```

The file `contentforge.android.yaml` selects:
- OpenRouter and `deepseek/deepseek-v4.1-flash` for all eight agents;
- Russian articles (`language: ru`);
- omission of the `max_tokens` parameter in normal and streaming requests;
- 1,500 target words and up to three editor/quality passes;
- translation disabled because the article is written directly in Russian.

The CLI now preserves the YAML language and word count, unless you override them with
`--language` or `--words`.

To check the resolved settings *without an API request*:

```sh
python -c "from contentforge.core.config import ContentForgeConfig; c=ContentForgeConfig.from_yaml('contentforge.android.yaml'); print(c.llm.provider, c.llm.model, c.llm.omit_max_tokens, c.pipeline.language, c.pipeline.target_word_count)"
```

Expected:

```text
openrouter deepseek/deepseek-v4.1-flash True ru 1500
```

To run regression tests (developer dependencies required):

```sh
python -m pip install --only-binary=:all: pytest pytest-asyncio
python -m pytest tests/unit/test_android_profile.py
```

The option `omit_max_tokens: true` means the program does not send an artificial
output cap to the API. **It does not bypass the model's provider-side limits** or
remove the article word-count target or editor iteration bound. It can affect API costs.

The original system prompts are unchanged. A Russian-language output instruction
is appended when `pipeline.language` is `ru`; JSON keys remain unchanged.

No API key is committed to GitHub.
