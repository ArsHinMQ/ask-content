# Design

## Context

Today `/init` downloads captions (`yt_dlp.YoutubeDL.download`, json3), chunks them into ~30s segments, and embeds them into a single LanceDB table `chunks` (`api/brain/db.py`) using `BAAI/bge-small-en-v1.5`. `/ask` runs one initial search plus up to four refined-query searches (`limit=20` each), merges by `segment_id`, and feeds the whole pool to `find_possible_answers`. All LLM calls go through `LLManager`'s `PROMPTS` registry. Transcripts are cached at `transcripts/{video_id}.{language}.json`. The current yt-dlp options never extract video metadata, so the video duration is unknown today.

## Goals / Non-Goals

**Goals:**

- Shrink the candidate pool fed to `find_possible_answers` on long videos by scoping retrieval to ~3 sections.
- Keep ask-time latency flat: section selection must add no LLM call.
- Make sectioning a one-time, cacheable init cost.

**Non-Goals:**

- YouTube chapters (explicitly rejected for now; uniform own-method sectioning).
- Async init (Celery, "processing" UI) — design only must not preclude it.
- Any change to the `/init` or `/ask` request/response shapes.
- Changing the chunking granularity or the embedding model.

## Decisions

1. **Uniform own-method sectioning; chapters ignored.** One code path for every ≥10min video. Alternatives considered: chapters (creator/auto chapter coverage gaps, generic titles, yt-dlp chapter quirks) and hybrid (chapters where present). Uniform windows won on simplicity; chapters can be layered in later as a better window source without changing the downstream contract.

2. **Section decision at init, not at ask time.** Windows are fixed 5-minute transcript spans; titles/summaries are computed once and cached. The ask-time step is pure embedding similarity. Alternative rejected: letting `refine_user_question` also pick sections — it would couple two concerns and make the refine prompt video-dependent for every question.

3. **Duration from yt-dlp `extract_info`.** Switch the downloader from `ydl.download()` to `extract_info`-style extraction (metadata + subtitle files in one pass; still no video download). Alternative: derive duration from the last caption event's end — rejected because it measures transcript coverage, not video length, and intros/trailers can skew it.

4. **Sections live in a new LanceDB table `sections`; `chunks` gains a `section_id` column.** The `sections` table has `video_id`, `language`, `section_id`, `title`, `summary`, `start`, `end`, and a vector column produced by the same registered `sentence-transformers` embedding applied to `title + ". " + summary` (a `SourceField` on a joined text column keeps it automatic). Same embedder guarantees query and section vectors are comparable. `chunks.section_id` is an empty string for unsectioned videos, so one filter style works everywhere.

5. **Schema migration by recreation.** LanceDB's `exist_ok=True` does not alter an existing table schema, so `db.py` drops and recreates `chunks` when its schema differs from the current `Chunk` model. Existing stored segments are discarded rather than migrated — there is no bulk re-init step; a video is simply re-initialized on demand the next time someone initializes it. The DB is a local dev artifact (`api/yt_rag_db/`), so this is acceptable. Rolling back the code restores the old model, which again triggers recreation.

6. **One batched titling call.** New prompt `title_sections` in `PROMPTS` with a pydantic output model: `sections: list[SectionTitleResult]`, each `{title, summary}`; all window transcripts are interpolated into one prompt as numbered blocks. One call per video keeps init latency and request count low and avoids partial-failure bookkeeping. Model/temperature mirror the existing prompts. Alternative rejected: one call per window (simple retry granularity, but N× requests and slow init — the opposite of the chosen batching).

7. **Section cache next to the transcript cache.** `transcripts/{video_id}.{language}.sections.json`, written when titling completes; re-init loads it and skips the LLM. Regenerated when unparseable. It is not keyed to a transcript hash: the transcript cache itself is the change detector — if the transcript is re-fetched and differs, sections are recomputed on the next init (the transcript cache is content-stable per video/language today).

8. **Ask-time flow.** If the video has sections: embed the question, vector-search `sections` filtered by `video_id`/`language` with `limit=3`, no threshold. Collect the ≤3 `section_id`s and extend the existing `.where()` filter with `section_id IN (...)` for the initial search and every refined-query search. If the scoped search yields no candidates, or `find_possible_answers` returns `answerable=false`, rerun the full existing pipeline unscoped and use its result. Selection output handling is otherwise unchanged.

## Risks / Trade-offs

- [Titling assigns a wrong/mismatched title] → top-3 selection plus the whole-video fallback bounds the damage to extra latency, not a wrong empty answer.
- [Free OpenRouter model returns malformed JSON for the batched output] → pydantic-ai validation already raises; init fails loudly and can be retried. If it proves flaky, shrink the batch later without changing the prompt's contract.
- [Init latency grows with video length (one large prompt)] → batching is the mitigation; the titling step stays isolated so it can move into a Celery task later without touching chunking or retrieval.
- [5-minute windows cut mid-topic] → titles may blur topic boundaries; acceptable for retrieval scoping since selection is fuzzy matching, not exact routing.
- [Cosine distance thresholds would be folklore] → avoided entirely: unconditional top-3, no cutoff.
- [Existing chunk data invalidated by schema recreation] → old rows are dropped, not migrated; videos are re-initialized on demand.

## Migration Plan

1. Land schema change (`chunks` recreation + new `sections` table) and init-side sectioning.
2. Delete the existing `chunks` data (the schema-drift recreation drops it anyway); no bulk re-run of `/init` — videos are re-initialized on demand.
3. Land the ask-time scoping + fallback (or ship together; the fallback keeps behavior safe even while titles are unproven).

## Open Questions

None — decisions were settled during exploration with the user.

