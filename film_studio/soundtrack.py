"""Soundtrack: genre-based ambient musical bed generated with pure ffmpeg (offline).

No external music API needed — layers of sine drones + tremolo + noise shaped per
genre, mixed at low volume under the narration during render.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from .render import _ffmpeg

# Each genre: (freqs_amps, lowpass_hz, tremolo_hz, extra_noise_amp)
# Freq/amp pairs are deterministic — subtle differences come from the hash seed.
PRESETS = {
    "drama":        ([110, 130.81, 164.81], 700, 0.12, 0.0),
    "scifi":        ([55, 82.41, 110], 600, 0.08, 0.02),
    "romance":      ([130.81, 196.0, 261.63], 900, 0.10, 0.0),
    "horror":       ([52, 65.41, 78.0], 500, 0.0, 0.06),
    "action":       ([82.41, 110.0, 164.81], 750, 2.1, 0.03),
    "commercial":   ([196.0, 261.63, 329.63], 1200, 0.5, 0.0),
    "documentary":  ([110, 146.83, 220], 800, 0.09, 0.0),
}


def _expr(freqs: list[float], seed: float) -> str:
    """Build a deterministic sine-chord expression (fundamental strongest)."""
    terms = []
    for i, freq in enumerate(freqs):
        amp = 0.06 * (0.72 ** i)  # first note strongest
        terms.append(f"{amp:.3f}*sin(2*PI*{freq:.2f}*t+{seed + i * 0.7:.2f})")
    return "+".join(terms)


def generate_theme(project, duration: float | None = None) -> Path:
    """Render a looping ambient bed for the film's genre → sound/<slug>-theme.wav."""
    from .render import _ffmpeg

    film = project.film
    dur = duration if duration else film.duration + 2
    freqs_amps, lowpass, trem, noise = PRESETS.get(film.genre, PRESETS["drama"])

    # deterministic phase offset from title so every film sounds slightly different
    seed = sum(ord(c) for c in film.title) % 6.28
    expr = _expr(list(freqs_amps), seed)

    out_dir = project.root / "sound"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{film.slug}-theme.wav"

    inputs = ["-f", "lavfi", "-i", f"aevalsrc={expr}:s=44100:d={dur:.1f}"]
    filter_parts: list[str] = []
    if noise > 0:
        inputs += ["-f", "lavfi", "-i", f"anoisesrc=colour=brown:amplitude={noise}:duration={dur:.1f}:sample_rate=44100"]
        filter_parts.append(f"[0:a]volume=1.0[m];[1:a]volume={0.5:.2f}[n];[m][n]amix=inputs=2:duration=first:normalize=0[am]")
        main_label = "am"
    else:
        filter_parts.append("[0:a]anull[am]")
        main_label = "am"

    filter_parts.append(
        f"[{main_label}]lowpass=f={lowpass},tremolo=f={trem}:d=0.45,apad=pad_dur={max(dur - 0.1, 1):.1f}"
        f",volume=0.28,afade=t=in:st=0:d=1.2,afade=t=out:st={max(dur - 1.5, 0):.1f}:d=1.5[out]"
    )
    cmd = [
        _ffmpeg(), "-y", *inputs,
        "-filter_complex", ";".join(filter_parts),
        "-map", "[out]", "-c:a", "pcm_s16le", str(out),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not out.exists() or out.stat().st_size < 4096:
        raise RuntimeError(f"soundtrack failed: {proc.stderr[-400:]}")
    return out
