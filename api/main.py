import logging
from time import perf_counter
from typing import Annotated

from brain.llm import FindPossibleAnswersResult, LLManager
from brain.yt_embedder import YTEmbedder, YTEmbedderChunk, YTEmbedderMetadata
from fastapi import FastAPI, Path
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(message)s")

app = FastAPI()
logger = logging.getLogger(__name__)

# Validated at the trust boundary: these values reach cache filenames and
# database filters, so malformed input is rejected with 422 before the handler.
VideoID = Annotated[str, Path(pattern=r"^[A-Za-z0-9_-]{11}$")]
Language = Annotated[str, Path(pattern=r"^[a-z]{2,3}(-[A-Za-z]{2,4})?$")]


@app.post("/init/{video_id}/{language}", response_model=YTEmbedderMetadata)
async def init_new_video(video_id: VideoID, language: Language):
    started = perf_counter()
    yte = YTEmbedder(video_id, language)
    await yte.init_video()
    metadata = yte.get_metadata()
    logger.info(
        "[init] %s/%s total %.1fs", video_id, language, perf_counter() - started
    )
    return metadata


class ReqAskAboutVideo(BaseModel):
    question: str


class ResAskAboutVideoRowSegment(BaseModel):
    segment_id: str
    text: str
    start: float
    end: float
    reason: str


class ResAskAboutVideo(BaseModel):
    segments: list[ResAskAboutVideoRowSegment]


async def _retrieve_and_select(
    llm_manager: LLManager,
    yte: YTEmbedder,
    question: str,
    queries: list[str],
    section_ids: list[str] | None,
    label: str,
) -> tuple[FindPossibleAnswersResult | None, dict[str, YTEmbedderChunk]]:
    """Search (optionally scoped to sections) and let the LLM select excerpts.

    Returns the selection plus the candidates it may refer to; the selection is
    `None` when the search found no candidates at all. Search and LLM time are
    logged separately: the search is local and the LLM call is not.
    """
    rag_started = perf_counter()
    yte_result = yte.search(question, section_ids=section_ids)
    segment_ids = {ytr.segment_id: ytr for ytr in yte_result}
    for q in queries:
        nyte_result = yte.search(q, section_ids=section_ids)
        for r in nyte_result:
            if r.segment_id in segment_ids:
                continue
            yte_result.append(r)
            segment_ids[r.segment_id] = r
    rag_time = perf_counter() - rag_started
    if not yte_result:
        logger.info("%s rag %.1fs, no candidates", label, rag_time)
        return None, segment_ids
    logger.info("%s rag %.1fs, %d candidates", label, rag_time, len(yte_result))

    llm_started = perf_counter()
    result: FindPossibleAnswersResult = await llm_manager.process(
        "find_possible_answers", user_question=question, answer_options=yte_result
    )
    logger.info(
        "%s rag %.1fs, llm %.1fs", label, rag_time, perf_counter() - llm_started
    )
    return result, segment_ids


@app.post("/ask/{video_id}/{language}", response_model=ResAskAboutVideo)
async def ask_about_video(
    video_id: VideoID, language: Language, data: ReqAskAboutVideo
):
    started = perf_counter()
    label = f"[ask] {video_id}/{language}"
    llm_manager = LLManager()
    yte = YTEmbedder(video_id, language)

    # A sectioned video is searched in its most relevant sections first; an
    # unsectioned one has no sections to select (empty list -> whole video).
    rag_started = perf_counter()
    section_ids = yte.select_sections(data.question)
    logger.info("%s sections rag %.1fs", label, perf_counter() - rag_started)
    llm_started = perf_counter()
    refined_result = await llm_manager.process(
        "refine_user_question", user_question=data.question
    )
    logger.info("%s refine llm %.1fs", label, perf_counter() - llm_started)
    result, segment_ids = await _retrieve_and_select(
        llm_manager,
        yte,
        data.question,
        refined_result.queries,
        section_ids,
        f"{label} scoped",
    )
    if section_ids and (result is None or not result.answerable):
        # The selected sections could not answer the question: retry over the
        # whole video. The queries are question-derived, so only retrieval and
        # selection are re-run.
        result, segment_ids = await _retrieve_and_select(
            llm_manager,
            yte,
            data.question,
            refined_result.queries,
            None,
            f"{label} fallback",
        )

    res = ResAskAboutVideo(segments=[])
    if result is None:
        logger.info("%s total %.1fs, 0 segments", label, perf_counter() - started)
        return res
    for row in result.segments:
        segment = segment_ids.get(row.segment_id)
        if segment is None:
            continue
        res.segments.append(
            ResAskAboutVideoRowSegment(
                segment_id=row.segment_id,
                text=segment.text,
                start=segment.start,
                end=segment.end,
                reason=row.reason,
            )
        )
    logger.info(
        "%s total %.1fs, %d segments",
        label,
        perf_counter() - started,
        len(res.segments),
    )
    return res
