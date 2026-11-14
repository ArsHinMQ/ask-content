from pydantic import BaseModel, Field


class TitleSectionsResultSection(BaseModel):
    title: str = Field(
        description=(
            "A short title (2 to 6 words) naming the topic of this transcript section."
        )
    )
    summary: str = Field(
        description=(
            "One or two sentences describing what this transcript section covers."
        )
    )


class TitleSectionsResult(BaseModel):
    sections: list[TitleSectionsResultSection] = Field(
        description=(
            "Exactly one entry per input section, in the same order as the input."
        )
    )
