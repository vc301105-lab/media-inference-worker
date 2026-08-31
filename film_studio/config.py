"""Configuration: env loading, provider models, availability checks."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = REPO_ROOT / ".env"

# ---------------------------------------------------------------------------
# Higgsfield platform (same auth as generate.py / RUNBOOK.md)
# ---------------------------------------------------------------------------
HIGGSFIELD_BASE = "https://platform.higgsfield.ai"

IMAGE_MODELS = {
    "qwen-image-3": "/alibaba/qwen-image-3/text-to-image",
    "nano-banana-2": "/nano-banana-2/lite/text-to-image",
    "gpt-image-2": "/openai/gpt-image-2",
}

VIDEO_MODELS = {
    "kling-3.0": "/kling-video/v3.0/std/text-to-video",
    "veo-3.1-fast": "/veo3.1/fast/text-to-video",
    "ltx-2.5-pro": "/lightricks/ltx-2.5/text-to-video/pro",
    "minimax-h3": "/minimax/h3/text-to-video",
}

TERMINAL_STATUS = {"completed", "failed", "nsfw", "canceled"}

# ---------------------------------------------------------------------------
# ElevenLabs (optional — used when ELEVENLABS_API_KEY is set)
# ---------------------------------------------------------------------------
ELEVENLABS_BASE = "https://api.elevenlabs.io/v1"


@dataclass
class ProviderStatus:
    name: str
    available: bool
    detail: str = ""
    models: dict = field(default_factory=dict)


def load_env() -> None:
    """Load key=value lines from .env into os.environ (don't override)."""
    if not ENV_FILE.exists():
        return
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        os.environ.setdefault(name.strip(), value.strip())


def higgsfield_auth() -> str | None:
    key_id = os.environ.get("HF_API_KEY_ID")
    secret = os.environ.get("HF_API_KEY_SECRET")
    if key_id and secret:
        return f"Key {key_id}:{secret}"
    return None


def elevenlabs_key() -> str | None:
    return os.environ.get("ELEVENLABS_API_KEY") or None


def check_providers() -> list[ProviderStatus]:
    load_env()
    statuses = []

    hf = higgsfield_auth()
    statuses.append(
        ProviderStatus(
            "higgsfield (images+videos)",
            bool(hf),
            "key found" if hf else "HF_API_KEY_ID/SECRET missing in .env",
            {"images": dict(IMAGE_MODELS), "videos": dict(VIDEO_MODELS)},
        )
    )

    el = elevenlabs_key()
    statuses.append(
        ProviderStatus(
            "elevenlabs (voiceover)",
            bool(el),
            "key found" if el else "optional — set ELEVENLABS_API_KEY; edge-tts falls back",
            {"voices": ["Rachel", "Adam", "Antoni", "Bella"]},
        )
    )

    try:
        import edge_tts  # noqa: F401

        statuses.append(ProviderStatus("edge-tts (free voiceover)", True, "installed — free Microsoft voices"))
    except ImportError:
        statuses.append(ProviderStatus("edge-tts (free voiceover)", False, "pip install edge-tts"))

    statuses.append(ProviderStatus("local renderer (offline)", True, "Pillow + ffmpeg — always works"))
    return statuses
