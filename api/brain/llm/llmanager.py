import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Generic, Literal, TypeVar, overload

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from .models import (
    FindPossibleAnswersResult,
    RefineUserQuestionsResult,
    TitleSectionsResult,
)

PROMPTS_DIR = Path(__file__).parent / "prompts"

_PLACEHOLDER_RE = re.compile(r"\{\{(\w+)\}\}")

_DEFAULT_TEMPERATURE = 1.0

OutputT = TypeVar("OutputT")


@dataclass(frozen=True)
class PromptSpec(Generic[OutputT]):
    """How to run one prompt.

    `output_type` is the pydantic-ai output type: a `BaseModel` subclass for
    structured output (the JSON schema is generated from it) or `str` for
    plain text.
    """

    model: str
    output_type: type[OutputT] = str
    temperature: float = _DEFAULT_TEMPERATURE


# Registry of all prompts: name -> PromptSpec. To add a prompt, drop a
# `<name>.md` template in prompts/ and add an entry here.
PROMPTS: dict[str, PromptSpec[Any]] = {
    "refine_user_question": PromptSpec(
        model="meta-llama/llama-3.1-8b-instruct",
        output_type=RefineUserQuestionsResult,
        temperature=0.7,
    ),
    "find_possible_answers": PromptSpec(
        model="meta-llama/llama-3.1-8b-instruct",
        output_type=FindPossibleAnswersResult,
        temperature=0.7,
    ),
    "title_sections": PromptSpec(
        model="meta-llama/llama-3.1-8b-instruct",
        output_type=TitleSectionsResult,
        temperature=0.7,
    ),
}


class LLManager:
    """Renders prompt templates and runs them through an LLM via OpenRouter.

    Each prompt consists of a `<name>.md` template with `{{KEY}}` placeholders
    in `prompts/`, plus a `PromptSpec` in `PROMPTS` that names the model and
    the output type.

    `process` is async and must be awaited. Its return value (not the
    coroutine) matches the prompt's `output_type`: a pydantic model instance
    for structured prompts, `str` for text prompts.
    """

    # Overloads give callers precise types for known prompt names.
    # Keep in sync with PROMPTS. kwargs are Any: templates stringify values,
    # and missing/unused kwargs are still validated at runtime.
    @overload
    async def process(
        self, prompt_name: Literal["refine_user_question"], **kwargs: Any
    ) -> RefineUserQuestionsResult: ...

    @overload
    async def process(
        self, prompt_name: Literal["find_possible_answers"], **kwargs: Any
    ) -> FindPossibleAnswersResult: ...

    @overload
    async def process(
        self, prompt_name: Literal["title_sections"], **kwargs: Any
    ) -> TitleSectionsResult: ...

    @overload
    async def process(self, prompt_name: str, **kwargs: Any) -> Any: ...

    async def process(self, prompt_name: str, **kwargs: Any) -> Any:
        """Render the prompt with kwargs, run the LLM, and return the output."""
        spec = self._get_spec(prompt_name)
        prompt = self._get_prompt(prompt_name, **kwargs)
        return await self._run_llm(prompt, spec)

    @staticmethod
    def _get_spec(name: str) -> PromptSpec[Any]:
        """Look up the PromptSpec for a prompt name.

        Raises:
            KeyError: If the prompt is not registered in PROMPTS.
        """
        try:
            return PROMPTS[name]
        except KeyError:
            raise KeyError(
                f"Prompt '{name}' is not registered; known prompts: {sorted(PROMPTS)}"
            ) from None

    def _get_prompt(self, name: str, **kwargs: str) -> str:
        """Load a prompt template and substitute {{KEY}} placeholders with kwargs.

        Raises:
            FileNotFoundError: If the prompt file does not exist.
            KeyError: If a {{KEY}} placeholder has no matching kwarg, or a kwarg
                has no matching placeholder.
        """
        path = self._prompt_path(name, ".md")
        template = path.read_text(encoding="utf-8")

        placeholder_keys = set(_PLACEHOLDER_RE.findall(template))

        missing_keys = placeholder_keys - kwargs.keys()
        if missing_keys:
            raise KeyError(f"Missing arguments for prompt '{name}': {sorted(missing_keys)}")

        unused_kwargs = kwargs.keys() - placeholder_keys
        if unused_kwargs:
            raise KeyError(f"Unused arguments for prompt '{name}': {sorted(unused_kwargs)}")

        for key in placeholder_keys:
            template = template.replace("{{" + key + "}}", str(kwargs[key]))

        return template

    async def _run_llm(self, prompt: str, spec: PromptSpec[Any]) -> Any:
        """Send the rendered prompt to the configured model via OpenRouter.

        Uses the native async `agent.run` (not `run_sync`) so it can be
        awaited inside a running event loop (FastAPI/uvicorn).
        """
        agent = Agent(
            model=_build_model(spec.model),
            output_type=spec.output_type,
            model_settings={"temperature": spec.temperature},
        )
        return (await agent.run(prompt)).output

    @staticmethod
    def _prompt_path(name: str, suffix: str) -> Path:
        if not name.endswith(suffix):
            name = f"{name}{suffix}"
        path = PROMPTS_DIR / name
        if not path.is_file():
            raise FileNotFoundError(f"Prompt file '{name}' not found in {PROMPTS_DIR}")
        return path


def _build_model(model_name: str) -> OpenAIChatModel:
    """Build the OpenRouter-backed model (OpenAI-compatible endpoint).

    Split out as a module-level function so tests can monkeypatch it
    (e.g. with pydantic_ai.models.test.TestModel).
    """
    # Imported lazily so the module can be loaded without env vars configured.
    from config import get_settings

    s = get_settings()
    return OpenAIChatModel(
        model_name,
        provider=OpenAIProvider(
            base_url=s.openrouter_base_url,
            api_key=s.openrouter_api_key,
        ),
    )


