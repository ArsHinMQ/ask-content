from pydantic import BaseModel, Field


class RefineUserQuestionsResult(BaseModel):
    queries: list[str] = Field(
        description=(
            "1 to 4 search queries over the video transcript. "
            "Empty list if the question is not searchable."
        )
    )
