import json
import os
import pathlib
import tempfile

import yt_dlp
from pydantic import BaseModel

# Static cookie exports go stale fast (YouTube rotates __Secure-*PSIDTS server
# side) and then get answered with a bot check, so prefer reading cookies LIVE
# from a real browser profile: set YT_COOKIES_FROM_BROWSER=firefox (chrome,
# brave, edge, ...). It takes precedence over COOKIES_FILE when set; otherwise
# the cookies file below is used.
COOKIES_FROM_BROWSER = os.environ.get("YT_COOKIES_FROM_BROWSER") or None

# Anchored to the repo root (api/brain/yt_downloader.py -> parents[2]) so it does
# NOT depend on the process's working directory: the server runs from api/
# Override with the YT_COOKIES_FILE env var if needed.
COOKIES_FILE = pathlib.Path(
    os.environ.get(
        "YT_COOKIES_FILE",
        str(pathlib.Path(__file__).resolve().parents[2] / "cookies.txt"),
    )
)

# Per-video transcript cache (same idea as temp.py's transcripts/ dir): hit
# YouTube once per video, then serve from disk. Filename includes the language
CACHE_DIR = pathlib.Path(__file__).resolve().parents[2] / "transcripts"

OPTS = {
    "quiet": True,
    "no_warnings": False,
    "skip_download": True,
    "ignore_no_formats_error": True,  # we only want captions, not video formats
    "writesubtitles": True,  # human-made captions if they exist
    "writeautomaticsub": True,  # fall back to auto-generated
    "subtitlesformat": "json3",
}

# Models only conatin fields that are relevant to our use case. The actual data returned by yt-dlp has many more fields, but we don't need them.
class YTDownloaderSubtitleEventSegment(BaseModel):
    utf8: str


class YTDownloaderSubtitleEvent(BaseModel):
    tStartMs: float
    dDurationMs: float = 0.0  # some events (e.g. window close) have no duration
    segs: list[YTDownloaderSubtitleEventSegment] | None = (
        None  # window/metadata events have no segs; each seg has "utf8": str
    )


class YTDownloaderSubtitle(BaseModel):
    events: list[YTDownloaderSubtitleEvent]


class YTDownloaderResult(BaseModel):
    """A fetched transcript plus the metadata init needs to section it."""

    duration: float  # video length in seconds, straight from the YouTube metadata
    subtitle: YTDownloaderSubtitle


class YTDownloaderSection(BaseModel):
    """Section metadata cached next to the transcript (title, summary, range)."""

    section_id: str
    title: str
    summary: str
    start: float
    end: float


class YTDownloaderSections(BaseModel):
    sections: list[YTDownloaderSection]


class _CapturingLogger:
    """Collects yt-dlp log lines so failures can report the actual reason.

    yt-dlp reports detail only through these lines: extraction can raise before
    any subtitle file exists (bot check, unavailable video), and
    ignore_no_formats_error downgrades a missing-formats failure to a warning
    while still writing no captions.
    """

    def __init__(self) -> None:
        self.lines: list[str] = []

    @staticmethod
    def _fmt(msg: str, *args: object) -> str:
        try:
            return msg % args if args else msg
        except Exception:
            return msg

    def debug(self, msg: str, *args: object) -> None:
        if "[debug]" not in msg[:9]:  # skip yt-dlp's noisy [debug] lines
            self.lines.append(self._fmt(msg, *args))

    def warning(self, msg: str, *args: object) -> None:
        self.lines.append("WARNING: " + self._fmt(msg, *args))

    def error(self, msg: str, *args: object) -> None:
        self.lines.append("ERROR: " + self._fmt(msg, *args))


class YTDownloader:
    _video_id: str
    _language: str

    def __init__(self, video_id: str, language: str):
        self._video_id = video_id
        self._language = language

    def fetch(self) -> YTDownloaderResult:
        """Fetch the video's captions and duration, cached on disk per language.

        Returns the parsed subtitle events together with the video duration in
        seconds, so init can decide whether to section the video. The cache is
        `CACHE_DIR/{video_id}.{language}.json`: a hit returns both without
        touching YouTube, a corrupt entry is discarded and fetched again.
        """
        cache_file = CACHE_DIR / f"{self._video_id}.{self._language}.json"
        if cache_file.exists():
            try:
                return YTDownloaderResult.model_validate(
                    json.loads(cache_file.read_text(encoding="utf-8"))
                )
            except Exception:
                cache_file.unlink(missing_ok=True)  # corrupt cache -> refetch

        url = f"https://www.youtube.com/watch?v={self._video_id}"
        with tempfile.TemporaryDirectory() as tmp:
            opts = OPTS.copy()
            opts["subtitleslangs"] = [
                f"{self._language}.*"
            ]  # matches en, en-orig, en-US, ...
            opts["outtmpl"] = f"{tmp}/%(id)s"
            if COOKIES_FROM_BROWSER:
                opts["cookiesfrombrowser"] = (COOKIES_FROM_BROWSER,)
            else:
                if not COOKIES_FILE.exists():
                    raise RuntimeError(
                        f"Cookies file not found: {COOKIES_FILE}\n"
                        "Set YT_COOKIES_FROM_BROWSER=firefox to read cookies live "
                        "from a browser logged into YouTube, or point the "
                        "YT_COOKIES_FILE env var at an existing cookies file."
                    )
                opts["cookiefile"] = str(COOKIES_FILE)
            logger = _CapturingLogger()
            opts["logger"] = logger

            with yt_dlp.YoutubeDL(opts) as ydl:
                # extract_info(download=True) writes the subtitle files (same
                # options as a plain download) and hands back the metadata dict,
                # which carries the video duration; skip_download=True in OPTS
                # keeps the video itself off disk.
                try:
                    info = ydl.extract_info(url, download=True)
                except yt_dlp.utils.DownloadError as exc:
                    raise RuntimeError(self._fetch_error_message(logger, exc)) from exc

            files = sorted(pathlib.Path(tmp).glob(f"{self._video_id}.*.json3"))
            if not files:
                raise RuntimeError(self._fetch_error_message(logger))

            # prefer the plain language track (e.g. ".en.json3") over variants like ".en-orig"
            chosen = next(
                (
                    f
                    for f in files
                    if f.name == f"{self._video_id}.{self._language}.json3"
                ),
                files[0],
            )
            data = json.loads(chosen.read_text(encoding="utf-8"))
        result = YTDownloaderResult(
            duration=float((info or {}).get("duration") or 0.0),
            subtitle=YTDownloaderSubtitle.model_validate(data),
        )
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(result.model_dump_json(), encoding="utf-8")
        return result

    def _fetch_error_message(
        self, logger: "_CapturingLogger", error: Exception | None = None
    ) -> str:
        """Diagnostic text for a failed fetch; yt-dlp only reports detail in logs."""
        log_tail = "\n".join(f"  | {line}" for line in logger.lines[-15:])
        hint = ""
        if any("not a bot" in line.lower() for line in logger.lines):
            hint = (
                "\nYouTube answered with a bot check ('Sign in to confirm "
                "you're not a bot'). Static cookie exports go stale fast; "
                "set YT_COOKIES_FROM_BROWSER=firefox (or your browser) to use "
                "live cookies, or re-export fresh cookies from a browser where "
                "you are logged into YouTube. If the block persists, this "
                "IP/account is rate-limited - wait a while and retry."
            )
        intro = (
            f"No captions downloaded for {self._video_id} "
            f"(language={self._language!r})."
            if error is None
            else f"yt-dlp failed for {self._video_id} "
            f"(language={self._language!r}): {error}"
        )
        return (
            f"{intro}\n"
            f"cookies file: {COOKIES_FILE} (exists: {COOKIES_FILE.exists()})\n"
            f"yt-dlp log tail:\n{log_tail or '  | (no log output)'}{hint}"
        )

    @property
    def _sections_cache_file(self) -> pathlib.Path:
        return CACHE_DIR / f"{self._video_id}.{self._language}.sections.json"

    def load_cached_sections(self) -> list[YTDownloaderSection] | None:
        """Section metadata from a previous init, or None when unusable.

        A corrupt cache entry is discarded so the next init regenerates it.
        """
        cache_file = self._sections_cache_file
        if not cache_file.exists():
            return None
        try:
            return YTDownloaderSections.model_validate(
                json.loads(cache_file.read_text(encoding="utf-8"))
            ).sections
        except Exception:
            cache_file.unlink(missing_ok=True)  # corrupt cache -> regenerate
            return None

    def cache_sections(self, sections: list[YTDownloaderSection]) -> None:
        """Persist section metadata next to the transcript cache."""
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self._sections_cache_file.write_text(
            YTDownloaderSections(sections=sections).model_dump_json(),
            encoding="utf-8",
        )
