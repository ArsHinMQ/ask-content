# Spec Delta

## MODIFIED Requirements

### Requirement: Section metadata cache on disk

The system SHALL cache each sectioned video's section metadata (titles,
summaries, time ranges) on disk per video and language, and reuse it on
re-initialization without another LLM call only when the cached time ranges
still match the current transcript windows. A corrupt or stale cache entry
SHALL be discarded and regenerated.

#### Scenario: Re-init reuses cached sections

- **WHEN** a sectioned video and language is initialized again with unchanged transcript windows
- **THEN** the cached section metadata is reused and no LLM titling call is made

#### Scenario: Corrupt section cache

- **WHEN** the cached section metadata cannot be parsed
- **THEN** it is discarded and regenerated with a fresh LLM call

#### Scenario: Transcript changed but window count stayed the same

- **WHEN** a re-fetched transcript produces the same number of windows with different time ranges
- **THEN** the cached metadata is not reused, titles are regenerated, and stored ranges come from the current transcript
