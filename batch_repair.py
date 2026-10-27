#!/usr/bin/env python3
"""Repair corrupted JPEG, PNG, and BMP files in a folder.

Layers, in order:

1. Pillow truncated-scanline recovery. ``ImageFile.LOAD_TRUNCATED_IMAGES``
   lets Pillow keep readable MCU blocks. The image is re-encoded into a
   clean file (JPEG quality 95 by default). PNG alpha is preserved.
2. OpenCV matrix recovery. ``cv2.imdecode`` reads whatever macroblocks the
   hardware decoder can salvage, then writes a fresh stream.
3. JPEG container repair, only after both decoders refuse the original
   bytes:
   - marker cleanup (leading junk, a missing EOI, trailing junk)
   - header transplant from a reference photo shot on the same camera and
     at the same resolution. The reference supplies bytes from SOI
     (``FF D8``) through the first SOS segment (``FF DA``). The damaged
     file keeps its entropy-coded scan.

One bad file never stops the batch. Images are closed before the next file
is opened. ``--workers`` uses ``ThreadPoolExecutor``; each worker handles a
different file, and the reference header is read-only shared state.

Examples
--------
python batch_repair.py
python batch_repair.py --workers 4
python batch_repair.py --reference camera_sample.jpg

Install
-------
pip install -r requirements-repair.txt
"""

from __future__ import annotations

import argparse
import logging
import os
import shutil
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from io import BytesIO

import cv2
import numpy as np
from PIL import Image, ImageFile

__version__ = "1.0.0"

# Pillow would otherwise raise on a short scan and throw away readable blocks.
ImageFile.LOAD_TRUNCATED_IMAGES = True

logger = logging.getLogger("batch_repair")

JPEG_EXTENSIONS = (".jpg", ".jpeg")
SUPPORTED_EXTENSIONS = JPEG_EXTENSIONS + (".png", ".bmp")
MAX_WORKERS = 32

# SOF markers (baseline, extended, progressive, lossless, differential).
# DHT is C4, JPG is C8, DAC is CC — those are not frame headers.
_SOF_MARKERS = frozenset(
    {
        0xC0,
        0xC1,
        0xC2,
        0xC3,
        0xC5,
        0xC6,
        0xC7,
        0xC9,
        0xCA,
        0xCB,
        0xCD,
        0xCE,
        0xCF,
    }
)

_EPILOG = """
folders:
  input        ./corrupted_images
  repaired     ./repaired_images
  unrepairable ./unrepairable_images

examples:
  python batch_repair.py
  python batch_repair.py --workers 4 --quality 90
  python batch_repair.py --reference camera_sample.jpg
""".strip(
    "\n"
)


@dataclass(frozen=True)
class FileResult:
    """Outcome for a single input file."""

    filename: str
    status: str
    method: str = ""


@dataclass
class BatchSummary:
    """Counts and per-file results for one run."""

    total: int = 0
    success: int = 0
    failed: int = 0
    results: list[FileResult] = field(default_factory=list)
    elapsed_seconds: float = 0.0
    status: str = "ok"


@dataclass(frozen=True)
class JpegLayout:
    """Where the frame header and the first entropy-coded scan sit."""

    soi: int
    width: int | None
    height: int | None
    sos_index: int
    entropy_start: int


def configure_logging(verbose: bool = False, log_path: str | None = None) -> None:
    """Send human-readable lines to stdout and, optionally, a log file."""

    logger.handlers.clear()
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    logger.propagate = False

    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(stream)

    if log_path:
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(message)s")
        )
        logger.addHandler(file_handler)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="batch_repair.py",
        description=(
            "Repair corrupted JPEG, PNG, and BMP files. Pillow rebuilds "
            "truncated images first; OpenCV is the fallback. JPEG files that "
            "still will not open get marker cleanup and, with --reference, a "
            "same-camera header transplant (FF D8 through FF DA)."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=_EPILOG,
    )
    parser.add_argument(
        "--input",
        "-i",
        default="./corrupted_images",
        help="Folder of damaged images (default: ./corrupted_images)",
    )
    parser.add_argument(
        "--output",
        "-o",
        default="./repaired_images",
        help="Folder for repaired images (default: ./repaired_images)",
    )
    parser.add_argument(
        "--failed",
        "-f",
        default="./unrepairable_images",
        help="Folder for files neither decoder could open (default: ./unrepairable_images)",
    )
    parser.add_argument(
        "--reference",
        "-r",
        default=None,
        help=(
            "JPEG from the same camera and resolution. Its header (FF D8 "
            "through FF DA) replaces a header that will not parse."
        ),
    )
    parser.add_argument(
        "--workers",
        "-w",
        type=int,
        default=1,
        help=f"Parallel files to repair (1-{MAX_WORKERS}, default: 1)",
    )
    parser.add_argument(
        "--quality",
        "-q",
        type=int,
        default=95,
        help="JPEG quality tag written by both decoders (1-100, default: 95)",
    )
    parser.add_argument(
        "--move",
        action="store_true",
        help="Move unrepairable files instead of copying them",
    )
    parser.add_argument(
        "--log",
        default=None,
        help="Also append the run log to this file",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Log the decoder error behind each failed attempt",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"batch_repair {__version__}",
    )
    return parser.parse_args(argv)


def _same_path(left: str, right: str) -> bool:
    return os.path.normcase(os.path.abspath(left)) == os.path.normcase(
        os.path.abspath(right)
    )


def _read_bytes(path: str) -> bytes | None:
    try:
        with open(path, "rb") as handle:
            return handle.read()
    except OSError as exc:
        logger.debug("Could not read %s: %s", path, exc)
        return None


def _write_bytes(path: str, payload: bytes) -> None:
    """Atomically replace ``path`` so a reader never sees a partial image."""

    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=".repair-", suffix=".part", dir=directory)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _quarantine(src: str, dst: str, move_failures: bool) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(dst)) or ".", exist_ok=True)
    if os.path.exists(dst):
        os.remove(dst)
    if move_failures:
        shutil.move(src, dst)
        return
    with open(src, "rb") as source, open(dst, "wb") as target:
        shutil.copyfileobj(source, target, length=1024 * 1024)


def list_images(folder: str) -> list[str]:
    """Return supported image files directly inside ``folder``, sorted by name."""

    paths = []
    for name in os.listdir(folder):
        path = os.path.join(folder, name)
        if not os.path.isfile(path):
            continue
        if os.path.splitext(name)[1].lower() not in SUPPORTED_EXTENSIONS:
            continue
        paths.append(path)
    paths.sort(key=lambda item: os.path.basename(item).lower())
    return paths


def _valid_image_bytes(payload: bytes) -> bool:
    bio = BytesIO(payload)
    try:
        with Image.open(bio) as img:
            img.load()
            width, height = img.size
            return width > 0 and height > 0
    except Exception:
        return False
    finally:
        bio.close()


def _within_pixel_limit(width: int, height: int) -> bool:
    limit = Image.MAX_IMAGE_PIXELS
    if limit is None:
        return width > 0 and height > 0
    return width > 0 and height > 0 and width * height <= limit


def _png_working(img: Image.Image) -> Image.Image:
    """Return a PNG-safe image without dropping an alpha channel."""

    if img.mode in ("1", "L", "RGB", "RGBA", "LA"):
        return img
    if img.mode in ("P", "PA") and "transparency" in img.info:
        return img.convert("RGBA")
    if img.mode == "PA":
        return img.convert("RGBA")
    return img.convert("RGB")


def _encode_pillow(
    img: Image.Image,
    ext: str,
    quality: int,
    optimize: bool,
) -> bytes:
    out = BytesIO()
    extra: Image.Image | None = None
    try:
        if ext in JPEG_EXTENSIONS:
            working = img.convert("RGB")
            if working is not img:
                extra = working
            working.save(
                out,
                format="JPEG",
                quality=quality,
                optimize=optimize,
            )
        elif ext == ".png":
            working = _png_working(img)
            if working is not img:
                extra = working
            working.save(out, format="PNG", optimize=optimize)
        elif ext == ".bmp":
            working = img.convert("RGB")
            if working is not img:
                extra = working
            working.save(out, format="BMP")
        else:
            raise ValueError(f"unsupported extension: {ext}")
        return out.getvalue()
    finally:
        if extra is not None:
            extra.close()
        out.close()


def _encode_loaded(img: Image.Image, ext: str, quality: int) -> bytes | None:
    optimize_attempts = (True, False) if ext in JPEG_EXTENSIONS or ext == ".png" else (False,)
    for optimize in optimize_attempts:
        try:
            payload = _encode_pillow(img, ext, quality, optimize)
        except Exception as exc:
            logger.debug("Pillow encode failed (optimize=%s): %s", optimize, exc)
            continue
        if payload and _valid_image_bytes(payload):
            return payload
    return None


def _pillow_from_path(path: str, ext: str, quality: int) -> bytes | None:
    try:
        with Image.open(path) as img:
            img.load()
            return _encode_loaded(img, ext, quality)
    except Exception as exc:
        logger.debug("Pillow could not open %s: %s", os.path.basename(path), exc)
        return None


def _pillow_from_bytes(data: bytes, ext: str, quality: int) -> bytes | None:
    bio = BytesIO(data)
    try:
        with Image.open(bio) as img:
            img.load()
            return _encode_loaded(img, ext, quality)
    except Exception as exc:
        logger.debug("Pillow could not decode bytes: %s", exc)
        return None
    finally:
        bio.close()


def _opencv_encode(matrix: np.ndarray, ext: str, quality: int) -> bytes | None:
    if matrix.size == 0:
        return None
    height, width = matrix.shape[:2]
    if not _within_pixel_limit(width, height):
        logger.debug("Rejecting OpenCV image of %sx%s", width, height)
        return None

    working = np.ascontiguousarray(matrix)
    encode_ext = ext
    params: list[int] = []
    if ext in JPEG_EXTENSIONS:
        encode_ext = ".jpg"
        if working.ndim == 3 and working.shape[2] == 4:
            working = cv2.cvtColor(working, cv2.COLOR_BGRA2BGR)
        params = [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)]
    elif ext == ".png":
        params = [int(cv2.IMWRITE_PNG_COMPRESSION), 3]
    elif ext == ".bmp":
        if working.ndim == 3 and working.shape[2] == 4:
            working = cv2.cvtColor(working, cv2.COLOR_BGRA2BGR)
    else:
        return None

    try:
        ok, encoded = cv2.imencode(encode_ext, working, params)
    except cv2.error as exc:
        logger.debug("OpenCV encode failed: %s", exc)
        return None
    if not ok:
        return None
    payload = encoded.tobytes()
    if not _valid_image_bytes(payload):
        return None
    return payload


def _opencv_from_bytes(data: bytes, ext: str, quality: int) -> bytes | None:
    if not data:
        return None
    buffer = np.frombuffer(data, dtype=np.uint8)
    matrix = None
    try:
        try:
            matrix = cv2.imdecode(buffer, cv2.IMREAD_UNCHANGED)
        except cv2.error:
            matrix = cv2.imdecode(np.array(buffer), cv2.IMREAD_UNCHANGED)
    except Exception as exc:
        logger.debug("OpenCV decode failed: %s", exc)
        return None
    if matrix is None:
        return None
    try:
        return _opencv_encode(matrix, ext, quality)
    finally:
        del matrix


def _decode_both(data: bytes, ext: str, quality: int) -> tuple[bytes, str] | None:
    payload = _pillow_from_bytes(data, ext, quality)
    if payload:
        return payload, "pillow"
    payload = _opencv_from_bytes(data, ext, quality)
    if payload:
        return payload, "opencv"
    return None


def _inspect_jpeg(data: bytes) -> JpegLayout | None:
    """Walk markers from the first SOI through the first SOS segment.

    Segment lengths are honored, so an ``FF D9`` inside a comment or EXIF
    thumbnail is not treated as the end of the file. Returns ``None`` when
    the header is too damaged to walk.
    """

    if not data:
        return None
    soi = data.find(b"\xff\xd8")
    if soi < 0:
        return None

    width: int | None = None
    height: int | None = None
    index = soi + 2
    limit = len(data)
    while index + 1 < limit:
        if data[index] != 0xFF:
            return None
        while index < limit and data[index] == 0xFF:
            index += 1
        if index >= limit:
            return None
        marker = data[index]
        marker_index = index - 1
        index += 1
        if marker == 0x01 or 0xD0 <= marker <= 0xD7:
            continue
        if marker in (0x00, 0xD9):
            return None
        if index + 2 > limit:
            return None
        segment_length = int.from_bytes(data[index : index + 2], "big")
        if segment_length < 2 or index + segment_length > limit:
            return None
        if marker in _SOF_MARKERS and segment_length >= 7:
            parsed_height = int.from_bytes(data[index + 3 : index + 5], "big")
            parsed_width = int.from_bytes(data[index + 5 : index + 7], "big")
            if parsed_width > 0 and parsed_height > 0:
                width = parsed_width
                height = parsed_height
        if marker == 0xDA:
            entropy_start = index + segment_length
            return JpegLayout(soi, width, height, marker_index, entropy_start)
        index += segment_length
    return None


def _find_sos_fallback(data: bytes) -> tuple[int, int] | None:
    """Find a plausible SOS segment when the bytes before it will not parse.

    Baseline SOS lengths are 8, 10, 12, or 14 bytes. Anything outside a
    slightly wider band is treated as a coincidental ``FF DA`` in entropy
    data rather than a scan header.
    """

    start = 0
    while True:
        found = data.find(b"\xff\xda", start)
        if found < 0 or found + 4 > len(data):
            return None
        segment_length = int.from_bytes(data[found + 2 : found + 4], "big")
        entropy_start = found + 2 + segment_length
        if 8 <= segment_length <= 64 and entropy_start < len(data):
            return found, entropy_start
        start = found + 2


def _eoi_end(data: bytes) -> int | None:
    """Return the index just past a real EOI marker, if markers walk cleanly."""

    if len(data) < 4 or not data.startswith(b"\xff\xd8"):
        return None
    index = 2
    limit = len(data)
    while index + 1 < limit:
        if data[index] != 0xFF:
            return None
        while index < limit and data[index] == 0xFF:
            index += 1
        if index >= limit:
            return None
        marker = data[index]
        index += 1
        if marker == 0xD9:
            return index
        if marker == 0x01 or 0xD0 <= marker <= 0xD7:
            continue
        if marker == 0x00 or index + 2 > limit:
            return None
        segment_length = int.from_bytes(data[index : index + 2], "big")
        if segment_length < 2 or index + segment_length > limit:
            return None
        index += segment_length
        if marker != 0xDA:
            continue
        while index + 1 < limit:
            if data[index] != 0xFF:
                index += 1
                continue
            while index < limit and data[index] == 0xFF:
                index += 1
            if index >= limit:
                return None
            entropy_marker = data[index]
            index += 1
            if entropy_marker == 0x00:
                continue
            if entropy_marker == 0xD9:
                return index
            if entropy_marker == 0x01 or 0xD0 <= entropy_marker <= 0xD7:
                continue
            if index + 2 > limit:
                return None
            next_length = int.from_bytes(data[index : index + 2], "big")
            if next_length < 2 or index + next_length > limit:
                return None
            index += next_length
        return None
    return None


def normalize_jpeg_container(data: bytes) -> bytes | None:
    """Strip junk around a JPEG container and append a missing EOI.

    Returns ``None`` when ``data`` is already a clean container, or when it
    contains no SOI marker. Thumbnail EOI bytes that live inside an APP
    segment are left in place; only a marker-level EOI ends the container.
    """

    if not data:
        return None
    soi = data.find(b"\xff\xd8")
    if soi < 0:
        return None
    body = data[soi:]
    eoi_end = _eoi_end(body)
    if eoi_end is not None:
        body = body[:eoi_end]
    elif not body.endswith(b"\xff\xd9"):
        body = body + b"\xff\xd9"
    if body == data:
        return None
    return body


def transplant_jpeg_header(damaged: bytes, reference: bytes) -> bytes | None:
    """Replace the damaged header with the reference header.

    The reference must be a JPEG from the same sensor and the same pixel
    size. Its bytes from SOI (``FF D8``) through the first SOS segment
    (``FF DA``) are kept. The damaged file contributes the entropy-coded
    scan that follows its own SOS segment. When both frame headers still
    parse and their sizes differ, the transplant is refused.
    """

    if not damaged or not reference:
        return None
    ref_layout = _inspect_jpeg(reference)
    if ref_layout is None or ref_layout.entropy_start <= ref_layout.soi:
        return None

    damaged_layout = _inspect_jpeg(damaged)
    if damaged_layout is not None:
        if (
            ref_layout.width
            and ref_layout.height
            and damaged_layout.width
            and damaged_layout.height
            and (
                ref_layout.width != damaged_layout.width
                or ref_layout.height != damaged_layout.height
            )
        ):
            return None
        entropy_start = damaged_layout.entropy_start
    else:
        found = _find_sos_fallback(damaged)
        if found is None:
            return None
        entropy_start = found[1]

    scan = damaged[entropy_start:]
    if not scan:
        return None
    header = reference[ref_layout.soi : ref_layout.entropy_start]
    if not header.startswith(b"\xff\xd8"):
        return None
    rebuilt = header + scan
    if not rebuilt.endswith(b"\xff\xd9"):
        rebuilt += b"\xff\xd9"
    if rebuilt == damaged:
        return None
    return rebuilt


def _recover(
    path: str,
    ext: str,
    quality: int,
    reference: bytes | None,
) -> tuple[bytes, str] | None:
    payload = _pillow_from_path(path, ext, quality)
    if payload:
        return payload, "pillow"

    data = _read_bytes(path)
    if data is None:
        return None

    payload = _opencv_from_bytes(data, ext, quality)
    if payload:
        return payload, "opencv"

    if ext not in JPEG_EXTENSIONS:
        return None

    candidates: list[tuple[bytes, str]] = []
    normalized = normalize_jpeg_container(data)
    if normalized is not None:
        candidates.append((normalized, "markers"))
    if reference:
        transplanted = transplant_jpeg_header(data, reference)
        if transplanted is not None:
            candidates.append((transplanted, "header"))
        if normalized is not None:
            transplanted = transplant_jpeg_header(normalized, reference)
            if transplanted is not None and all(
                transplanted != current for current, _suffix in candidates
            ):
                candidates.append((transplanted, "header"))

    for candidate, suffix in candidates:
        recovered = _decode_both(candidate, ext, quality)
        if recovered:
            decoded, decoder = recovered
            return decoded, f"{decoder}-{suffix}"
    return None


def process_one(
    input_path: str,
    output_folder: str,
    error_folder: str,
    reference: bytes | None = None,
    quality: int = 95,
    move_failures: bool = False,
) -> FileResult:
    """Repair one file. Exceptions are contained so the batch can continue."""

    filename = os.path.basename(input_path)
    error_path = os.path.join(error_folder, filename)
    try:
        ext = os.path.splitext(filename)[1].lower()
        if ext not in SUPPORTED_EXTENSIONS:
            raise ValueError(f"unsupported extension: {ext}")
        recovered = _recover(input_path, ext, quality, reference)
        if recovered is None:
            _quarantine(input_path, error_path, move_failures)
            return FileResult(filename, "failed", "")
        payload, method = recovered
        _write_bytes(os.path.join(output_folder, filename), payload)
        return FileResult(filename, "repaired", method)
    except Exception as exc:
        logger.debug("Unexpected failure on %s: %s", filename, exc)
        try:
            if os.path.isfile(input_path):
                _quarantine(input_path, error_path, move_failures)
        except Exception as quarantine_error:
            logger.error(
                "Could not store %s in the unrepairable folder: %s",
                filename,
                quarantine_error,
            )
        return FileResult(filename, "failed", "")


def _log_result(index: int, total: int, result: FileResult, move_failures: bool) -> None:
    if result.status == "repaired":
        logger.info(
            "[%s/%s] REPAIRED: %s via %s",
            index,
            total,
            result.filename,
            result.method,
        )
        return
    action = "moved" if move_failures else "copied"
    logger.info(
        "[%s/%s] FAILED: %s (%s to unrepairable folder)",
        index,
        total,
        result.filename,
        action,
    )


def _empty_summary(status: str, started: float) -> BatchSummary:
    return BatchSummary(
        status=status,
        elapsed_seconds=time.perf_counter() - started,
    )


def process_batch(
    input_folder: str,
    output_folder: str,
    error_folder: str,
    reference_path: str | None = None,
    workers: int = 1,
    quality: int = 95,
    move_failures: bool = False,
) -> BatchSummary:
    """Repair every supported image in ``input_folder``.

    The first three arguments match the original batch helper. Extra
    behaviour is keyword-only at the call site when using the defaults:
    sequential repair, JPEG quality 95, and a copy of each failed file.
    """

    started = time.perf_counter()
    if workers < 1 or workers > MAX_WORKERS:
        logger.error("workers must be between 1 and %s", MAX_WORKERS)
        return _empty_summary("bad_arguments", started)
    if quality < 1 or quality > 100:
        logger.error("quality must be between 1 and 100")
        return _empty_summary("bad_arguments", started)
    if (
        _same_path(input_folder, output_folder)
        or _same_path(input_folder, error_folder)
        or _same_path(output_folder, error_folder)
    ):
        logger.error("Input, repaired, and unrepairable folders must be different")
        return _empty_summary("bad_arguments", started)

    if not os.path.isdir(input_folder):
        if os.path.exists(input_folder):
            logger.error("Input path is not a folder: %s", input_folder)
            return _empty_summary("bad_arguments", started)
        os.makedirs(input_folder, exist_ok=True)
        logger.error("Input folder did not exist and was created: %s", input_folder)
        logger.error("Add JPEG, PNG, or BMP files there and run the script again.")
        return _empty_summary("input_missing", started)

    reference: bytes | None = None
    if reference_path:
        reference = _read_bytes(reference_path)
        if reference is None or _inspect_jpeg(reference) is None:
            logger.error(
                "Reference image has no usable JPEG header: %s",
                reference_path,
            )
            return _empty_summary("bad_reference", started)

    try:
        os.makedirs(output_folder, exist_ok=True)
        os.makedirs(error_folder, exist_ok=True)
        files = list_images(input_folder)
    except OSError as exc:
        logger.error("Could not prepare folders: %s", exc)
        return _empty_summary("bad_arguments", started)

    total = len(files)
    logger.info("Input: %s", input_folder)
    logger.info("Repaired: %s", output_folder)
    logger.info("Unrepairable: %s", error_folder)
    logger.info("Found %s images to process...", total)
    logger.info("=" * 40)

    results: list[FileResult] = []
    if total == 0:
        pass
    elif workers == 1 or total == 1:
        for index, path in enumerate(files, start=1):
            result = process_one(
                path,
                output_folder,
                error_folder,
                reference,
                quality,
                move_failures,
            )
            results.append(result)
            _log_result(index, total, result, move_failures)
    else:
        pool_size = min(workers, total)
        with ThreadPoolExecutor(
            max_workers=pool_size,
            thread_name_prefix="repair",
        ) as executor:
            futures = [
                executor.submit(
                    process_one,
                    path,
                    output_folder,
                    error_folder,
                    reference,
                    quality,
                    move_failures,
                )
                for path in files
            ]
            completed = 0
            for future in as_completed(futures):
                completed += 1
                try:
                    result = future.result()
                except Exception as exc:
                    logger.debug("Worker failed: %s", exc)
                    result = FileResult("unknown", "failed", "")
                results.append(result)
                _log_result(completed, total, result, move_failures)

    success = sum(1 for item in results if item.status == "repaired")
    failed = sum(1 for item in results if item.status != "repaired")
    logger.info("=" * 40)
    logger.info("Batch Processing Complete!")
    logger.info("Successfully Processed: %s", success)
    logger.info("Failed / Completely Unreadable: %s", failed)
    if success:
        counts: dict[str, int] = {}
        for item in results:
            if item.status == "repaired" and item.method:
                counts[item.method] = counts.get(item.method, 0) + 1
        detail = ", ".join(f"{name}={counts[name]}" for name in sorted(counts))
        logger.info("By method: %s", detail)
    elapsed = time.perf_counter() - started
    logger.info("Elapsed: %.2f s", elapsed)
    return BatchSummary(
        total=total,
        success=success,
        failed=failed,
        results=results,
        elapsed_seconds=elapsed,
        status="ok",
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    configure_logging(verbose=args.verbose, log_path=args.log)
    summary = process_batch(
        args.input,
        args.output,
        args.failed,
        reference_path=args.reference,
        workers=args.workers,
        quality=args.quality,
        move_failures=args.move,
    )
    if summary.status == "ok":
        return 0 if summary.failed == 0 else 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
