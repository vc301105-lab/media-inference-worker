"""Transitions — crossfade / fade / wipe between shots (xfade + acrossfade)."""

from __future__ import annotations

import subprocess
from pathlib import Path

from .render import _ffmpeg, _probe_duration

TRANSITIONS = {
    "dissolve": "fade",
    "fade-soft": "fadewhite",
    "wipe": "wipeleft",
    "circle": "circleopen",
}


def apply_transitions(parts: list[Path], out: Path, transition: str = "dissolve", duration: float = 0.5) -> Path:
    """Concatenate clips with a transition effect. Requires audio on every clip."""
    if len(parts) == 0:
        raise RuntimeError("no clips to transition")
    if len(parts) == 1 or transition not in TRANSITIONS:
        # fall back to simple concat
        from .render import _concat

        return _concat(parts, out)

    ffmpeg = _ffmpeg()
    td = max(0.2, min(duration, 2.0))
    xf = TRANSITIONS[transition]

    durations = [_probe_duration(p) for p in parts]
    total = sum(durations) - td * (len(parts) - 1)

    # --- video: chain xfade ---
    vf_parts: list[str] = []
    labels: list[str] = [f"[{i}:v]" for i in range(len(parts))]
    offset = durations[0] - td
    label = labels[0]
    for i in range(1, len(parts)):
        nxt = f"[vx{i}]"
        vf_parts.append(
            f"{label}[{i}:v]xfade=transition={xf}:duration={td:.2f}:offset={offset:.2f}{nxt}"
        )
        label = nxt
        offset += durations[i] - td

    # --- audio: chain acrossfade ---
    af_parts: list[str] = []
    alabel = f"[{0}:a]"
    for i in range(1, len(parts)):
        nxt = f"[ax{i}]"
        af_parts.append(
            f"{alabel}[{i}:a]acrossfade=d={td:.2f}:c1=tri:c2=tri{nxt}"
        )
        alabel = nxt

    filter_complex = ";".join(vf_parts + af_parts)
    cmd = [
        ffmpeg, "-y",
    ]
    for p in parts:
        cmd += ["-i", str(p)]
    cmd += [
        "-filter_complex", filter_complex,
        "-map", f"{label}", "-map", f"{alabel}",
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k", "-r", "24", "-pix_fmt", "yuv420p",
        "-t", f"{total:.2f}", str(out),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not out.exists():
        # graceful fallback: plain concat
        from .render import _concat

        return _concat(parts, out)
    return out
