# Tasks

## 1. Repository foundation

- [x] 1.1 Add root `.gitignore` covering `.env`, `venv/`, `api/venv/`, `__pycache__/`, `*.py[cod]`, `api/yt_rag_db/`, `transcripts/`, `cookies.txt`, `250`, `.pytest_cache/`, `.ruff_cache/`, `.DS_Store`; after `git init`, verify each path with `git check-ignore`.
- [x] 1.2 Delete the root `venv/`, `250`, empty `client/`, `api/__pycache__/`, and stale `transcripts/e6_XOqPxKII.json`; verify `api/venv/bin/python -c "import fastapi, lancedb, yt_dlp, sentence_transformers"` still succeeds.
- [x] 1.3 Write `README.md` titled `ask-content`, noting YouTube is the only supported source for now (what it is, architecture, setup, env vars, `curl` examples for `/init` and `/ask`, local caches/DB, OpenSpec pointer); verify every command runs as written from a fresh shell.
- [x] 1.4 Run `git init -b main`, stage everything, confirm `git status` contains none of the ignored artifacts, and commit the cleaned tree.

## 2. Safety fixes

- [x] 2.1 Add `video_id`/`language` pattern validation to both endpoints via typed `Path(...)` parameters; verify with TestClient that bad values return `422` and a valid pair reaches a stubbed handler.
- [x] 2.2 Add `yt_cookies_from_browser`/`yt_cookies_file` to `Settings` and extract a `_cookie_options()` helper in `YTDownloader` that reads settings lazily with browser-over-file precedence; verify a unit test loads both from a temporary env file and checks precedence.
- [x] 2.3 Reuse cached section metadata only when every `(start, end)` matches the fresh windows (add a small predicate helper); verify a unit test covers equal ranges, different ranges, and a corrupt cache.

## 3. Mechanical cleanup

- [x] 3.1 Replace the 10 `print()` calls with module loggers, remove the `print(q)` debug line, and keep the existing timing labels; verify `grep -rn "print(" api --include="*.py" --exclude-dir=venv` returns nothing and `ruff check` passes.
- [x] 3.2 Remove the empty `ResInitNewVideo` class, use `YTEmbedderMetadata` directly, add the missing `_generate_*` return types, and narrow the possibly-`None` window bounds; verify a clean interpreter import and `ruff check`.
- [x] 3.3 Anchor the LanceDB path to `api/yt_rag_db` with `Path(__file__)`; verify `cd /tmp && PYTHONPATH=/path/to/api api/venv/bin/python -c "from brain import db; print(db.db.uri)"` reports the `api/yt_rag_db` path.
- [x] 3.4 Move window splitting into a pure `api/brain/transcript.py` and import it from `yt_embedder`; verify the chunking test passes without importing `brain.db`.
- [x] 3.5 Rename `models/refine_user_questions.py` to `refine_user_question.py` and remove the two prompt sentences that promise conversation history the API never sends; verify `pytest` prompt tests and `brain.llm` imports pass.
- [x] 3.6 Remove `youtube-transcript-api`, pin `lancedb==0.41.0` and `sentence-transformers==6.2.0` in `api/requirements.txt`; verify `api/venv/bin/pip check` and imports succeed.

## 4. Test suite and tooling

- [x] 4.1 Add a root `pyproject.toml` with ruff (line length, target `py313`) and pytest (`pythonpath = ["api"]`, `testpaths = ["api/tests"]`); verify `ruff check` and `pytest` run from the repo root.
- [x] 4.2 Add `api/tests/test_prompts.py` using `TestModel` smoke tests for all three prompts plus strict-placeholder `KeyError` cases; verify `pytest api/tests/test_prompts.py` passes with no network.
- [x] 4.3 Add `api/tests/test_transcript.py` covering 30-second windows, a trailing partial window, and section-boundary lookup; verify the module imports without `brain.db`.
- [x] 4.4 Add `.github/workflows/ci.yml` (Python 3.13, pip cache, install requirements + ruff/pytest, run lint, format check, tests); verify the YAML parses and the same commands pass locally.
- [x] 4.5 Document the project name `ask-content`, the ruff/pytest commands, and the new `brain/transcript.py` module in `AGENT.md`; verify the documented commands run as written.

## 5. Publish and integrate

- [ ] 5.1 Run `ruff check`, `ruff format --check`, and `pytest` from the repo root; verify all pass.
- [ ] 5.2 Scan the stage: `git ls-files` contains no `.env`, `250`, `cookies.txt`, venv, DB or transcript paths, and `git grep -I -E "sk-or-|OPENROUTER_API_KEY=."` is empty.
- [ ] 5.3 Create the public repo (`gh repo create ArsHinMQ/ask-content --public --source=. --remote=origin --push`); verify `gh repo view` shows it and the CI workflow run succeeds.
- [ ] 5.4 Smoke the running app: `uvicorn main:app` from `api/`, `POST /init/<invalid>/en` returns `422`, and `/ask` against an already-cached video returns `200` with the documented shape.

## Workflow follow-up

- Archive this change after review and verify the baseline reflects semantic retrieval with a 5-segment limit and the new `request-validation` capability.
