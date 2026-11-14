"""Pure transcript math: window splitting and section lookup.

No database or embedding imports, so this module (and its tests) stays
lightweight.
"""

from collections.abc import Sequence
from typing import Protocol

from brain.yt_downloader import YTDownloaderSubtitle


class SectionLike(Protocol):
    end: float
    section_id: str


def windows(
    transcript: YTDownloaderSubtitle, window: float
) -> list[tuple[float, float, str]]:
    """Split caption events into consecutive `window`-second spans.

    Segments accumulate events until they span `window` seconds, then the
    next one starts at the following event; a final partial window is kept.
    """
    spans: list[tuple[float, float, str]] = []
    buf: list[str] = []
    start: float | None = None
    last_end = 0.0
    for event in transcript.events:
        if event.segs is None:
            continue
        if start is None:
            start = event.tStartMs / 1000
        for snippet in event.segs:
            buf.append(snippet.utf8)
        last_end = event.tStartMs / 1000 + event.dDurationMs / 1000
        if last_end - start >= window:
            spans.append((start, last_end, " ".join(buf)))
            buf.clear()
            start = None
    if buf and start is not None:
        spans.append((start, last_end, " ".join(buf)))
    return spans


def section_id_for_start(start: float, sections: Sequence[SectionLike]) -> str:
    """The section that owns a segment starting at `start`.

    Sections partition the transcript chronologically, so the first one that
    has not ended yet (or the last one, past its end) owns the segment.
    """
    for section in sections:
        if start < section.end:
            return section.section_id
    return sections[-1].section_id
