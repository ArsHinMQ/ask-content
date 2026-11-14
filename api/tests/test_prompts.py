"""Smoke tests for the LLM pipeline: render, run, validate.

The model is replaced with pydantic-ai's `TestModel`, so no network or API key
is needed (see AGENT.md).
"""

import asyncio

import pytest
from brain.llm import LLManager, llmanager
from brain.llm.models import (
    FindPossibleAnswersResult,
    RefineUserQuestionsResult,
    TitleSectionsResult,
)
from pydantic_ai.models.test import TestModel


@pytest.fixture(autouse=True)
def _test_model(monkeypatch):
    monkeypatch.setattr(llmanager, "_build_model", lambda name: TestModel())


def test_refine_user_question_returns_typed_output():
    result = asyncio.run(
        LLManager().process(
            "refine_user_question", user_question="what is the OSI model?"
        )
    )
    assert isinstance(result, RefineUserQuestionsResult)


def test_find_possible_answers_returns_typed_output():
    result = asyncio.run(
        LLManager().process(
            "find_possible_answers",
            user_question="what is the OSI model?",
            answer_options="[]",
        )
    )
    assert isinstance(result, FindPossibleAnswersResult)


def test_title_sections_returns_typed_output():
    result = asyncio.run(
        LLManager().process("title_sections", sections="Section 1: hello")
    )
    assert isinstance(result, TitleSectionsResult)


def test_missing_placeholder_raises_key_error():
    with pytest.raises(KeyError, match="Missing arguments"):
        LLManager()._get_prompt("refine_user_question")


def test_unused_kwarg_raises_key_error():
    with pytest.raises(KeyError, match="Unused arguments"):
        LLManager()._get_prompt("refine_user_question", user_question="x", extra="y")


def test_unknown_prompt_raises_key_error():
    with pytest.raises(KeyError, match="not registered"):
        LLManager()._get_spec("does_not_exist")
