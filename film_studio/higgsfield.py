"""Higgsfield platform client — image and video generation with polling."""

from __future__ import annotations

import random
import time
from pathlib import Path

import requests

from .config import HIGGSFIELD_BASE, TERMINAL_STATUS, higgsfield_auth, load_env


class HiggsfieldError(RuntimeError):
    pass


def _headers() -> dict:
    auth = higgsfield_auth()
    if not auth:
        raise HiggsfieldError("HF_API_KEY_ID/HF_API_KEY_SECRET missing in .env")
    return {"Authorization": auth, "Content-Type": "application/json"}


def submit(model_path: str, prompt: str, timeout: float = 90.0) -> tuple[str, str]:
    """Submit a job; return (request_id, status_url)."""
    load_env()
    resp = requests.post(
        HIGGSFIELD_BASE + model_path,
        headers=_headers(),
        json={"prompt": prompt},
        timeout=timeout,
    )
    if resp.status_code >= 400:
        raise HiggsfieldError(f"submit failed ({resp.status_code}): {resp.text[:300]}")
    data = resp.json()
    return data.get("request_id", ""), data.get("status_url", "")


def wait(status_url: str, on_status=None, timeout_s: float = 1800.0) -> dict:
    """Poll status_url until a terminal state; calls on_status(status) on change."""
    delay = 2.0
    deadline = time.time() + timeout_s
    last = ""
    while time.time() < deadline:
        time.sleep(delay + random.random() / 2)
        resp = requests.get(status_url, headers=_headers(), timeout=30)
        if resp.status_code >= 400:
            raise HiggsfieldError(f"status failed ({resp.status_code}): {resp.text[:300]}")
        data = resp.json()
        status = data.get("status", "")
        if status and status != last:
            if on_status:
                on_status(status)
            last = status
        if status in TERMINAL_STATUS:
            return data
        delay = min(delay * 1.5, 10.0)
    raise HiggsfieldError("timed out waiting for result")


def generate_image(prompt: str, model: str = "qwen-image-3", on_status=None) -> str:
    """Generate an image, download it, and return the local path."""
    from .config import IMAGE_MODELS

    if model not in IMAGE_MODELS:
        raise HiggsfieldError(f"unknown image model: {model}")
    request_id, status_url = submit(IMAGE_MODELS[model], prompt)
    result = wait(status_url, on_status=on_status)
    if result.get("status") != "completed":
        raise HiggsfieldError(result.get("error", result.get("status", "failed")))
    url = result["images"][0]["url"]

    filename = f"{request_id or 'image'}.png"
    out = _cache_dir() / filename
    _download(url, out)
    return str(out)


def generate_video(prompt: str, model: str = "kling-3.0", on_status=None) -> str:
    """Generate a video, download it, and return the local path."""
    from .config import VIDEO_MODELS

    if model not in VIDEO_MODELS:
        raise HiggsfieldError(f"unknown video model: {model}")
    request_id, status_url = submit(VIDEO_MODELS[model], prompt)
    result = wait(status_url, on_status=on_status)
    if result.get("status") != "completed":
        raise HiggsfieldError(result.get("error", result.get("status", "failed")))
    url = result["video"]["url"]

    filename = f"{request_id or 'video'}.mp4"
    out = _cache_dir() / filename
    _download(url, out)
    return str(out)


def _download(url: str, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=300) as r:
        r.raise_for_status()
        with out.open("wb") as fh:
            for chunk in r.iter_content(chunk_size=1 << 20):
                fh.write(chunk)
    if out.stat().st_size < 1024:
        raise HiggsfieldError(f"downloaded file too small: {out}")


def _cache_dir() -> Path:
    cache = Path(__file__).resolve().parent.parent / "cache"
    cache.mkdir(exist_ok=True)
    return cache
