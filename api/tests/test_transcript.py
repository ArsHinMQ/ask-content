"""Tests for the pure transcript math in brain/transcript.py.

Deliberately avoids brain.db, so these run without loading the embedding model.
"""

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from brain.transcript import section_id_for_start, windows
from brain.yt_downloader import (
    YTDownloaderSubtitle,
    YTDownloaderSubtitleEvent,
    YTDownloaderSubtitleEventSegment,
)

REPO_API = Path(__file__).resolve().parents[1]


def _subtitle(*spans: tuple[float, float, str]) -> YTDownloaderSubtitle:
    """Build subtitle events from (start_seconds, end_seconds, text) spans."""
    events = []
    for start, end, text in spans:
        events.append(
            YTDownloaderSubtitleEvent(
                tStartMs=start * 1000,
                dDurationMs=(end - start) * 1000,
                segs=[YTDownloaderSubtitleEventSegment(utf8=text)],
            )
        )
    # a metadata event with no segs must be ignored, not crash
    events.append(YTDownloaderSubtitleEvent(tStartMs=0, dDurationMs=0, segs=None))
    return YTDownloaderSubtitle(events=events)


@dataclass
class _Section:
    end: float
    section_id: str


def test_thirty_second_windows():
    subtitle = _subtitle(
        (0, 10, "a"),
        (10, 20, "b"),
        (20, 30, "c"),
        (30, 40, "d"),
        (40, 50, "e"),
        (50, 60, "f"),
    )

    spans = windows(subtitle, 30.0)

    assert [(start, end) for start, end, _ in spans] == [(0, 30), (30, 60)]
    assert spans[0][2] == "a b c"


def test_trailing_partial_window_is_kept():
    subtitle = _subtitle((0, 10, "a"), (10, 20, "b"), (20, 30, "c"), (30, 40, "d"))

    spans = windows(subtitle, 30.0)

    assert [(start, end) for start, end, _ in spans] == [(0, 30), (30, 40)]
    assert spans[-1][2] == "d"


def test_empty_transcript_yields_no_windows():
    assert windows(_subtitle(), 30.0) == []


def test_section_owns_segment_by_start():
    sections = [
        _Section(end=300.0, section_id="sec1"),
        _Section(end=600.0, section_id="sec2"),
    ]

    assert section_id_for_start(0.0, sections) == "sec1"
    assert section_id_for_start(299.9, sections) == "sec1"
    assert section_id_for_start(300.0, sections) == "sec2"
    # past the last section's end, the last section owns the segment
    assert section_id_for_start(9999.0, sections) == "sec2"


def test_transcript_module_imports_without_the_database():
    # Run in a fresh interpreter so an earlier test importing main/brain.db
    # cannot mask whether brain.transcript alone pulls the database in.
    code = (
        "import sys; import brain.transcript; "
        "assert 'brain.db' not in sys.modules, 'brain.transcript pulled in brain.db'"
    )
    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=REPO_API,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
