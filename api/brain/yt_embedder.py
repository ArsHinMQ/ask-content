from time import perf_counter
from typing import Any

from brain.db import chunk_table, section_table
from brain.llm import LLManager, TitleSectionsResult
from brain.yt_downloader import (
    YTDownloader,
    YTDownloaderSection,
    YTDownloaderSubtitle,
)
from pydantic import BaseModel

# Videos at least this long are split into sections; shorter ones are ingested
# exactly as before, with untagged chunks (design decision 1).
SECTION_MIN_DURATION_SECONDS = 600.0
# Sections are consecutive windows of this many seconds of transcript.
SECTION_WINDOW_SECONDS = 300.0
# How many sections a question scopes retrieval to. Unconditional: no threshold.
SECTION_SELECTION_LIMIT = 3


class YTEmbedderMetadata(BaseModel):
    video_id: str
    language: str


class YTEmbedderChunk(BaseModel):
    segment_id: str
    text: str
    video_id: str
    language: str
    start: float
    end: float


class YTEmbedderSection(BaseModel):
    video_id: str
    language: str
    section_id: str
    title: str
    summary: str
    start: float
    end: float

    def to_row(self) -> dict[str, Any]:
        """Row for the `sections` table; `text` is what LanceDB embeds."""
        return {**self.model_dump(), "text": f"{self.title}. {self.summary}"}


class YTEmbedder:
    _downloader: YTDownloader
    _video_id: str
    _language: str

    def __init__(self, video_id: str, language: str):
        self._downloader = YTDownloader(video_id, language)
        self._video_id = video_id
        self._language = language

    def _generate_segment_id(self, n: int):
        return f"{self._video_id}_{self._language}_{n}"

    def _generate_section_id(self, n: int):
        return f"{self._video_id}_{self._language}_sec{n}"

    @staticmethod
    def _windows(
        transcript: YTDownloaderSubtitle, window: float
    ) -> list[tuple[float, float, str]]:
        """Split caption events into consecutive `window`-second spans.

        Segments accumulate events until they span `window` seconds, then the
        next one starts at the following event; a final partial window is kept.
        """
        windows: list[tuple[float, float, str]] = []
        buf: list[str] = []
        start: float | None = None
        for event in transcript.events:
            if event.segs is None:
                continue
            if start is None:
                start = event.tStartMs / 1000
            for snippet in event.segs:
                buf.append(snippet.utf8)
            end = event.tStartMs / 1000 + event.dDurationMs / 1000
            if end - start >= window:
                windows.append((start, end, " ".join(buf)))
                buf.clear()
                start = None
        if buf:
            windows.append((start, end, " ".join(buf)))
        return windows

    @staticmethod
    def _section_id_for_start(start: float, sections: list[YTEmbedderSection]) -> str:
        """The section that owns a segment starting at `start`.

        Sections partition the transcript chronologically, so the first one that
        has not ended yet (or the last one, past its end) owns the segment.
        """
        for section in sections:
            if start < section.end:
                return section.section_id
        return sections[-1].section_id

    def _chunk_transcript(
        self,
        transcript: YTDownloaderSubtitle,
        sections: list[YTEmbedderSection] | None = None,
        window: float = 30.0,
    ) -> list[dict[str, Any]]:
        sections = sections or []
        chunks: list[dict[str, Any]] = []
        for n, (start, end, text) in enumerate(
            self._windows(transcript, window), start=1
        ):
            chunks.append(
                {
                    "segment_id": self._generate_segment_id(n),
                    "text": text,
                    "video_id": self._video_id,
                    "start": start,
                    "end": end,
                    "language": self._language,
                    "section_id": (
                        self._section_id_for_start(start, sections) if sections else ""
                    ),
                }
            )
        return chunks

    def _split_sections(
        self, transcript: YTDownloaderSubtitle
    ) -> list[tuple[float, float, str]]:
        """The ~5-minute transcript windows that become this video's sections."""
        return self._windows(transcript, SECTION_WINDOW_SECONDS)

    async def _title_sections(
        self, windows: list[tuple[float, float, str]]
    ) -> TitleSectionsResult:
        """One batched LLM call: a title and summary per window, in window order."""
        blocks = "\n\n".join(
            f"Section {n}:\n{text}" for n, (_, _, text) in enumerate(windows, start=1)
        )
        result: TitleSectionsResult = await LLManager().process(
            "title_sections", sections=blocks
        )
        if len(result.sections) != len(windows):
            raise RuntimeError(
                f"title_sections returned {len(result.sections)} titles for "
                f"{len(windows)} sections of video {self._video_id}"
            )
        return result

    async def _sections(
        self, transcript: YTDownloaderSubtitle, duration: float
    ) -> list[YTEmbedderSection]:
        """This video's sections, or an empty list when it is not sectioned.

        A video shorter than the threshold is not sectioned at all. A long one
        reuses the section metadata cached next to the transcript (no LLM call)
        and only titles its windows when the cache is missing, corrupt, or out of
        step with the current windows.
        """
        if duration < SECTION_MIN_DURATION_SECONDS:
            return []
        windows = self._split_sections(transcript)
        cached = self._downloader.load_cached_sections()
        if cached is not None and len(cached) == len(windows):
            titled = cached
        else:
            titles = await self._title_sections(windows)
            titled = [
                YTDownloaderSection(
                    section_id=self._generate_section_id(n),
                    title=title.title,
                    summary=title.summary,
                    start=start,
                    end=end,
                )
                for n, ((start, end, _), title) in enumerate(
                    zip(windows, titles.sections), start=1
                )
            ]
            self._downloader.cache_sections(titled)
        return [
            YTEmbedderSection(
                video_id=self._video_id, language=self._language, **section.model_dump()
            )
            for section in titled
        ]

    def _store_transcript(
        self, transcript: YTDownloaderSubtitle, sections: list[YTEmbedderSection]
    ):
        chunks_lst = self._chunk_transcript(transcript, sections)
        where = f"video_id = '{self._video_id}' AND language = '{self._language}'"
        # Replace this video's segments and sections together. There is no
        # transaction, so delete first and store the sections before the chunks
        # that reference them.
        chunk_table.delete(where)
        section_table.delete(where)
        if sections:
            section_table.add([section.to_row() for section in sections])
        chunk_table.add(chunks_lst)

    async def init_video(self):
        started = perf_counter()
        fetched = self._downloader.fetch()
        fetched_at = perf_counter()
        sections = await self._sections(fetched.subtitle, fetched.duration)
        sectioned_at = perf_counter()
        self._store_transcript(fetched.subtitle, sections)
        print(
            f"[init] {self._video_id}/{self._language} fetch "
            f"{fetched_at - started:.1f}s, sections {sectioned_at - fetched_at:.1f}s "
            f"({len(sections)}), store+embed {perf_counter() - sectioned_at:.1f}s",
            flush=True,
        )

    def get_metadata(self):
        return YTEmbedderMetadata(video_id=self._video_id, language=self._language)

    def select_sections(
        self, question: str, limit: int = SECTION_SELECTION_LIMIT
    ) -> list[str]:
        """The sections whose titles and summaries are closest to the question.

        Unconditional top `limit`, no similarity threshold. An unsectioned video
        yields an empty list, which leaves retrieval over the whole video.
        """
        hits = (
            section_table.search(question)
            .where(f"video_id = '{self._video_id}' AND language = '{self._language}'")
            .limit(limit)
            .to_list()
        )
        return [YTEmbedderSection(**hit).section_id for hit in hits]

    def search(
        self, question: str, limit: int = 5, section_ids: list[str] | None = None
    ) -> list[YTEmbedderChunk]:
        where = f"video_id = '{self._video_id}' AND language = '{self._language}'"
        if section_ids:
            ids = ", ".join(f"'{section_id}'" for section_id in section_ids)
            where += f" AND section_id IN ({ids})"
        hits = chunk_table.search(question).where(where).limit(limit).to_list()
        return [YTEmbedderChunk(**hit) for hit in hits]
