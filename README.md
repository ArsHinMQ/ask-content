# ask-content

Ask questions about a YouTube video and get answers grounded in its transcript.

YouTube is the only supported source for now; more sources may come later.

## How it works

```
POST /init/{video_id}/{language}
  └─ fetch captions (yt-dlp)
  └─ cache transcript on disk (transcripts/)
  └─ split into ~30s chunks
  └─ (≥10 min videos) split into ~5min sections, LLM titles + summaries
  └─ embed chunks + sections into LanceDB (api/yt_rag_db/)

POST /ask/{video_id}/{language}
  └─ pick the most relevant sections (semantic)
  └─ LLM refines the question into 1–4 search queries
  └─ semantic search per query, scoped to those sections (fallback: whole video)
  └─ LLM selects the excerpts that answer the question
  └─ return the selected excerpts with timestamps and a reason
```

All LLM calls go through `api/brain/llm/LLManager`, which runs prompt templates
against an OpenRouter-hosted model. See `AGENT.md` for the module layout.

## Setup

Requires Python 3.13.

```sh
cd api
python3.13 -m venv venv
venv/bin/pip install -r requirements.txt
cp .env.example .env
```

Edit `api/.env`:

| Variable | Required | Meaning |
| --- | --- | --- |
| `OPENROUTER_API_KEY` | yes | OpenRouter API key used for every LLM call |
| `OPENROUTER_BASE_URL` | no | Override the OpenRouter endpoint |
| `YT_COOKIES_FROM_BROWSER` | no | Read YouTube cookies live from a browser profile (`firefox`, `chrome`, `brave`, `edge`, …) |
| `YT_COOKIES_FILE` | no | Path to a cookies file; defaults to `cookies.txt` at the repo root |

Cookie values are read from the app settings, so setting them in `api/.env` is
enough. Live browser cookies take precedence over a cookies file; YouTube bot
checks are handled far better by live cookies than by a stale export.

## Run

```sh
cd api
venv/bin/uvicorn main:app --reload
```

```sh
# Ingest a video (fetch captions, section, embed)
curl -X POST http://127.0.0.1:8000/init/dQw4w9WgXcQ/en

# Ask about it
curl -X POST http://127.0.0.1:8000/ask/dQw4w9WgXcQ/en \
  -H 'Content-Type: application/json' \
  -d '{"question": "What does the video say about X?"}'
```

Both endpoints validate their path parameters and return `422` for a malformed
video ID or language code.

## Local state

Everything below is gitignored and safe to delete:

- `transcripts/` — per-video caption cache plus cached section metadata.
- `api/yt_rag_db/` — LanceDB database with the embedded chunks and sections.
- `api/.env` — your secrets.
- `api/venv/` — the virtual environment.

Re-run `/init` for a video to rebuild its rows.

## Development

Run from the repository root:

```sh
api/venv/bin/ruff check .
api/venv/bin/ruff format --check .
api/venv/bin/pytest
```

## Specs

Behavior is specified with [OpenSpec](https://github.com/Fission-AI/OpenSpec)
under `openspec/`: `openspec/specs/` is the current baseline and
`openspec/changes/` holds in-flight changes. Run `openspec` commands from the
repository root.
