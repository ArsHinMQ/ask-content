# Spec Delta

## MODIFIED Requirements

### Requirement: YouTube authentication via cookies

The transcript fetcher SHALL authenticate caption downloads with YouTube
cookies taken live from a browser profile when `YT_COOKIES_FROM_BROWSER` is
set (taking precedence), otherwise from a cookies file (default
`cookies.txt` at the repo root, overridable via `YT_COOKIES_FILE`). Both
settings SHALL be read from the application configuration, including the
`api/.env` environment file.

#### Scenario: No cookies available

- **WHEN** neither a browser-cookie setting nor an existing cookies file is available
- **THEN** initialization fails with an error explaining how to provide cookies

#### Scenario: Bot check

- **WHEN** YouTube answers the caption download with a bot check
- **THEN** the failure reports the yt-dlp log tail and hints at using live browser cookies

#### Scenario: Cookie settings from the environment file

- **WHEN** `YT_COOKIES_FROM_BROWSER` or `YT_COOKIES_FILE` is set only in `api/.env`
- **THEN** the transcript fetcher uses that value without requiring the variable in the process environment
