"""Tests for the image repair web service."""

import io
import random
import re

from PIL import Image

from repair_web import app


def _jpeg_bytes():
    rng = random.Random(4)
    raw = bytes(rng.randrange(256) for _ in range(24 * 16 * 3))
    image = Image.frombytes("RGB", (24, 16), raw)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=85)
    image.close()
    return buffer.getvalue()


def _client(tmp_path):
    app.config["JOB_ROOT"] = str(tmp_path)
    return app.test_client()


def test_home_and_health(tmp_path):
    client = _client(tmp_path)
    home = client.get("/")
    assert home.status_code == 200
    assert b"Image repair" in home.data
    assert b"Repair images" in home.data
    assert b"Repair sample images" in home.data
    assert b"truncated.jpg" in home.data
    health = client.get("/health")
    assert health.status_code == 200
    assert health.get_json()["status"] == "ok"


def test_repair_upload_returns_a_download(tmp_path):
    client = _client(tmp_path)
    response = client.post(
        "/repair",
        data={
            "quality": "90",
            "images": (io.BytesIO(_jpeg_bytes()), "shot.jpg"),
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "shot.jpg" in page
    assert "Repaired" in page
    assert "Pillow" in page
    match = re.search(r'class="result-download" href="([^"]+)"', page)
    assert match is not None
    href = match.group(1)
    downloaded = client.get(href)
    assert downloaded.status_code == 200
    assert downloaded.data.startswith(b"\xff\xd8")
    with Image.open(io.BytesIO(downloaded.data)) as image:
        image.load()
        assert image.size == (24, 16)


def test_empty_and_unsupported_uploads_are_rejected(tmp_path):
    client = _client(tmp_path)
    empty = client.post("/repair", data={"quality": "95"}, content_type="multipart/form-data")
    assert empty.status_code == 400
    assert b"Choose at least one" in empty.data

    bad = client.post(
        "/repair",
        data={"images": (io.BytesIO(b"hello"), "notes.txt")},
        content_type="multipart/form-data",
    )
    assert bad.status_code == 400
    assert b"not a JPEG, PNG, or BMP" in bad.data


def test_sample_set_repairs_and_keeps_the_unreadable_file(tmp_path):
    client = _client(tmp_path)
    response = client.post("/samples/repair")
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "truncated.jpg" in page
    assert "broken-header.jpg" in page
    assert "Pillow, after header transplant" in page
    assert "unreadable.jpg" in page
    assert "Unreadable" in page
    sample = client.get("/samples/reference.jpg")
    assert sample.status_code == 200
    assert sample.data.startswith(b"\xff\xd8")
    missing = client.get("/samples/not-a-sample.jpg")
    assert missing.status_code == 404


def test_download_rejects_path_escape(tmp_path):
    client = _client(tmp_path)
    response = client.get("/jobs/not-a-job/repaired/shot.jpg")
    assert response.status_code == 404
    response = client.get("/jobs/" + ("a" * 32) + "/repaired/../secret.jpg")
    assert response.status_code == 404
