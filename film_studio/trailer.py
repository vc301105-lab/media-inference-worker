"""Trailer maker: fast-cut teaser from the film's best shots + music + COMING SOON card."""

from __future__ import annotations

from pathlib import Path

from .project import Project, Shot
from .render import (
    _concat,
    _make_clip,
    make_silent_audio,
    make_title_card,
    mix_music,
)
from .music import generate_theme

CUT = 1.6          # seconds per teaser shot
END_CUT = 2.5      # COMING SOON card


def _pick_shots(project: Project, max_shots: int = 4) -> list[tuple[object, Shot, Path]]:
    """One key shot per scene (first available asset), capped at max_shots."""
    picks: list[tuple[object, Shot, Path]] = []
    for scene in project.film.scenes:
        for shot in scene.shots:
            asset = Path(shot.local_asset) if shot.local_asset else None
            if asset and asset.exists():
                picks.append((scene, shot, asset))
                break
    return picks[:max_shots]


def make_trailer(project: Project, music: bool = True) -> Path:
    """Render movie/<slug>-trailer.mp4: fast cuts + genre music + COMING SOON."""
    film = project.film
    render_dir = project.root / "render"
    clips_dir = render_dir / "clips"
    out = project.root / "movie" / f"{film.slug}-trailer.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)

    picks = _pick_shots(project)
    parts: list[Path] = []

    if not picks:
        # Every shot has a silent track so the concat stays uniform (audio present).
        # Build a title-card teaser if no assets exist yet.
        card = make_title_card(film.title.upper(), "TEASER", render_dir / "trailer-fallback.png")
        silent = make_silent_audio(CUT, render_dir / "trailer-fallback-silent.mp3")
        parts.append(_make_clip(card, silent, CUT, clips_dir / "trail-00.mp4", kenburns=False))

    for i, (_, shot, asset) in enumerate(picks):
        silent = make_silent_audio(CUT, render_dir / f"trail-{i:02d}-silent.mp3")
        parts.append(
            _make_clip(
                asset, silent, CUT, clips_dir / f"trail-{i:02d}.mp4",
                caption=f"{film.title.upper()}" if i == 0 else "",
                work=render_dir / "prep", kenburns=True,
            )
        )

    end = make_title_card("COMING SOON", film.title.upper(), render_dir / "trailer-end.png")
    end_silent = make_silent_audio(END_CUT, render_dir / "trailer-end-silent.mp3")
    parts.append(_make_clip(end, end_silent, END_CUT, clips_dir / "trail-end.mp4", kenburns=False))

    movie = _concat(parts, out)

    if music:
        name = f"{film.slug}-trailer-theme.wav"
        theme = project.root / "sound" / name
        if not theme.exists():
            generate_theme(project, duration=len(parts) * CUT + 2, filename=name)
        mix_music(project, movie, theme)
    return movie
