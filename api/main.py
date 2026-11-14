from time import perf_counter

from brain.llm import FindPossibleAnswersResult, LLManager
from brain.yt_embedder import YTEmbedder, YTEmbedderChunk, YTEmbedderMetadata
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()


class ResInitNewVideo(YTEmbedderMetadata):
    pass


@app.post("/init/{video_id}/{language}", response_model=ResInitNewVideo)
async def init_new_video(video_id: str, language: str):
    started = perf_counter()
    yte = YTEmbedder(video_id, language)
    await yte.init_video()
    metadata = yte.get_metadata()
    print(f"[init] {video_id}/{language} total {perf_counter() - started:.1f}s", flush=True)
    return ResInitNewVideo(**metadata.model_dump())


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
        print(q)
        nyte_result = yte.search(q, section_ids=section_ids)
        for r in nyte_result:
            if r.segment_id in segment_ids:
                continue
            yte_result.append(r)
            segment_ids[r.segment_id] = r
    print(f"{label} rag {perf_counter() - rag_started:.1f}s, {len(yte_result)} candidates", flush=True)
    rag_time = perf_counter() - rag_started
    if not yte_result:
        print(f"{label} rag {rag_time:.1f}s, no candidates", flush=True)
        return None, segment_ids

    llm_started = perf_counter()
    result: FindPossibleAnswersResult = await llm_manager.process(
        "find_possible_answers", user_question=question, answer_options=yte_result
    )
    print(
        f"{label} rag {rag_time:.1f}s, llm {perf_counter() - llm_started:.1f}s",
        flush=True,
    )
    return result, segment_ids


@app.post("/ask/{video_id}/{language}", response_model=ResAskAboutVideo)
async def ask_about_video(video_id: str, language: str, data: ReqAskAboutVideo):
    started = perf_counter()
    label = f"[ask] {video_id}/{language}"
    llm_manager = LLManager()
    yte = YTEmbedder(video_id, language)

    # A sectioned video is searched in its most relevant sections first; an
    # unsectioned one has no sections to select (empty list -> whole video).
    rag_started = perf_counter()
    section_ids = yte.select_sections(data.question)
    print(f"{label} sections rag {perf_counter() - rag_started:.1f}s", flush=True)
    llm_started = perf_counter()
    refined_result = await llm_manager.process(
        "refine_user_question", user_question=data.question
    )
    print(f"{label} refine llm {perf_counter() - llm_started:.1f}s", flush=True)
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
        print(f"{label} total {perf_counter() - started:.1f}s, 0 segments", flush=True)
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
    print(
        f"{label} total {perf_counter() - started:.1f}s, {len(res.segments)} segments",
        flush=True,
    )
    return res
