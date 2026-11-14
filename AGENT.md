# AGENT.md

Guidance for AI coding agents (and humans) working in this repo.

## Project overview

**ask-content**: ask questions about a YouTube video and get answers grounded
in its transcript. YouTube is the only supported source for now (code symbols
keep their `yt_*` names until a second source is added).

- `api/` — FastAPI backend. Runs from `api/` as the working directory
  (`uvicorn main:app`); imports are rooted there (e.g. `from brain.llm import LLManager`).
  Dependencies are in `api/venv` (`api/requirements.txt`, dev tools in
  `api/requirements-dev.txt`), Python 3.13.
- The transcript is chunked into ~30s excerpts, embedded (LanceDB in
  `api/yt_rag_db/`), and searched semantically before any LLM call.

## Development

Run from the repository root (config in `pyproject.toml`):

```sh
api/venv/bin/ruff check .          # lint
api/venv/bin/ruff format --check . # formatting
api/venv/bin/pytest                # tests (pythonpath=api, testpaths=api/tests)
```

CI (`.github/workflows/ci.yml`) runs exactly these three commands on Python 3.13.

Pure transcript math (window splitting, section lookup) lives in
`api/brain/transcript.py` — no database or embedding imports, so its tests stay
fast (`api/tests/test_transcript.py` asserts it does not pull in `brain.db`).

## OpenSpec (repo root)

OpenSpec lives at the repo root (`openspec/`) and describes the whole system.

- `openspec/` — spec-driven workflow (proposal → specs → design → tasks);
  config in `openspec/config.yaml`, current specs in `openspec/specs/`,
  in-flight changes in `openspec/changes/`.
- `openspec/specs/` holds the **baseline** (current behavior): `request-validation`,
  `question-answering`, `video-ingestion`, `video-sectioning`,
  `prompt-management`. Keep these in sync with reality — changes propose deltas
  against them, and archiving a change merges the deltas back in.
- Run `openspec` CLI commands from the repo root.
- Cline integration: skills in `.cline/skills/openspec-*` and slash-command
  workflows in `.clinerules/workflows/opsx-*.md` (e.g. `/opsx-propose` to
  start a change, `/opsx-apply` to implement it, `/opsx-archive` to finish it).
- OpenCode integration: the same workflows as skills in `.opencode/skills/`
  and commands in `.opencode/commands/opsx-*.md`. `opencode.json` loads this
  file via `instructions` (OpenCode only auto-discovers `AGENTS.md`).
- To add support for more AI tools later: `openspec init --tools <tool>`
  (`openspec update` only refreshes tools already configured).

## Scratch changes (not spec work)

Not every request is spec work. A quick experiment, a debug line, "just let me
try this" is not part of any OpenSpec change and will probably be removed again.

- Skip the test / smoke run / DB check / openspec update entirely: make the
  smallest edit and hand it back to try.
- Say in one line that it is unverified and temporary.
- Don't fold it into `openspec/specs/`, a change's tasks, or this file.
- Validation at trust boundaries still applies if it touches user data or secrets.

## LLM layer (`api/brain/llm/`)

All LLM calls go through `LLManager` — never call OpenRouter / pydantic-ai
directly elsewhere.

```
api/brain/llm/
├── __init__.py        # re-exports LLManager + result models
├── llmanager.py       # LLManager, PromptSpec, PROMPTS registry
├── models/            # pydantic output models, one module per prompt
│   ├── __init__.py    # re-exports all result models
│   ├── <prompt_name>.py
│   └── ...
└── prompts/           # one <name>.md template per prompt ({{KEY}} placeholders)
```

### How it works

- Each prompt is a `<name>.md` template in `prompts/` with `{{KEY}}`
  placeholders, plus a `PromptSpec` entry in the `PROMPTS` dict in
  `llmanager.py` (model, temperature, output_type).
- `LLManager().process(prompt_name, **kwargs)` is **async** — `await` it. It
  renders the template and runs it through the configured model via OpenRouter
  (OpenAI-compatible endpoint, creds from `api/config.py` / env vars). It uses
  pydantic-ai's native async `agent.run` (never `run_sync` — that crashes under
  a running event loop, e.g. FastAPI/uvicorn).
- **Output types are pydantic models, not dicts.** The `output_type` on a
  `PromptSpec` is a `BaseModel` subclass from `models/`; pydantic-ai generates
  the JSON schema for the LLM from it (including `Field(description=...)`
  as the field descriptions) and validates the response into a typed instance.
  `output_type=str` means plain text output.
- **Model naming convention:** result models live in
  `api/brain/llm/models/<prompt_name>.py`, one module per prompt, and are named
  `<PromptName>Result` (e.g. `RefineUserQuestionsResult` for
  `refine_user_question`, `FindPossibleAnswersResult` for
  `find_possible_answers`). Nested per-item models are prefixed with their
  parent (e.g. `FindPossibleAnswersResultSegment`).
- **Return type:** `process` returns an instance of the prompt's `output_type`.
  Precise static types come from `@overload`s on `Literal[prompt_name]` in
  `process` (kwargs are `Any` — templates stringify values; missing/unused
  kwargs are still validated at runtime) — keep overloads in sync with
  `PROMPTS`. For callers, an explicit annotation is still good practice:
  `result: FindPossibleAnswersResult = await LLManager().process(...)`.
- Placeholder rendering is strict: a `{{KEY}}` without a matching kwarg, or a
  kwarg without a matching placeholder, raises `KeyError` before any LLM call.
  Note: only **double** braces are placeholders; single braces are literal text.

### Adding a new prompt (checklist)

1. Create `api/brain/llm/prompts/<name>.md` with `{{KEY}}` placeholders.
2. If the output is structured, define a pydantic model in
   `api/brain/llm/models/<name>.py`, named `<PromptName>Result` (per-item
   sub-models prefixed with the parent, descriptions in `Field(...)`), and
   export it from `api/brain/llm/models/__init__.py`.
3. Add a `PromptSpec` entry to `PROMPTS` in `llmanager.py`:
   `"<name>": PromptSpec(model="...", output_type=MyModel, temperature=0.7)`.
4. Add an `@overload` to `process` keyed on `Literal["<name>"]` returning the
   output model, so callers get type checking.
5. Re-export the new result model from `api/brain/llm/__init__.py`.

### Testing LLM code

`api/tests/test_prompts.py` covers this module. Follow the same pattern when
adding tests: monkeypatch `llmanager._build_model` (kept module-level for
exactly this reason) to return `pydantic_ai.models.test.TestModel()` — this
exercises the full render → agent → validate pipeline with no network or API
key.

## Gotchas

- `{max_ranges}` in `prompts/find_possible_answers.md` is a single-brace
  **literal** sent to the LLM as-is. If it was meant to be a variable, change it
  to `{{max_ranges}}` and pass `max_ranges=...` to `process`. Also note it still
  says "ranges"/"excerpts" — reword if the output shape changes.
- Run Python one-liners from `api/` so `brain.*` imports resolve:
  `cd api && venv/bin/python ...`. `pytest` is configured at the repo root and
  runs from there (`pythonpath = ["api"]`).
- `config.get_settings()` is env-var driven and fails fast if
  `OPENROUTER_API_KEY` is unset — but it is only imported lazily inside
  `_build_model`, so tests can patch that function to avoid needing env vars.
- **There is no type checker configured in this repo** (no mypy/pyright config
  in requirements). The `@overload`s and annotations are enforced by your
  editor's checker (e.g. VS Code Pylance) if enabled — consider running
  `mypy`/`basedpyright` in CI before relying on them.
