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

# edge-tts voices (free) — Hindi + Indian English + international
EDGE_VOICES = [
    "en-IN-NeerjaNeural",
    "en-IN-PrabhatNeural",
    "en-US-AriaNeural",
    "en-US-GuyNeural",
    "en-GB-SoniaNeural",
    "hi-IN-MadhurNeural",
    "hi-IN-SwaraNeural",
]

LANG_VOICE = {
    "hi": "hi-IN-MadhurNeural",
    "en-in": "en-IN-NeerjaNeural",
    "en-us": "en-US-AriaNeural",
    "en-gb": "en-GB-SoniaNeural",
}


def pick_voice(lang: str, voice: str = "auto") -> str:
    """Choose an edge-tts voice: explicit name wins, otherwise auto by language."""
    if voice and voice != "auto":
        return voice
    key = lang.strip().lower().replace("_", "-")
    for prefix in (key, key.split("-")[0]):
        if prefix in LANG_VOICE:
            return LANG_VOICE[prefix]
    return LANG_VOICE["en-in"]

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
    chosen = pick_voice(lang, voice)
    print(f"   Voice: {chosen} {'(elevenlabs)' if key and voice == 'auto' else '(edge-tts)'}", flush=True)
    for scene in project.film.scenes:
        text = scene.narration.strip()
        if not text:
            continue
        dest = out_dir / f"scene-{scene.number:02d}.mp3"
        used = ""
        if not force_silent and key:
            try:
                _elevenlabs(key, text, dest, voice="Rachel" if voice == "auto" else voice)
                used = "elevenlabs"
            except Exception:
                used = ""
        if not used and not force_silent:
            try:
                _edge_tts(text, dest, chosen, lang)
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
