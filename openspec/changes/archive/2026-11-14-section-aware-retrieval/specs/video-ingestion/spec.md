# Spec Delta

## MODIFIED Requirements

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

## ADDED Requirements

### Requirement: Transcript fetch provides the video duration

The transcript fetcher SHALL provide the video's duration alongside the
downloaded transcript, so initialization can decide whether the video is
sectioned.

#### Scenario: Duration available at initialization

- **WHEN** captions are fetched for a video
- **THEN** the fetch result includes the video's duration
