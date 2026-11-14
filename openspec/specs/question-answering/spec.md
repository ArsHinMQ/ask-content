# question-answering Specification

## Purpose

Answer a user's question about an initialized video by retrieving relevant
transcript segments with hybrid retrieval, refining the question into search
queries, and letting an LLM select which segments can answer it.

## Requirements

### Requirement: Ask a question about an initialized video

The system SHALL expose `POST /ask/{video_id}/{language}` that takes a JSON
body with a `question` string and returns a list of transcript segments that
together contain what is needed to answer the question.

#### Scenario: Question about an initialized video

- **WHEN** `POST /ask/{video_id}/{language}` is called for a video that has been initialized in that language
- **THEN** the response contains segments with `segment_id`, `text`, `start`, `end`, and a `reason` explaining why the segment was selected

#### Scenario: Question cannot be answered from the transcript

- **WHEN** no candidate segment addresses the question
- **THEN** the response contains an empty segment list

### Requirement: Hybrid retrieval over the video's transcript

The system SHALL search the chunk database restricted to the requested video
and language, using hybrid retrieval (semantic embeddings plus keyword
matching), returning up to 20 segments per query. For a sectioned video, the
search SHALL additionally be restricted to the selected sections; for an
unsectioned video, retrieval is over the whole video as before.

#### Scenario: Retrieval is scoped to one video and language

- **WHEN** a search runs for a video and language
- **THEN** only segments stored for that video and language can be returned

#### Scenario: Retrieval is scoped to the selected sections

- **WHEN** a search runs for a question about a sectioned video
- **THEN** only segments belonging to the selected sections can be returned

### Requirement: LLM query refinement and expansion

Before answering, the system SHALL ask the LLM to turn the user's question
into 1 to 4 standalone search queries (resolving conversational references,
keeping queries short and spoken-style), then run each query through retrieval
and merge the results with the initial search, deduplicating by `segment_id`.

#### Scenario: Follow-up style question

- **WHEN** the user's question contains references like "it" or "that part"
- **THEN** the generated queries state the explicit topic so retrieval works without conversation history

#### Scenario: Non-searchable input

- **WHEN** the question is not searchable (e.g. a greeting or a request about the assistant itself)
- **THEN** the refinement yields no queries and only the initial search's candidates are considered

#### Scenario: Deduplication across queries

- **WHEN** multiple queries retrieve the same `segment_id`
- **THEN** the segment appears once in the candidate set

### Requirement: LLM selection of answerable segments

The system SHALL ask the LLM to choose, from the candidate segments only, the
smallest set of excerpts needed to answer the question, each with a confidence
score (1–10) and a reason. Selection SHALL judge only from the excerpt text,
SHALL NOT invent `segment_id`s outside the candidates, and SHALL order the
returned segments by confidence, highest first.

#### Scenario: Segments spanning the answer

- **WHEN** the answer is spread across several consecutive segments
- **THEN** all segments needed for a complete answer are selected

#### Scenario: Only candidates may be returned

- **WHEN** the LLM returns a `segment_id` that is not in the candidate set
- **THEN** that segment is dropped from the response

### Requirement: Returned segments carry transcript text and timestamps

Each returned segment SHALL include the actual transcript text and the
`start`/`end` timestamps of the stored segment, joined with the LLM's
selection reason.

#### Scenario: Response shape

- **WHEN** the answer contains selected segments
- **THEN** every segment includes `segment_id`, `text`, `start`, `end`, and `reason`

### Requirement: Section selection by embedding similarity

For a sectioned video, the system SHALL select the sections to search by
semantic similarity between the question's embedding and the sections'
title-and-summary embeddings, taking the 3 most similar sections
unconditionally, without a similarity threshold. An unsectioned video SHALL
skip section selection.

#### Scenario: Top sections are selected without a threshold

- **WHEN** a question is asked about a video with 8 sections
- **THEN** the 3 sections whose titles and summaries are most similar to the question are selected, regardless of similarity values

#### Scenario: Fewer sections than the selection size

- **WHEN** a sectioned video has fewer than 3 sections
- **THEN** all of its sections are selected

#### Scenario: Unsectioned video skips selection

- **WHEN** a question is asked about a video without sections
- **THEN** no section selection happens and retrieval runs over the whole video

### Requirement: Whole-video fallback after failed section-scoped answering

For a sectioned video, if the section-scoped search returns no candidates, or
the LLM selection returns `answerable=false`, the system SHALL retry retrieval
over the entire video before producing the final response.

#### Scenario: Scoped search finds nothing

- **WHEN** the search restricted to the selected sections returns no candidates
- **THEN** retrieval is retried over the entire video

#### Scenario: Scoped candidates do not answer the question

- **WHEN** the LLM selection over section-scoped candidates returns `answerable=false`
- **THEN** retrieval is retried over the entire video and selection runs again on the broader candidates

#### Scenario: Scoped answering succeeds

- **WHEN** the LLM selection over section-scoped candidates returns at least one segment
- **THEN** no whole-video retry happens and the section-scoped results are returned
