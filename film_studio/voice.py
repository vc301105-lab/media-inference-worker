"""Voiceover: ElevenLabs if key set, edge-tts (Microsoft) fallback, else silent track.

Real audio needs network access to the provider (works on the user's machine).
If the network is unavailable we fall back to a silent audio track so the film
still renders with perfect timing — replace the mp3s later if you want.
"""

from __future__ import annotations

import sys
from pathlib import Path

from .config import elevenlabs_key, load_env
from .render import make_silent_audio

# edge-tts voices (free) — Indian English names work well for Hindi-ish narration too
EDGE_VOICES = [
    "en-IN-NeerjaNeural",
    "en-IN-PrabhatNeural",
    "en-US-AriaNeural",
    "en-US-GuyNeural",
    "en-GB-SoniaNeural",
]

ELEVEN_VOICES = {
    "Rachel": "21m00Tcm4TlvDq8ikWAM",
    "Adam": "pNInz6obpgDQGcFmaJgB",
    "Antoni": "ErXwobaYiN019PkySvjV",
    "Bella": "EXAVITQu4vr4xnSDxMaL",
}


def generate_narration(project, voice: str = "auto", lang: str = "en-IN", force_silent: bool = False) -> dict[str, str]:
    """Create one .mp3 per scene; returns {scene_number: path}."""
    load_env()
    out_dir = project.root / "voice"
    out_dir.mkdir(parents=True, exist_ok=True)

    key = elevenlabs_key()
    paths: dict[str, str] = {}
    silent = force_silent or not key and False
    for scene in project.film.scenes:
        text = scene.narration.strip()
        if not text:
            continue
        dest = out_dir / f"scene-{scene.number:02d}.mp3"
        used = ""
        if not silent and key:
            try:
                _elevenlabs(key, text, dest, voice="Rachel" if voice == "auto" else voice)
                used = "elevenlabs"
            except Exception:
                used = ""
        if not used and not silent:
            try:
                _edge_tts(text, dest, voice if voice in EDGE_VOICES else EDGE_VOICES[0], lang)
                used = "edge-tts"
            except Exception:
                used = ""
        if used:
            print(f"   Scene {scene.number}: {used} → {dest}", flush=True)
        else:
            duration = sum(s.duration for s in scene.shots) or 4.0
            make_silent_audio(duration, dest)
            print(f"   Scene {scene.number}: ⚠ offline — silent track → {dest}", flush=True)
        paths[str(scene.number)] = str(dest)
    return paths


def _edge_tts(text: str, dest: Path, voice: str, lang: str) -> None:
    import asyncio

    import edge_tts

    async def _run():
        tts = edge_tts.Communicate(text=text, voice=voice, rate="+8%")
        await tts.save(str(dest))

    asyncio.run(_run())
    if not dest.exists() or dest.stat().st_size < 100:
        raise RuntimeError("edge-tts produced empty audio")


def _elevenlabs(key: str, text: str, dest: Path, voice: str, model: str = "eleven_multilingual_v2") -> None:
    import requests

    voice_id = ELEVEN_VOICES.get(voice, voice)
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    resp = requests.post(
        url,
        headers={"xi-api-key": key, "Content-Type": "application/json"},
        json={"text": text, "model_id": model, "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}},
        timeout=120,
    )
    resp.raise_for_status()
    dest.write_bytes(resp.content)
