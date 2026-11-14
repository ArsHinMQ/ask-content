# Spec Delta

## ADDED Requirements

### Requirement: Section titling prompt

The registry SHALL provide a section titling prompt that takes the transcript
text of multiple sections and returns, for each section in order, a short title
and a short summary as structured output. It currently runs on the configured
model.

#### Scenario: Titling multiple sections in one call

- **WHEN** `process(<section-titling-prompt>, sections=...)` is called with the transcript text of 4 sections
- **THEN** it returns a validated result containing exactly one title and one summary per section, in the same order
