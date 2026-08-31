"""Sound effects: synthesized whoosh / riser / impact via ffmpeg (no assets needed).

Events are mixed over the rendered movie at given timestamps.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from .render import _ffmpeg


def _synth(kind: str, out: Path, duration: float = 1.0) -> Path:
    """Render one effect into a wav file."""
    ffmpeg = _ffmpeg()
    out.parent.mkdir(parents=True, exist_ok=True)
    if kind == "whoosh":
        src = (
            f"anoisesrc=colour=pink:amplitude=0.6:duration={duration:.2f}:sample_rate=44100,"
            "lowpass=f=900,highpass=f=120,"
            f"afade=t=in:st=0:d={duration*0.5:.2f},afade=t=out:st={duration*0.5:.2f}:d={duration*0.5:.2f}"
        )
    elif kind == "riser":
        src = (
            f"aevalsrc=0.35*sin(2*PI*(140+420*(t/{duration:.2f}))*t):s=44100:d={duration:.2f},"
            f"afade=t=in:st=0:d={duration*0.2:.2f},afade=t=out:st={duration*0.7:.2f}:d={duration*0.3:.2f}"
        )
    elif kind == "impact":
        src = (
            f"aevalsrc=0.6*sin(2*PI*60*t)*exp(-t*6):s=44100:d={duration:.2f},"
            "lowpass=f=300"
        )
    else:
        raise ValueError(f"unknown sfx: {kind}")
    cmd = [ffmpeg, "-y", "-f", "lavfi", "-i", src, "-c:a", "pcm_s16le", str(out)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not out.exists():
        raise RuntimeError(f"sfx synth failed ({kind}): {proc.stderr[-300:]}")
    return out


def mix_sfx(movie: Path, events: list[tuple[float, str]], workdir: Path) -> Path:
    """Mix synthesized effects at (time_seconds, kind) events over movie audio."""
    if not events or not movie.exists():
        return movie
    ffmpeg = _ffmpeg()
    kind_paths: dict[str, Path] = {}
    inputs = ["-i", str(movie)]
    chains: list[str] = []
    mix_end = 0
    for i, (t, kind) in enumerate(events):
        if kind not in kind_paths:
            kind_paths[kind] = _synth(kind, workdir / f"sfx-{kind}-{i}.wav")
        inputs += ["-i", str(kind_paths[kind])]
        ms = int(max(t, 0) * 1000)
        chains.append(f"[{i+1}:a]adelay={ms}|{ms},volume=0.9[s{i}]")
        mix_end = max(mix_end, i + 1)

    inputs_labels = "[0:a]" + "".join(f"[s{i}]" for i in range(len(events)))
    chains.append(f"{inputs_labels}amix=inputs={len(events)+1}:duration=first:dropout_transition=2:normalize=0[a]")
    tmp = movie.with_suffix(".sfx.mp4")
    cmd = [
        ffmpeg, "-y", *inputs,
        "-filter_complex", ";".join(chains),
        "-map", "0:v", "-map", "[a]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", str(tmp),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not tmp.exists():
        return movie  # sfx is enhancement only — never break the film
    tmp.replace(movie)
    return movie
