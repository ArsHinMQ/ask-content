# Proposal

## Why

The code works, but the project is not publishable: there is no git repo or
history, no `.gitignore`, a live `.env` and a stray cookie file sit in the tree
next to a stale 1.5 GB venv, and there is no README, test suite or linter.
Publishing as-is risks committing secrets and makes the project hard to pick up.

Separately, the specs now overstate the system: after archiving
`section-aware-retrieval`, the baseline claims hybrid (keyword + semantic)
retrieval returning 20 segments per query, while the code does vector-only
search with a limit of 5. A false baseline is worse than no baseline — the next
change will build on it.

This change makes the repo safe to publish, cleans the small stuff, and makes
the baseline honest. It is deliberately scoped to mechanical cleanup plus
safety fixes; behavior improvements (hybrid search, prompt trimming, atomic
replace) are left as separate changes.

## What Changes

- **Project identity and repository foundation**: name the project
  `ask-content` (YouTube is the only supported source for now), initialize git
  on `main`, add `.gitignore` covering secrets, venvs, caches and local
  artifacts, write a real `README.md`, remove the stale/empty/duplicate
  artifacts, and publish it as the public `ArsHinMQ/ask-content` repository.
  Internal `yt_*` names stay until a later change adds a second source.
- **Input validation**: validate `video_id` and `language` at the API boundary
  before they reach cache filenames or database filters.
- **Cookie config actually works**: cookie settings are read through the app
  settings, so values in `api/.env` take effect instead of being silently
  ignored.
- **Section cache correctness**: reuse cached section metadata only when its
  time ranges still match the current transcript windows.
- **Mechanical cleanup**: replace `print` with `logging`, drop a debug print and
  a pointless response subclass, add missing return types, narrow a
  possibly-unset variable, anchor the database path to the package, align the
  refinement model filename with its prompt, and remove/pin dependencies.
- **Tooling**: add `ruff` (lint + format), `pytest` with `TestModel` smoke tests
  for the prompt pipeline and a chunking unit test, and a CI workflow that runs
  both.
- **Spec correction**: replace the "hybrid retrieval, up to 20 per query"
  requirement with the behavior the code actually has (semantic/vector
  retrieval, up to 5 per query).
- **BREAKING**: invalid `video_id`/`language` values now fail with `422` instead
  of producing undefined query/file behavior.

Out of scope: implementing hybrid search, changing the retrieval limit to 20,
atomic replacement of existing rows, changing prompt content beyond removing
references to conversation history that is never sent, and any new feature.

## Capabilities

### New Capabilities

- `request-validation`: Accept only well-formed video IDs and language codes on
  the API endpoints, so identifiers are safe to use in cache paths and database
  filters.

### Modified Capabilities

- `video-ingestion`: Cookie configuration is read from the application settings
  (including `api/.env`), not only from variables exported in the shell.
- `question-answering`: Retrieval is semantic/vector search over the selected
  scope, returning up to 5 segments per query — not hybrid search with 20.
- `video-sectioning`: Cached section metadata is reused only when its time
  ranges match the current transcript windows.

## Impact

- Repository root: new `.gitignore`, `README.md` (named `ask-content`),
  `pyproject.toml`, CI workflow; removes `venv/`, `250`, empty `client/`, stale
  transcript cache entries. Code symbols keep their `yt_*` names.
- `api/main.py`: endpoint parameter validation, logging, response model.
- `api/brain/yt_downloader.py`: cookie settings source, validated cache
  filenames, logging.
- `api/brain/yt_embedder.py`: cache range check, logging, type fixes.
- `api/brain/db.py`: database path anchored to the `api/` directory.
- `api/config.py`: cookie-related settings fields.
- `api/brain/llm/`: rename `models/refine_user_questions.py`, drop stale prompt
  wording.
- `api/requirements.txt` + new dev tooling: remove unused dependency, pin
  unpinned ones.
- `openspec/specs/`: three modified capabilities, one new capability.
- The existing `section-aware-retrieval` change is archived before this change
  so its deltas become the baseline this change amends.
