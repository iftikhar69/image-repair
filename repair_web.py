#!/usr/bin/env python3
"""Web front end for batch image repair.

Render starts this with gunicorn. Locally:

    python repair_web.py

Then open http://127.0.0.1:8765
"""

from __future__ import annotations

import os
import re
import shutil
import tempfile
import time
import uuid
from pathlib import Path

from flask import Flask, abort, render_template, request, send_file
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.utils import secure_filename

from batch_repair import JPEG_EXTENSIONS, SUPPORTED_EXTENSIONS, process_batch

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024
app.config["JOB_ROOT"] = str(Path(tempfile.gettempdir()) / "image-repair-jobs")

_JOB_ID = re.compile(r"[0-9a-f]{32}")
_STORED_NAME = re.compile(r"[A-Za-z0-9._-]{1,180}")
_BUCKETS = {"repaired", "failed"}


def _job_root() -> Path:
    root = Path(app.config["JOB_ROOT"])
    root.mkdir(parents=True, exist_ok=True)
    return root


def _purge_old_jobs(root: Path) -> None:
    cutoff = time.time() - 60 * 60
    for path in root.iterdir():
        try:
            if path.is_dir() and path.stat().st_mtime < cutoff:
                shutil.rmtree(path, ignore_errors=True)
        except OSError:
            continue


def _unique_name(original: str, used: set[str], fallback_stem: str) -> str:
    ext = os.path.splitext(original)[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        ext = ".jpg"
    cleaned = secure_filename(original)
    stem = os.path.splitext(cleaned)[0] or fallback_stem
    candidate = f"{stem}{ext}"
    number = 2
    while candidate.lower() in used:
        candidate = f"{stem}-{number}{ext}"
        number += 1
    used.add(candidate.lower())
    return candidate


def _page(error: str | None = None, job: dict | None = None, status: int = 200):
    return render_template("index.html", error=error, job=job), status


@app.get("/")
def index():
    return _page()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/repair")
def repair():
    quality_raw = (request.form.get("quality") or "95").strip()
    try:
        quality = int(quality_raw)
    except ValueError:
        return _page("Quality must be a whole number from 1 to 100.", status=400)
    if quality < 1 or quality > 100:
        return _page("Quality must be a whole number from 1 to 100.", status=400)

    uploads = [
        item
        for item in request.files.getlist("images")
        if item and item.filename
    ]
    if not uploads:
        return _page("Choose at least one JPEG, PNG, or BMP file.", status=400)

    root = _job_root()
    _purge_old_jobs(root)
    job_id = uuid.uuid4().hex
    job_dir = root / job_id
    incoming = job_dir / "incoming"
    repaired = job_dir / "repaired"
    failed = job_dir / "failed"
    incoming.mkdir(parents=True)
    used: set[str] = set()
    saved = 0
    try:
        for index, upload in enumerate(uploads, start=1):
            ext = os.path.splitext(upload.filename)[1].lower()
            if ext not in SUPPORTED_EXTENSIONS:
                shutil.rmtree(job_dir, ignore_errors=True)
                return _page(
                    f"{upload.filename} is not a JPEG, PNG, or BMP file.",
                    status=400,
                )
            name = _unique_name(upload.filename, used, f"image-{index}")
            upload.save(incoming / name)
            saved += 1

        reference_path = None
        reference = request.files.get("reference")
        if reference and reference.filename:
            ref_ext = os.path.splitext(reference.filename)[1].lower()
            if ref_ext not in JPEG_EXTENSIONS:
                shutil.rmtree(job_dir, ignore_errors=True)
                return _page(
                    "The reference file must be a JPEG from the same camera and size.",
                    status=400,
                )
            reference_path = str(job_dir / "reference.jpg")
            reference.save(reference_path)
    except OSError:
        shutil.rmtree(job_dir, ignore_errors=True)
        return _page("A file could not be stored. Try a smaller batch.", status=400)

    if saved == 0:
        shutil.rmtree(job_dir, ignore_errors=True)
        return _page("Choose at least one JPEG, PNG, or BMP file.", status=400)

    summary = process_batch(
        str(incoming),
        str(repaired),
        str(failed),
        reference_path=reference_path,
        workers=1,
        quality=quality,
    )
    if summary.status == "bad_reference":
        return _page(
            "That reference JPEG has no usable header. Use a photo that still opens.",
            job=_job_view(job_id, summary),
            status=400,
        )
    if summary.status != "ok":
        return _page(
            "The batch could not be started. Check the files and try again.",
            status=400,
        )
    return _page(job=_job_view(job_id, summary))


def _job_view(job_id: str, summary) -> dict:
    rows = []
    for item in summary.results:
        bucket = "repaired" if item.status == "repaired" else "failed"
        rows.append(
            {
                "filename": item.filename,
                "status": item.status,
                "method": item.method,
                "bucket": bucket,
                "job_id": job_id,
            }
        )
    return {
        "id": job_id,
        "total": summary.total,
        "success": summary.success,
        "failed": summary.failed,
        "elapsed": f"{summary.elapsed_seconds:.2f}",
        "rows": rows,
    }


@app.get("/jobs/<job_id>/<bucket>/<filename>")
def download(job_id: str, bucket: str, filename: str):
    if not _JOB_ID.fullmatch(job_id) or bucket not in _BUCKETS:
        abort(404)
    if not _STORED_NAME.fullmatch(filename):
        abort(404)
    folder = (_job_root() / job_id / bucket).resolve()
    path = (folder / filename).resolve()
    if folder not in path.parents or not path.is_file():
        abort(404)
    return send_file(path, as_attachment=True, download_name=filename)


@app.errorhandler(RequestEntityTooLarge)
def too_large(_error):
    return _page("That upload is larger than 32 MB. Split it into smaller batches.", status=413)


def main() -> None:
    port = int(os.environ.get("PORT", "8765"))
    app.run(host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
