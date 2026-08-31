"""Runway plugin — image/video generation via Runway API (optional key)."""

from __future__ import annotations

import time

import requests

BASE = "https://api.runwayml.com/v1"


def runway_key() -> str | None:
    import os

    import dotenv

    dotenv.load_dotenv()
    return os.environ.get("RUNWAY_API_KEY") or None


def generate_video(prompt: str, *, model: str = "gen4_turbo", on_status=None) -> str:
    key = runway_key()
    if not key:
        raise RuntimeError("RUNWAY_API_KEY not set")
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    resp = requests.post(
        f"{BASE}/text_to_video",
        headers=headers,
        json={"model": model, "promptText": prompt, "ratio": "1280:720", "duration": 5},
        timeout=120,
    )
    resp.raise_for_status()
    task_id = resp.json()["id"]

    while True:
        time.sleep(5)
        r = requests.get(f"{BASE}/tasks/{task_id}", headers=headers, timeout=60)
        r.raise_for_status()
        data = r.json()
        status = data.get("status")
        if on_status:
            on_status(status)
        if status == "SUCCEEDED":
            return data["output"][0]
        if status in {"FAILED", "CANCELLED"}:
            raise RuntimeError(f"runway task {status}: {data}")
