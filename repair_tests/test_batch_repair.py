"""Tests for the layered JPEG, PNG, and BMP repair tool."""

import io
import random
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image

from batch_repair import (
    ImageFile,
    _inspect_jpeg,
    main,
    normalize_jpeg_container,
    process_batch,
    transplant_jpeg_header,
)

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _isolate_logging():
    from batch_repair import logger

    logger.handlers.clear()
    logger.propagate = True
    yield
    logger.handlers.clear()
    logger.propagate = True


def _jpeg_bytes(size=(48, 32), color=(20, 140, 220), noise=False, quality=85, progressive=False):
    if noise:
        rng = random.Random(1)
        raw = bytes(rng.randrange(256) for _ in range(size[0] * size[1] * 3))
        image = Image.frombytes("RGB", size, raw)
    else:
        image = Image.new("RGB", size, color)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=quality, progressive=progressive)
    image.close()
    return buffer.getvalue()


def _png_bytes(mode="RGB", color=(12, 80, 200, 128)):
    image = Image.new(mode, (16, 10), color if mode == "RGBA" else color[:3])
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    image.close()
    return buffer.getvalue()


def _bmp_bytes():
    image = Image.new("RGB", (10, 12), (1, 2, 3))
    buffer = io.BytesIO()
    image.save(buffer, format="BMP")
    image.close()
    return buffer.getvalue()


def _dirs(tmp_path):
    source = tmp_path / "in"
    repaired = tmp_path / "out"
    failed = tmp_path / "bad"
    source.mkdir()
    return source, repaired, failed


def _run(source, repaired, failed, **kwargs):
    return process_batch(str(source), str(repaired), str(failed), **kwargs)


def test_truncated_images_flag_is_enabled():
    assert ImageFile.LOAD_TRUNCATED_IMAGES is True


def _strip_to_sos(data: bytes) -> bytes:
    layout = _inspect_jpeg(data)
    assert layout is not None
    return data[layout.sos_index :]


def test_pillow_repairs_truncated_jpeg_and_keeps_color(tmp_path):
    source, repaired, failed = _dirs(tmp_path)
    original = _jpeg_bytes(size=(96, 96), noise=True, quality=95)
    layout = _inspect_jpeg(original)
    assert layout is not None
    scan_length = len(original) - layout.entropy_start
    # Drop the tail of the entropy scan and keep the header intact.
    (source / "cut.jpg").write_bytes(
        original[: layout.entropy_start + max(64, scan_length // 4)]
    )
    with Image.open(io.BytesIO(original)) as intact:
        intact.load()
        expected = intact.getpixel((4, 4))

    summary = _run(source, repaired, failed)

    assert summary.status == "ok"
    assert summary.success == 1
    assert summary.failed == 0
    assert summary.results[0].method in {"pillow", "pillow-scanlines"}
    with Image.open(repaired / "cut.jpg") as repaired_image:
        repaired_image.load()
        assert repaired_image.size == (96, 96)
        actual = repaired_image.getpixel((4, 4))
        assert all(abs(left - right) <= 20 for left, right in zip(actual, expected))


def test_truncated_sample_fills_the_gray_gap(tmp_path):
    source, repaired, failed = _dirs(tmp_path)
    original = (Path(__file__).resolve().parents[1] / "samples" / "truncated.jpg").read_bytes()
    (source / "truncated.jpg").write_bytes(original)

    summary = _run(source, repaired, failed)

    assert summary.success == 1
    assert summary.results[0].method == "pillow-scanlines"
    with Image.open(repaired / "truncated.jpg") as image:
        image.load()
        assert image.size == (160, 100)
        assert image.getpixel((8, 4))[0] > 180
        bottom = image.getpixel((80, 90))
        assert bottom != (128, 128, 128)
        assert bottom[2] > bottom[0]


def test_png_alpha_and_bmp_round_trip(tmp_path):
    source, repaired, failed = _dirs(tmp_path)
    png = _png_bytes(mode="RGBA")
    bmp = _bmp_bytes()
    (source / "mark.png").write_bytes(png)
    (source / "plate.bmp").write_bytes(bmp)
    (source / "notes.txt").write_text("not an image")

    summary = _run(source, repaired, failed)

    assert summary.total == 2
    assert summary.success == 2
    with Image.open(repaired / "mark.png") as image:
        image.load()
        assert image.mode == "RGBA"
        assert image.size == (16, 10)
        assert image.getpixel((1, 1))[3] == 128
    with Image.open(repaired / "plate.bmp") as image:
        image.load()
        assert image.size == (10, 12)
    assert (source / "mark.png").read_bytes() == png


def test_unreadable_file_is_copied_and_batch_continues(tmp_path):
    source, repaired, failed = _dirs(tmp_path)
    (source / "ok.png").write_bytes(_png_bytes())
    (source / "bad.jpg").write_bytes(b"this is not a jpeg")
    (source / "skip.txt").write_bytes(b"ignore")

    summary = _run(source, repaired, failed)

    assert summary.total == 2
    assert summary.success == 1
    assert summary.failed == 1
    assert (repaired / "ok.png").is_file()
    assert not (repaired / "bad.jpg").exists()
    assert (failed / "bad.jpg").read_bytes() == b"this is not a jpeg"
    assert (source / "bad.jpg").read_bytes() == b"this is not a jpeg"


def test_move_failures_removes_the_source(tmp_path):
    source, repaired, failed = _dirs(tmp_path)
    (source / "bad.jpg").write_bytes(b"nope")

    summary = _run(source, repaired, failed, move_failures=True)

    assert summary.failed == 1
    assert not (source / "bad.jpg").exists()
    assert (failed / "bad.jpg").read_bytes() == b"nope"


def test_header_transplant_rebuilds_a_headerless_jpeg(tmp_path):
    good = _jpeg_bytes(size=(48, 32), noise=True)
    assert good.startswith(b"\xff\xd8")
    layout = _inspect_jpeg(good)
    assert layout is not None
    assert (layout.width, layout.height) == (48, 32)
    stripped = _strip_to_sos(good)
    assert transplant_jpeg_header(stripped, good) == good

    source, repaired, failed = _dirs(tmp_path)
    reference = tmp_path / "camera.jpg"
    reference.write_bytes(good)
    (source / "broken.jpg").write_bytes(b"\x00\x01GARBAGE" + stripped)

    summary = _run(source, repaired, failed, reference_path=str(reference))

    assert summary.success == 1
    assert summary.failed == 0
    assert summary.results[0].method.endswith("-header")
    with Image.open(repaired / "broken.jpg") as image:
        image.load()
        assert image.size == (48, 32)


def test_transplant_rejects_a_different_frame_size():
    small = _jpeg_bytes(size=(16, 16), color=(1, 2, 3))
    large = _jpeg_bytes(size=(32, 24), color=(4, 5, 6))
    assert transplant_jpeg_header(small, large) is None


def test_normalize_jpeg_container_keeps_real_markers():
    good = _jpeg_bytes(size=(40, 24), noise=True)
    progressive = _jpeg_bytes(size=(40, 24), noise=True, progressive=True)
    assert good.startswith(b"\xff\xd8") and good.endswith(b"\xff\xd9")

    assert normalize_jpeg_container(good) is None
    assert normalize_jpeg_container(b"abc" + good + b"xyz") == good
    assert normalize_jpeg_container(good[:-2]) == good
    assert normalize_jpeg_container(good + b"not-a-jpeg\xff\xd9") == good
    assert normalize_jpeg_container(b"Q" + progressive + b"Z") == progressive
    assert transplant_jpeg_header(_strip_to_sos(progressive), progressive) == progressive

    comment = b"xx\xff\xd9yy"
    segment = b"\xff\xfe" + (2 + len(comment)).to_bytes(2, "big") + comment
    stuffed = good[:2] + segment + good[2:]
    assert normalize_jpeg_container(b"LEAD" + stuffed + b"TRAIL") == stuffed


def test_leading_and_trailing_junk_uses_marker_cleanup(tmp_path):
    source, repaired, failed = _dirs(tmp_path)
    good = _jpeg_bytes(size=(48, 32), noise=True)
    (source / "dirty.jpg").write_bytes(b"GARBAGE" + good + b"TRAILER")

    summary = _run(source, repaired, failed)

    assert summary.success == 1
    assert summary.results[0].method == "pillow-markers"
    with Image.open(repaired / "dirty.jpg") as image:
        image.load()
        assert image.size == (48, 32)


def test_opencv_fallback_when_pillow_cannot_decode(tmp_path, monkeypatch):
    monkeypatch.setattr("batch_repair._pillow_from_path", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("batch_repair._pillow_from_bytes", lambda *_args, **_kwargs: None)
    source, repaired, failed = _dirs(tmp_path)
    (source / "shot.jpg").write_bytes(_jpeg_bytes(size=(48, 32), noise=True))

    summary = _run(source, repaired, failed)

    assert summary.success == 1
    assert summary.failed == 0
    assert summary.results[0].method == "opencv"
    with Image.open(repaired / "shot.jpg") as image:
        image.load()
        assert image.size == (48, 32)


def test_uppercase_jpeg_extension_is_kept(tmp_path):
    source, repaired, failed = _dirs(tmp_path)
    (source / "Photo.JPG").write_bytes(_jpeg_bytes())

    summary = _run(source, repaired, failed)

    assert summary.success == 1
    assert (repaired / "Photo.JPG").is_file()
    assert not (repaired / "Photo.jpg").exists()


def test_parallel_workers_repair_every_file(tmp_path):
    source, repaired, failed = _dirs(tmp_path)
    for index in range(8):
        (source / f"frame-{index}.png").write_bytes(_png_bytes())

    summary = _run(source, repaired, failed, workers=4)

    assert summary.success == 8
    assert summary.failed == 0
    assert len(list(repaired.glob("*.png"))) == 8


def test_empty_folder_succeeds_and_same_folder_is_rejected(tmp_path):
    source, repaired, failed = _dirs(tmp_path)
    empty = _run(source, repaired, failed)
    assert empty.status == "ok"
    assert empty.total == 0
    assert empty.success == 0

    rejected = process_batch(str(source), str(source), str(failed))
    assert rejected.status == "bad_arguments"


def test_missing_input_is_created(tmp_path):
    missing = tmp_path / "corrupted_images"
    summary = process_batch(
        str(missing),
        str(tmp_path / "out"),
        str(tmp_path / "bad"),
    )
    assert summary.status == "input_missing"
    assert missing.is_dir()


def test_bad_reference_stops_before_the_batch(tmp_path):
    source, repaired, failed = _dirs(tmp_path)
    (source / "ok.png").write_bytes(_png_bytes())
    reference = tmp_path / "ref.png"
    reference.write_bytes(_png_bytes())

    summary = _run(source, repaired, failed, reference_path=str(reference))

    assert summary.status == "bad_reference"
    assert summary.total == 0
    assert not (repaired / "ok.png").exists()


def test_cli_reports_repaired_and_failed_files(tmp_path):
    source, repaired, failed = _dirs(tmp_path)
    (source / "ok.jpg").write_bytes(_jpeg_bytes())
    (source / "bad.jpg").write_bytes(b"nope")
    log_path = tmp_path / "run.log"

    code = main(
        [
            "--input",
            str(source),
            "--output",
            str(repaired),
            "--failed",
            str(failed),
            "--log",
            str(log_path),
            "--quality",
            "90",
        ]
    )

    assert code == 1
    text = log_path.read_text(encoding="utf-8")
    assert "REPAIRED: ok.jpg via pillow" in text
    assert "FAILED: bad.jpg (copied to unrepairable folder)" in text
    assert "Successfully Processed: 1" in text
    assert "Failed / Completely Unreadable: 1" in text
    assert "Batch Processing Complete!" in text


def test_cli_help_lists_the_default_folders():
    result = subprocess.run(
        [sys.executable, str(ROOT / "batch_repair.py"), "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "corrupted_images" in result.stdout
    assert "repaired_images" in result.stdout
    assert "unrepairable_images" in result.stdout
    assert "workers" in result.stdout


def test_cli_rejects_a_quality_outside_the_jpeg_range():
    with pytest.raises(SystemExit) as caught:
        main(["--quality", "0"])
    assert caught.value.code == 2
