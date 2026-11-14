# Proposal

## Why

On long videos, `/ask` is slow and noisier than it should be: the initial search plus up to four refined queries merge into a candidate pool of up to ~100 transcript excerpts, and the `find_possible_answers` LLM has to read all of them in one call. The vector search itself is fast; the cost is prompt size and noise. Scoping retrieval to a few relevant sections of the video shrinks and cleans that pool, cutting response time and improving answer selection.

## What Changes

- At `/init`, videos with a duration of 10 minutes or more are split into consecutive 5-minute transcript windows. An LLM generates a title and a short summary for each window (one batched call). YouTube chapters are NOT used; sectioning is always the project's own method.
- Each section's `title + summary` is embedded and stored. Every ~30-second transcript chunk from a sectioned video is tagged with its section. Videos under 10 minutes are ingested exactly as today (no windows, no titles, no section tags).
- Section titles/summaries are cached on disk alongside the transcript cache so re-initialization does not re-pay the LLM titling when the transcript is unchanged.
- At `/ask` for a sectioned video, the question is embedded and compared against the section embeddings; the top 3 sections are selected unconditionally (no score threshold), and all retrieval (initial search + refined-query searches) is scoped to those sections.
- Fallback: if the section-scoped search returns no results, or `find_possible_answers` returns `answerable=false`, the search is retried over the whole video.
- A new registered prompt (`LLManager` `PROMPTS` registry) produces per-window titles and summaries as structured output.
- `/init` becomes slower for long videos (one batched LLM call over all windows). Async processing (Celery, "processing" screen) is explicitly out of scope; the design must not preclude it.

## Capabilities

### New Capabilities

- `video-sectioning`: Splitting a long transcript into 5-minute windows, generating a title and short summary per window via LLM, embedding and storing section metadata, tagging chunks with sections, and caching section metadata on disk. Owns the entire sectioning pipeline at ingestion time.

### Modified Capabilities

- `video-ingestion`: Chunks stored for sectioned videos gain a section association; initialization of long videos now also produces sections; re-initialization replaces sections together with segments; transcript fetching must also yield the video duration.
- `question-answering`: Retrieval for sectioned videos is scoped to the top-3 sections selected by embedding similarity between the question and section title+summary embeddings, with a whole-video fallback on empty results or `answerable=false`.
- `prompt-management`: The registry gains a section titling prompt (batched windows in, title + summary per window out).

## Impact

- `api/brain/yt_downloader.py`: extract video info (duration) alongside captions; section metadata cache file next to the transcript cache.
- `api/brain/db.py`: chunks schema gains a section field; new section storage (titles, summaries, time ranges, embedding) per video/language.
- `api/brain/yt_embedder.py`: sectioning pipeline at init; section-scoped search.
- `api/brain/llm/`: new prompt template, output model, `PROMPTS` entry.
- `api/main.py`: `/ask` flow selects sections and applies the fallback path.
- No API request/response shape changes; no new external dependencies (embedding uses the existing sentence-transformers model).
