from brain import yt_downloader
from brain.yt_downloader import YTDownloader, YTDownloaderSection
from brain.yt_embedder import YTEmbedder

WINDOWS = [(0.0, 300.0, "a"), (300.0, 600.0, "b")]


def _section(section_id: str, start: float, end: float) -> YTDownloaderSection:
    return YTDownloaderSection(
        section_id=section_id, title="t", summary="s", start=start, end=end
    )


def test_matching_ranges_are_reused():
    cached = [_section("sec1", 0.0, 300.0), _section("sec2", 300.0, 600.0)]

    assert YTEmbedder._cache_matches(cached, WINDOWS)


def test_different_ranges_are_not_reused():
    cached = [_section("sec1", 0.0, 250.0), _section("sec2", 250.0, 600.0)]

    assert not YTEmbedder._cache_matches(cached, WINDOWS)


def test_different_window_count_is_not_reused():
    cached = [_section("sec1", 0.0, 300.0)]

    assert not YTEmbedder._cache_matches(cached, WINDOWS)


def test_corrupt_section_cache_is_discarded(tmp_path, monkeypatch):
    monkeypatch.setattr(yt_downloader, "CACHE_DIR", tmp_path)
    cache_file = tmp_path / "dQw4w9WgXcQ.en.sections.json"
    cache_file.write_text("{not json", encoding="utf-8")

    assert YTDownloader("dQw4w9WgXcQ", "en").load_cached_sections() is None
    assert not cache_file.exists()
