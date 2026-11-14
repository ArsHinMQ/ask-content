from pathlib import Path

import lancedb
from lancedb.embeddings import get_registry
from lancedb.pydantic import LanceModel, Vector

# Anchored to api/ so the database path does not depend on the working directory.
db = lancedb.connect(str(Path(__file__).resolve().parents[1] / "yt_rag_db"))

embed = (
    get_registry().get("sentence-transformers").create(name="BAAI/bge-small-en-v1.5")
)


class Chunk(LanceModel):
    segment_id: str
    text: str = embed.SourceField()
    vector: Vector(embed.ndims()) = embed.VectorField()  # type: ignore
    language: str
    video_id: str
    start: float
    end: float
    section_id: str = ""  # empty for unsectioned videos (and their chunks)


class Section(LanceModel):
    """A titled ~5-minute window of a long video's transcript.

    `text` is `title + ". " + summary`; it exists so LanceDB embeds exactly the
    text the ask-time section search matches against.
    """

    video_id: str
    language: str
    section_id: str
    title: str
    summary: str
    start: float
    end: float
    text: str = embed.SourceField()
    vector: Vector(embed.ndims()) = embed.VectorField()  # type: ignore


def _schema_matches(table_schema, model: type[LanceModel]) -> bool:
    """Whether an existing table's columns still match the current model."""
    expected = model.to_arrow_schema()
    if len(table_schema) != len(expected):
        return False
    return all(
        actual.name == wanted.name and actual.type == wanted.type
        for actual, wanted in zip(table_schema, expected, strict=False)
    )


def _open_table(name: str, model: type[LanceModel]):
    """Open `name`, recreating it when its on-disk schema drifted from `model`.

    `create_table(..., exist_ok=True)` never alters an existing table's schema,
    so a changed model would otherwise be silently ignored and the old columns
    would keep being read and written. Rows are not migrated (the DB is a local
    artifact and videos are re-initialized on demand).
    """
    if name in db.list_tables():
        table = db.open_table(name)
        if _schema_matches(table.schema, model):
            return table
        db.drop_table(name)  # schema drift: drop and recreate
    return db.create_table(name, schema=model)


chunk_table = _open_table("chunks", Chunk)
section_table = _open_table("sections", Section)
