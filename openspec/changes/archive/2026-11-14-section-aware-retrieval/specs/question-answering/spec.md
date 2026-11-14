# Spec Delta

## MODIFIED Requirements

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

## ADDED Requirements

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
