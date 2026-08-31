"""Cinematic finish: 2.35:1 letterbox, film grain, vignette — post-render look pass."""

from __future__ import annotations

import subprocess
from pathlib import Path

from .render import _ffmpeg


def apply_film_look(movie: Path, grain: int = 6, bars: bool = True, vignette: bool = True) -> Path:
    """Encode a cinematic look onto the movie in place (audio is copied untouched)."""
    if not movie.exists():
        raise FileNotFoundError(f"movie not found: {movie}")
    ffmpeg = _ffmpeg()
    tmp = movie.with_suffix(".look.mp4")

    filters = ["scale=1280:720"]
    if bars:
        # 2.35:1 crop inside 16:9, then letterbox pad back to 16:9
        filters += ["crop=1280:544:0:88", "pad=1280:720:0:88:black"]
    if grain:
        filters.append(f"noise=alls={int(grain)}:allf=t")
    if vignette:
        filters.append("vignette=PI/4.5")

    cmd = [
        ffmpeg, "-y", "-i", str(movie),
        "-vf", ",".join(filters),
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-c:a", "copy", "-pix_fmt", "yuv420p", str(tmp),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not tmp.exists():
        raise RuntimeError(f"cinematic look failed: {proc.stderr[-400:]}")
    tmp.replace(movie)
    return movie
