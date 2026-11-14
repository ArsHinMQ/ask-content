# Design

## Context

See `proposal.md` — Why. Relevant current state:

- Python 3.13 / FastAPI backend runs from `api/` (`uvicorn main:app`); imports
  are rooted there (`brain.*`, `config`). There is no packaging metadata.
- `api/brain/db.py` connects to `./yt_rag_db` at import time, relative to the
  process working directory.
- `YTDownloader` reads `YT_COOKIES_FROM_BROWSER` / `YT_COOKIES_FILE` from
  `os.environ`; `config.Settings` reads `api/.env` but is only imported lazily
  by the LLM layer, so `.env` values never reach the downloader.
- `section-aware-retrieval` is archived, so `video-sectioning` exists in the
  baseline this change amends.
- The API has no test suite; `AGENT.md` documents the `TestModel` smoke pattern.

## Goals / Non-Goals

**Goals:**

- A publishable repository with no secrets, venvs or local artifacts tracked.
- Validated API identifiers before any file or database access.
- Cookie settings that work when configured only in `api/.env`.
- Cached section metadata that cannot outlive a changed transcript window set.
- Lint, tests and CI that run from the repository root.
- Specs that describe the code that exists.

**Non-Goals:**

- Implementing keyword/FTS search or changing the 5-segment per-query limit.
- Atomic replacement of stored rows on re-init.
- Trimming the `find_possible_answers` candidate payload or enforcing
  `{max_ranges}`.
- Restructuring `api/` into an installable package or adding a license.
- Any new endpoint or response field.

## Decisions

1. **Validate at the endpoint, not in the downloader.** Use typed FastAPI path
   parameters with patterns: `video_id` `^[A-Za-z0-9_-]{11}$`, `language`
   `^[a-z]{2,3}(-[A-Za-z]{2,4})?$`. FastAPI returns `422` before the handler
   runs, so no cache or DB access can happen. Keeping validation at the trust
   boundary avoids duplicating it in internal helpers.
   *Alternative rejected:* sanitizing values inside `YTDownloader` — leaves the
   query filter injectable and hides the contract.

2. **Cookie configuration comes from `Settings`.** Add optional
   `yt_cookies_from_browser` and `yt_cookies_file` fields to
   `config.Settings` and read them lazily in `YTDownloader` via
   `get_settings()`, keeping the current precedence: browser profile first,
   then file. The lazy import preserves the ability to import the module
   without configuration.
   *Alternative rejected:* `dotenv.load_dotenv()` in the downloader — duplicates
   configuration loading and leaks `.env` into `os.environ` process-wide.

3. **Section cache validity is the window range list.** Reuse cached metadata
   only when both the count and every `(start, end)` pair match the freshly
   computed windows; otherwise re-title and rebuild ranges from the fresh
   windows. Titles are cheap to regenerate and never reused for a different
   transcript.
   *Alternative rejected:* hashing transcript text — heavier and unnecessary
   when the ranges already identify the windows.

4. **Extract pure transcript math for testability.** Move the window-splitting
   helper out of `YTEmbedder` into a new `api/brain/transcript.py` (pure
   functions, no DB or model imports). `yt_embedder` keeps its behavior but
   imports the helper. This lets the chunking test run without importing
   `brain.db`, which would load `sentence-transformers` and open LanceDB.
   *Alternative rejected:* stubbing `sys.modules["brain.db"]` in the test —
   brittle and hides the real dependency.

5. **Anchor the database path to the package.** `db.py` uses
   `Path(__file__).resolve().parents[1] / "yt_rag_db"`, matching the anchoring
   already used by `YTDownloader`. Behavior is unchanged when run from `api/`
   and becomes correct from any working directory.

6. **One root `pyproject.toml`; no package build.** Ruff and pytest
   configuration live at the root, with `pythonpath = ["api"]` and
   `testpaths = ["api/tests"]`, so `ruff` and `pytest` work from the repo root.
   No build backend: nothing is distributed.
   *Alternative rejected:* `api/pyproject.toml` — splits tooling config from the
   repo root for no benefit.

7. **Tests use pydantic-ai's `TestModel`, no network.** Prompt tests monkeypatch
   `llmanager._build_model` to return `TestModel()`, per `AGENT.md`. Placeholder
   strictness is tested without a model at all. The chunking test uses synthetic
   `YTDownloaderSubtitle` events.
   *Alternative rejected:* live OpenRouter calls in CI — nondeterministic and
   needs a key.

8. **Publish only after cleanup.** The project is named `ask-content`; only
   the repository and user-facing docs use that name, while code symbols keep
   their `yt_*` names because YouTube is the only source today. Sequence:
   `git init` → `.gitignore` → clean → tests → `gh repo create
   ArsHinMQ/ask-content --public --source=. --remote=origin --push`. The first
   commit is the cleaned tree, so no secret ever enters history.
   *Alternative rejected:* init/push first, clean in a later commit — the
   secret would already be in history.

## Risks / Trade-offs

- **CI installs `sentence-transformers` → torch, making jobs slow.** → Cache
  `pip`, run only the two test modules, and keep DB/model imports out of the
  tested modules (decision 4).
- **The 11-character ID rule rejects IDs from other video sources.** → This app
  only accepts YouTube IDs; the regex is the documented contract, and tests
  cover a valid ID with `-`/`_`.
- **Deleting `venv/`, `250` and `client/` is irreversible.** → `api/venv` has a
  superset of packages (109 vs 87); `250` is not referenced by code; `client/`
  is empty. Confirm before deleting, then commit.
- **Reading Settings in the downloader adds an `OPENROUTER_API_KEY`
  requirement to init.** → The app already requires it; the import stays lazy so
  importing modules for tests still works.
- **Public repo exposes the code and architecture.** → Accepted; no history
  exists, and no secrets are committed. Rotate the OpenRouter key if it was
  ever shared outside this machine.

## Migration Plan

1. Clean and commit before creating the remote; no history rewrite needed.
2. Rollback is a revert of the single cleanup commit; the database path and
   cache formats are unchanged, so no data migration is required.
3. Existing `yt_rag_db/` and `transcripts/` remain local and gitignored.

## Open Questions

None.
