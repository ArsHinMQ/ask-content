import main
from brain.yt_embedder import YTEmbedderMetadata
from fastapi.testclient import TestClient

client = TestClient(main.app)

VALID_ID = "dQw4w9WgXcQ"


def test_invalid_video_id_is_rejected():
    response = client.post("/init/short/en")
    assert response.status_code == 422


def test_invalid_language_is_rejected():
    response = client.post(f"/init/{VALID_ID}/EN")
    assert response.status_code == 422


def test_ask_rejects_invalid_identifiers():
    response = client.post("/ask/not-a-video-id/en", json={"question": "anything"})
    assert response.status_code == 422


def test_valid_identifiers_reach_the_handler(monkeypatch):
    seen: list[tuple[str, str]] = []

    class FakeEmbedder:
        def __init__(self, video_id: str, language: str):
            seen.append((video_id, language))

        async def init_video(self):
            pass

        def get_metadata(self):
            return YTEmbedderMetadata(video_id=seen[-1][0], language=seen[-1][1])

    monkeypatch.setattr(main, "YTEmbedder", FakeEmbedder)

    response = client.post(f"/init/{VALID_ID}/en-US")

    assert response.status_code == 200
    assert response.json() == {"video_id": VALID_ID, "language": "en-US"}
    assert seen == [(VALID_ID, "en-US")]
