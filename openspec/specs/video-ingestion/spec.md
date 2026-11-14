# video-ingestion Specification

## Purpose

Initialize a YouTube video for questioning: fetch its transcript captions,
split them into ~30-second segments, and index them for retrieval. This is the
ingestion step that must complete before a video can be asked about.

## Requirements

### Requirement: Initialize a video by ID and language

The system SHALL expose `POST /init/{video_id}/{language}` that ingests the
captions for the given YouTube video ID and language, returning the video ID
and language that were ingested.

#### Scenario: Successful initialization

- **WHEN** `POST /init/{video_id}/{language}` is called with a video that has captions in the requested language
- **THEN** the response returns the `video_id` and `language` that were ingested
- **AND** the transcript segments are stored in the chunk database for that video and language

### Requirement: Download captions with fallback between human-made and auto-generated

The transcript fetcher SHALL prefer human-made captions for the requested
language and fall back to auto-generated captions when no human-made track
exists. The requested language SHALL match plain tracks (e.g. `en`) as well as
variants (e.g. `en-orig`, `en-US`), preferring the exact plain track when both
exist.

#### Scenario: Human captions exist

- **WHEN** the video has human-made captions in the requested language
- **THEN** the human-made track is used

#### Scenario: Only auto-generated captions exist

- **WHEN** the video has no human-made captions but has auto-generated captions in the requested language
- **THEN** the auto-generated track is used

### Requirement: YouTube authentication via cookies

The transcript fetcher SHALL authenticate caption downloads with YouTube
cookies taken live from a browser profile when `YT_COOKIES_FROM_BROWSER` is
set (taking precedence), otherwise from a cookies file (default
`cookies.txt` at the repo root, overridable via `YT_COOKIES_FILE`).

#### Scenario: No cookies available

- **WHEN** neither a browser-cookie setting nor an existing cookies file is available
- **THEN** initialization fails with an error explaining how to provide cookies

#### Scenario: Bot check

- **WHEN** YouTube answers the caption download with a bot check
- **THEN** the failure reports the yt-dlp log tail and hints at using live browser cookies

### Requirement: Per-video transcript cache on disk

The transcript fetcher SHALL cache each downloaded transcript on disk
(`transcripts/{video_id}.{language}.json`) and serve subsequent requests for
the same video and language from the cache without hitting YouTube. A corrupt
cache file SHALL be deleted and re-fetched.

#### Scenario: Cache hit

- **WHEN** the transcript for the requested video and language is already cached and valid
- **THEN** no YouTube request is made and the cached transcript is used

#### Scenario: Corrupt cache entry

- **WHEN** the cached transcript file cannot be parsed
- **THEN** the cache file is removed and the transcript is re-downloaded from YouTube

### Requirement: Chunk transcript into ~30-second segments

The system SHALL split the transcript into segments of at least ~30 seconds of
caption events each. Each segment SHALL have a `segment_id` of the form
`{video_id}_{language}_{n}` (1-based, in chronological order), the joined
caption text, and `start`/`end` timestamps in seconds. A trailing partial
window SHALL be emitted as a final segment. For a sectioned video, each segment
SHALL additionally record the section whose time range contains it.

#### Scenario: Chunking a transcript

- **WHEN** a transcript is chunked
- **THEN** consecutive caption events are accumulated until the segment spans at least 30 seconds
- **AND** the final partial buffer (if any) becomes one last segment

#### Scenario: Chunking a sectioned video's transcript

- **WHEN** a video with sections is chunked
- **THEN** each stored segment references the section containing it

### Requirement: Re-initialization replaces previous segments

Re-initializing the same video and language SHALL atomically replace the
previously stored segments for that video and language — and, for a sectioned
video, its sections and section references — leaving other videos and languages
untouched.

#### Scenario: Re-init the same video

- **WHEN** a video and language that already has stored segments is initialized again
- **THEN** the old segments for that video and language are deleted and replaced with the new chunking
- **AND** any previously stored sections for that video and language are replaced with the new sectioning

### Requirement: Transcript fetch provides the video duration

The transcript fetcher SHALL provide the video's duration alongside the
downloaded transcript, so initialization can decide whether the video is
sectioned.

#### Scenario: Duration available at initialization

- **WHEN** captions are fetched for a video
- **THEN** the fetch result includes the video's duration
