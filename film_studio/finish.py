"""Cinematic finish: genre color grade, 2.35:1 letterbox, film grain, vignette.

The grade is applied first, then box/grain/vignette — a single final encode.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from .render import _ffmpeg

# Per-genre looks: (colorbalance, eq, saturation/contrast treatments)
GRADES = {
    "scifi": ("colorbalance=rs=-.08:gs=.02:bs=.12:rh=.10:gh=.02:bh=-.12", "eq=contrast=1.12:saturation=1.08"),
    "action": ("colorbalance=rs=.10:gs=.02:bs=-.10:rh=-.06:gh=.02:bh=.10", "eq=contrast=1.18:saturation=1.05"),
    "romance": ("colorbalance=rs=.08:gs=.04:bs=-.04:rh=.06:gh=.02:bh=-.02", "eq=contrast=1.04:saturation=1.10:brightness=0.02"),
    "horror": ("colorbalance=rs=-.10:gs=.04:bs=.06:rh=-.04:gh=.00:bh=.04", "eq=contrast=1.15:saturation=0.82"),
    "drama": ("colorbalance=rs=-.03:gs=.01:bs=.03:rh=.02:gh=.01:bh=-.02", "eq=contrast=1.08:saturation=0.95"),
    "documentary": ("", "eq=contrast=1.05:saturation=1.02"),
    "commercial": ("colorbalance=rs=.04:gs=.02:bs=-.02", "eq=contrast=1.10:saturation=1.15:brightness=0.03"),
}


def apply_color_grade(movie: Path, genre: str = "drama") -> Path:
    """Apply the genre's color treatment to a rendered movie (audio untouched)."""
    if not movie.exists():
        raise FileNotFoundError(f"movie not found: {movie}")
    cb, eq = GRADES.get(genre, GRADES["drama"])
    filters = [f for f in (cb, eq) if f]
    if not filters:
        return movie
    ffmpeg = _ffmpeg()
    tmp = movie.with_suffix(".grade.mp4")
    cmd = [
        ffmpeg, "-y", "-i", str(movie),
        "-vf", ",".join(filters),
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-c:a", "copy", "-pix_fmt", "yuv420p", str(tmp),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not tmp.exists():
        raise RuntimeError(f"color grade failed: {proc.stderr[-400:]}")
    tmp.replace(movie)
    return movie


def apply_film_look(movie: Path, grain: int = 6, bars: bool = True, vignette: bool = True, genre: str | None = None) -> Path:
    """Encode a cinematic look onto the movie in place (audio is copied untouched)."""
    if not movie.exists():
        raise FileNotFoundError(f"movie not found: {movie}")
    ffmpeg = _ffmpeg()
    tmp = movie.with_suffix(".look.mp4")

    filters = []
    if genre:
        cb, eq = GRADES.get(genre, GRADES["drama"])
        filters += [f for f in (cb, eq) if f]
    filters.append("scale=1280:720")
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
