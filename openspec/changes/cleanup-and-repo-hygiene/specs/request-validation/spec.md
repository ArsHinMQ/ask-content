# Spec Delta

## Purpose

Reject malformed video identifiers and language codes at the API boundary so
they can never reach cache paths or database filters.

## ADDED Requirements

### Requirement: Video and language identifiers are validated

Both video endpoints SHALL validate the `video_id` and `language` path
parameters before ingesting or answering. `video_id` SHALL be exactly 11
characters from `[A-Za-z0-9_-]`; `language` SHALL be a lowercase primary tag of
2–3 letters, optionally followed by a hyphen and a 2–4 letter region or script
tag. An invalid value SHALL produce a `422` response, and the request SHALL NOT
read or write cache files or query the database.

#### Scenario: Invalid video ID is rejected

- **WHEN** a request uses a `video_id` that is not 11 characters from the allowed set
- **THEN** the response is `422` and no cache file or database row is touched

#### Scenario: Invalid language is rejected

- **WHEN** a request uses a `language` that is not a valid language tag
- **THEN** the response is `422` and no cache file or database row is touched

#### Scenario: Valid identifiers proceed

- **WHEN** both identifiers are valid
- **THEN** the endpoint behaves exactly as before validation was added
