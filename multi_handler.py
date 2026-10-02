"""Route three modes through one RunPod queue endpoint.

The FLUX job still uses RunPod's pinned ComfyUI 5.10.0 handler. FaceFusion runs
in its own venv and uses only data from the current job, never local user paths.
"""

import base64
import binascii
import os
from pathlib import Path
import subprocess
import tempfile

import handler as comfy_handler
import runpod

FACEFUSION = Path("/opt/facefusion")
FACEFUSION_PYTHON = "/opt/facefusion-venv/bin/python"
MAX_INPUT_BYTES = 7 * 1024 * 1024  # /run has a 10 MB JSON request limit.
MAX_INLINE_OUTPUT_BYTES = 5 * 1024 * 1024  # Conservative until S3 is wired.
MODES = {"flux", "facefusion_photo", "facefusion_video"}


def decode_media(value, kind):
    if not isinstance(value, str) or not value:
        raise ValueError(f"{kind} must be a base64 data URI or base64 string")
    encoded = value.partition(",")[2] if value.startswith("data:") else value
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError(f"{kind} is invalid base64") from exc
    if not raw:
        raise ValueError(f"{kind} is empty")
    if kind == "image":
        if raw.startswith(b"\x89PNG\r\n\x1a\n"):
            return raw, ".png"
        if raw.startswith(b"\xff\xd8\xff"):
            return raw, ".jpg"
        if raw.startswith(b"RIFF") and raw[8:12] == b"WEBP":
            return raw, ".webp"
        raise ValueError("image must be PNG, JPEG, or WebP")
    if raw[4:8] == b"ftyp":
        return raw, ".mp4"
    raise ValueError("video must be MP4")


def count_video_frames(path):
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
         "-show_entries", "stream=nb_read_frames", "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True, timeout=120, check=False,
    )
    value = probe.stdout.strip()
    return int(value) if probe.returncode == 0 and value.isdigit() else None


def run_facefusion(payload, mode):
    try:
        source, source_ext = decode_media(payload.get("source_image"), "image")
        target_kind = "video" if mode == "facefusion_video" else "image"
        target, target_ext = decode_media(payload.get("target_media"), target_kind)
        if len(source) + len(target) > MAX_INPUT_BYTES:
            return {"error": "input_too_large", "details": "Combined files exceed 7 MiB raw; the RunPod /run JSON limit is 10 MB. Use a shorter or more compressed video until bucket input is configured."}
    except ValueError as exc:
        return {"error": "invalid_input", "details": str(exc)}

    with tempfile.TemporaryDirectory(prefix="facefusion-job-") as root:
        directory = Path(root)
        source_path = directory / f"source{source_ext}"
        target_path = directory / f"target{target_ext}"
        output_path = directory / f"result{target_ext}"
        source_path.write_bytes(source)
        target_path.write_bytes(target)
        command = [
            FACEFUSION_PYTHON, "facefusion.py", "headless-run",
            "--config-path", str(FACEFUSION / "facefusion.ini"),
            "--source-paths", str(source_path),
            "--target-path", str(target_path),
            "--output-path", str(output_path),
            "--temp-path", str(directory / "temp"),
            "--jobs-path", str(directory / "jobs"),
            "--execution-providers", "cuda",
        ]
        try:
            result = subprocess.run(
                command, cwd=FACEFUSION, capture_output=True, text=True,
                timeout=1800, check=False,
                env={**os.environ, "PYTHONUNBUFFERED": "1"},
            )
        except subprocess.TimeoutExpired:
            return {"error": "facefusion_timeout", "details": "FaceFusion exceeded 30 minutes"}
        print("facefusion exit code:", result.returncode, flush=True)
        print("facefusion log tail:", (result.stdout + result.stderr)[-6000:], flush=True)
        if result.returncode != 0 or not output_path.is_file():
            return {"error": "facefusion_failed", "exit_code": result.returncode,
                    "details": (result.stdout + result.stderr)[-3000:]}

        size = output_path.stat().st_size
        frame_count = count_video_frames(output_path) if target_kind == "video" else None
        if size > MAX_INLINE_OUTPUT_BYTES:
            return {"error": "output_too_large_bucket_required", "output_bytes": size,
                    "frame_count": frame_count,
                    "details": "Processing finished, but the result exceeds the temporary 5 MiB inline limit. Configure an S3-compatible bucket to retrieve full video outputs."}
        mime = "video/mp4" if target_kind == "video" else {
            ".png": "image/png", ".jpg": "image/jpeg", ".webp": "image/webp"
        }[target_ext]
        item = {"filename": output_path.name, "type": "base64", "mime": mime,
                "data": base64.b64encode(output_path.read_bytes()).decode("ascii")}
        if target_kind == "video":
            return {"videos": [item], "frame_count": frame_count,
                    "output_bytes": size}
        return {"images": [item], "output_bytes": size}


def route(job):
    payload = job.get("input")
    if not isinstance(payload, dict):
        return {"error": "invalid_input", "details": "input must be an object"}
    mode = payload.get("mode", "flux")
    if mode not in MODES:
        return {"error": "invalid_mode", "details": f"mode must be one of {sorted(MODES)}"}
    if mode == "flux":
        clean_job = {**job, "input": {key: value for key, value in payload.items() if key != "mode"}}
        return comfy_handler.handler(clean_job)
    return run_facefusion(payload, mode)


if __name__ == "__main__":
    runpod.serverless.start({"handler": route})
