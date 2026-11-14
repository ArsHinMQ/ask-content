# video-sectioning Specification

## Purpose
Split long video transcripts into titled sections at ingestion time so that
later question answering can scope retrieval to a few relevant sections instead
of the whole transcript.

## Requirements

### Requirement: Section long transcripts into ~5-minute windows

The system SHALL, when initializing a video whose duration is at least 10
minutes, split its transcript into consecutive sections of approximately 5
minutes of transcript each. The final partial window SHALL become a final
section. Videos shorter than 10 minutes SHALL NOT be sectioned: no section
metadata is produced and their chunks carry no section.

#### Scenario: Sectioning a 20-minute video

- **WHEN** a video of about 20 minutes is initialized
- **THEN** its transcript is split into 4 sections covering the whole transcript chronologically

#### Scenario: Short video is not sectioned

- **WHEN** a video shorter than 10 minutes is initialized
- **THEN** no sections are created and its chunks carry no section

#### Scenario: Partial trailing window

- **WHEN** the transcript does not divide evenly into 5-minute windows
- **THEN** the remaining transcript becomes one final, shorter section

### Requirement: Generate a title and summary for each section via one batched LLM call

The system SHALL obtain, in a single batched LLM call over all of a video's
sections, a short title and a short summary for each section, derived from that
section's transcript text. Every section SHALL receive exactly one title and
one summary, in window order.

#### Scenario: Titles and summaries for all windows

- **WHEN** a video is sectioned into 4 windows
- **THEN** one LLM call produces a title and a summary for each of the 4 windows, in order

### Requirement: Sections are findable by semantic similarity

The system SHALL store each section's title, summary, and time range such that
a query can be matched against sections by semantic similarity between the
query and the section's title and summary.

#### Scenario: Matching a question to a section

- **WHEN** a question's embedding is compared against a sectioned video's sections
- **THEN** each section yields a similarity indicating how relevant its title and summary are to the question

### Requirement: Chunks record their section

For a sectioned video, each stored transcript segment SHALL record the section
whose time range contains it.

#### Scenario: Chunk inside a section

- **WHEN** a transcript segment starts and ends within one section's time range
- **THEN** the stored segment references that section

### Requirement: Section metadata cache on disk

The system SHALL cache each sectioned video's section metadata (titles,
summaries, time ranges) on disk per video and language, and reuse it on
re-initialization without another LLM call when the transcript is unchanged. A
corrupt cache entry SHALL be discarded and regenerated.

#### Scenario: Re-init reuses cached sections

- **WHEN** a sectioned video and language is initialized again
- **THEN** the cached section metadata is reused and no LLM titling call is made

#### Scenario: Corrupt section cache

- **WHEN** the cached section metadata cannot be parsed
- **THEN** it is discarded and regenerated with a fresh LLM call
