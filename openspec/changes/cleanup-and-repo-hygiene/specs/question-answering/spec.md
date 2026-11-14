# Spec Delta

## RENAMED Requirements

- FROM: `### Requirement: Hybrid retrieval over the video's transcript`
- TO: `### Requirement: Semantic retrieval over the video's transcript`

## MODIFIED Requirements

### Requirement: Semantic retrieval over the video's transcript

The system SHALL search the chunk database restricted to the requested video
and language using semantic (vector) similarity between the query and segment
text, returning up to 5 segments per query. For a sectioned video, the search
SHALL additionally be restricted to the selected sections; for an unsectioned
video, retrieval is over the whole video as before.

#### Scenario: Retrieval is scoped to one video and language

- **WHEN** a search runs for a video and language
- **THEN** only segments stored for that video and language can be returned

#### Scenario: Retrieval is scoped to the selected sections

- **WHEN** a search runs for a question about a sectioned video
- **THEN** only segments belonging to the selected sections can be returned

#### Scenario: Query result count

- **WHEN** a single query runs against the chunk database
- **THEN** at most 5 segments are returned for that query
