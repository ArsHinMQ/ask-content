# Tasks

## 1. Transcript fetcher: duration + extraction refactor

- [x] 1.1 Refactor `YTDownloader` from `ydl.download()` to a metadata-including extraction (e.g. `extract_info` with the same subtitle options) so captions are still written as json3 files, and return the video duration alongside `YTDownloaderSubtitle`. Verify: `cd api && venv/bin/python -c` snippet fetching a known video returns duration matching YouTube and a parsed transcript.
- [x] 1.2 Keep the transcript disk cache behavior intact (cache hit returns transcript + duration without hitting YouTube; corrupt cache re-fetches). Verify: run the fetch twice with a temp `CACHE_DIR` and confirm the second run reads from disk and still reports the duration (stored with the cached transcript or re-derived from cached data).

## 2. Database schema: chunks section tag + sections table

- [x] 2.1 In `api/brain/db.py`, add a `section_id` field (default empty string) to `Chunk`, add a `Section` LanceModel (`video_id`, `language`, `section_id`, `title`, `summary`, `start`, `end`, joined `title + ". " + summary` as `SourceField` with `VectorField`), and create the `sections` table. Verify: import `brain.db` fresh and list tables + schemas.
- [x] 2.2 Handle schema drift: when the existing `chunks` table's schema differs from the current `Chunk` model, drop and recreate it (per design decision 5). Verify: with the old on-disk table present, importing `brain.db` recreates `chunks` with the new schema and reports no error.

## 3. Section titling prompt

- [x] 3.1 Create `api/brain/llm/models/title_sections.py` with `TitleSectionsResult` (`sections: list[TitleSectionsResultSection]`, each `{title: str, summary: str}`) and re-export it from `models/__init__.py` and `brain/llm/__init__.py`. Verify: importing `brain.llm` exposes the model.


- [x] 3.2 Create `api/brain/llm/prompts/title_sections.md`: numbered transcript blocks in, one short title + short summary per block out, valid JSON only. Register `title_sections` in `PROMPTS` (model/temperature mirroring the existing prompts) and add the `Literal` overload on `process`. Verify: monkeypatched `TestModel` smoke run of `process("title_sections", sections=...)` returns a `TitleSectionsResult` with one entry per block (follow the AGENT.md smoke-test pattern).

## 4. Sectioning pipeline at init

- [x] 4.1 Add window splitting: partition the transcript into consecutive ~5-minute windows by caption event times (final partial window becomes a section); produce rows with `section_id` following a documented ID scheme (e.g. `{video_id}_{language}_sec{n}`), each with `title`, `summary`, `start`, `end`. Verify: unit-style `venv/bin/python` run over a synthetic transcript splits a 20-minute transcript into 4 windows with correct time ranges.
- [x] 4.2 Gate on duration: section only when duration ≥ 600s; otherwise skip sectioning entirely (chunks keep empty `section_id`). Verify: a synthetic short transcript (<10 min) produces no windows and no section rows.
- [x] 4.3 Wire titling: on init of a sectioned video, load `transcripts/{video_id}.{language}.sections.json` if present and parseable; otherwise run the single batched `title_sections` call over all windows, write the cache file, and regenerate on parse failure. Verify: second init of the same video makes no LLM call and reuses cached titles (monkeypatch the model builder to fail if called).
- [x] 4.4 Store sections and tag chunks: on init, replace prior `sections` rows for the video+language, assign each chunk the section containing its time range, and extend the atomic replace in `_store_transcript` to cover section references (per the modified re-init requirement). Verify: init a ≥10min video and inspect `sections` rows plus `chunks.section_id` values (every chunk tagged, ranges consistent); re-init and confirm old rows were replaced.
- [x] 4.5 Update `YTEmbedderMetadata`/`/init` response only if needed (response shape must stay compatible). Verify: `POST /init/{video_id}/{language}` returns the same fields as before.

## 5. Ask-time scoping and fallback

- [x] 5.1 Add section selection to `YTEmbedder`: embed the question, vector-search `sections` filtered by `video_id`/`language` with `limit=3`, no threshold; return the selected `section_id`s (empty list for unsectioned videos). Verify: `venv/bin/python` run against an initialized long video returns exactly ≤3 section ids for a topical question.
- [x] 5.2 Scope search: extend the `.where()` filter with `section_id IN (...)` when sections are selected, for the initial search and every refined-query search. Verify: scoped search returns only chunks whose `section_id` is in the selection (inspect returned rows).
- [x] 5.3 Implement the fallback in `/ask`: if the scoped candidate pool is empty or `find_possible_answers` returns `answerable=false`, rerun retrieval + selection over the whole video and use that result; otherwise return the scoped result. Response shape unchanged. Verify: endpoint run with a question whose scoped search yields nothing returns segments from the fallback pass (or an empty list only when the whole-video pass also fails).

## 6. Integration verification

- [x] 6.1 End-to-end init: init a long (≥10 min) video and a short (<10 min) video via the running API; confirm the long one gains sections + tagged chunks and the short one is unchanged. Verify: DB inspection + both `/init` calls succeed.
- [x] 6.2 End-to-end ask: ask topical questions against the long video and confirm answers come from plausible sections (spot-check `start`/`end` against the section ranges); ask a cross-section question and confirm the fallback produces results. Verify: manual API runs with recorded responses.
- [x] 6.3 Re-init regression: re-initialize the long video and confirm sections/chunks are replaced cleanly and a subsequent `/ask` still works. Verify: repeat `/init` then `/ask` succeeds.

## Workflow follow-up

- Archive the change after review (merges deltas into `openspec/specs/`).
- Verify the archived result.
