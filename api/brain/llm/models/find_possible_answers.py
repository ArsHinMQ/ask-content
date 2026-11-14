from pydantic import BaseModel, Field


class FindPossibleAnswersResultSegment(BaseModel):
    segment_id: str = Field(
        description=(
            "The segment_id of the selected candidate excerpt, "
            "copied exactly from the candidates."
        )
    )
    score: int = Field(
        description=(
            "Confidence that this segment helps answer the question, "
            "from 1 (weak) to 10 (essential)."
        )
    )
    reason: str = Field(description="Why this segment was selected.")


class FindPossibleAnswersResult(BaseModel):
    answerable: bool = Field(
        description=(
            "False if none of the excerpts address the question. "
            "Must be false whenever segments is empty."
        )
    )
    segments: list[FindPossibleAnswersResultSegment] = Field(
        description=(
            "The selected candidate excerpts, identified by segment_id and "
            "ordered by score, highest confidence first. "
            "Empty list when answerable is false."
        )
    )
