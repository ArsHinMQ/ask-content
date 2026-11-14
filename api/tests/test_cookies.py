import config
import pytest
from brain.yt_downloader import YTDownloader


def _settings(env_file):
    return config.Settings(_env_file=env_file)


def _write_env(path, *lines: str) -> None:
    path.write_text("OPENROUTER_API_KEY=test\n" + "\n".join(lines) + "\n", "utf-8")


def test_cookie_settings_load_from_env_file(tmp_path):
    env_file = tmp_path / "test.env"
    _write_env(
        env_file,
        "YT_COOKIES_FROM_BROWSER=firefox",
        f"YT_COOKIES_FILE={tmp_path / 'cookies.txt'}",
    )

    settings = _settings(env_file)

    assert settings.yt_cookies_from_browser == "firefox"
    assert settings.yt_cookies_file == str(tmp_path / "cookies.txt")


def test_browser_profile_takes_precedence(tmp_path, monkeypatch):
    env_file = tmp_path / "cookies.env"
    _write_env(
        env_file,
        "YT_COOKIES_FROM_BROWSER=firefox",
        f"YT_COOKIES_FILE={tmp_path / 'cookies.txt'}",
    )
    monkeypatch.setattr(config, "get_settings", lambda: _settings(env_file))

    assert YTDownloader._cookie_options() == {"cookiesfrombrowser": ("firefox",)}


def test_cookies_file_used_without_browser(tmp_path, monkeypatch):
    cookies = tmp_path / "cookies.txt"
    cookies.write_text("", encoding="utf-8")
    env_file = tmp_path / "cookies.env"
    _write_env(env_file, f"YT_COOKIES_FILE={cookies}")
    monkeypatch.setattr(config, "get_settings", lambda: _settings(env_file))

    assert YTDownloader._cookie_options() == {"cookiefile": str(cookies)}


def test_missing_cookies_file_raises(tmp_path, monkeypatch):
    env_file = tmp_path / "cookies.env"
    _write_env(env_file, f"YT_COOKIES_FILE={tmp_path / 'missing.txt'}")
    monkeypatch.setattr(config, "get_settings", lambda: _settings(env_file))

    with pytest.raises(RuntimeError, match="Cookies file not found"):
        YTDownloader._cookie_options()
