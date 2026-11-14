# prompt-management Specification

## Purpose

Centralize every LLM call: prompts are named templates with typed outputs,
registered in one place, and executed through a single manager against an
OpenRouter-backed model.

## Requirements

### Requirement: All LLM calls go through the prompt manager

All LLM calls SHALL go through the prompt manager (`LLManager`); no other
module SHALL call the LLM provider directly.

#### Scenario: Running a registered prompt

- **WHEN** `process(prompt_name, **kwargs)` is called with a registered prompt name
- **THEN** the template is rendered with the kwargs, run through the configured model, and the validated result is returned

### Requirement: Prompts are registered with model, temperature, and output type

Each prompt SHALL be a `<name>.md` template in the prompts directory plus a
`PromptSpec` entry in the `PROMPTS` registry specifying the model name, the
output type (a pydantic model for structured output, or `str` for plain text),
and a temperature (default 1.0).

#### Scenario: Unknown prompt name

- **WHEN** `process` is called with a prompt name not present in `PROMPTS`
- **THEN** a `KeyError` is raised listing the known prompt names

#### Scenario: Missing template file

- **WHEN** a prompt is registered but its template file does not exist
- **THEN** a `FileNotFoundError` is raised naming the missing file

### Requirement: Strict `{{KEY}}` placeholder rendering

Template placeholders SHALL use double braces (`{{KEY}}`) and be substituted
from the call's keyword arguments. A placeholder without a matching kwarg, or
a kwarg without a matching placeholder, SHALL raise a `KeyError` before any
LLM call is made. Single braces SHALL be treated as literal text.

#### Scenario: Missing kwarg

- **WHEN** a template contains `{{KEY}}` but the call does not pass `key`
- **THEN** a `KeyError` is raised before any LLM call

#### Scenario: Unused kwarg

- **WHEN** the call passes a kwarg that matches no placeholder in the template
- **THEN** a `KeyError` is raised before any LLM call

#### Scenario: Single braces stay literal

- **WHEN** a template contains single-brace text such as `{max_ranges}`
- **THEN** it is sent to the LLM verbatim, not substituted

### Requirement: Structured outputs are validated pydantic models

For prompts with a pydantic output type, the LLM's JSON schema SHALL be
generated from the output model (field descriptions included) and the response
SHALL be validated into an instance of that model. `process` SHALL be async
and awaited (native async agent run, never `run_sync`, so it works under a
running event loop such as FastAPI/uvicorn).

#### Scenario: Structured prompt returns a typed instance

- **WHEN** a prompt with a pydantic output type completes
- **THEN** `process` returns an instance of that output model

### Requirement: Question refinement prompt

The registry SHALL provide `refine_user_question` that turns the user's
question into 1–4 standalone transcript search queries
(`RefineUserQuestionsResult`, `queries: list[str]`), returning an empty list
when the question is not searchable. It currently runs on the configured model
at temperature 0.7.

#### Scenario: Refinement prompt is registered

- **WHEN** `process("refine_user_question", user_question=...)` is called
- **THEN** it returns a `RefineUserQuestionsResult` with 0–4 query strings

### Requirement: Excerpt selection prompt

The registry SHALL provide `find_possible_answers` that selects which
candidate transcript excerpts are needed to answer the question
(`FindPossibleAnswersResult` with `answerable: bool` and `segments` of
`segment_id`/`score` (1–10)/`reason`, ordered by score, empty and
`answerable=false` when nothing fits). It currently runs on the configured
model at temperature 0.7.

#### Scenario: Selection prompt is registered

- **WHEN** `process("find_possible_answers", user_question=..., answer_options=...)` is called
- **THEN** it returns a `FindPossibleAnswersResult` whose segments reference candidate `segment_id`s

### Requirement: Section titling prompt

The registry SHALL provide a section titling prompt that takes the transcript
text of multiple sections and returns, for each section in order, a short title
and a short summary as structured output. It currently runs on the configured
model.

#### Scenario: Titling multiple sections in one call

- **WHEN** `process(<section-titling-prompt>, sections=...)` is called with the transcript text of 4 sections
- **THEN** it returns a validated result containing exactly one title and one summary per section, in the same order
