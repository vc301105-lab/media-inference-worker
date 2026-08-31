"""End-to-end film pipeline: script -> storyboard -> assets -> voice -> render."""

from __future__ import annotations

import sys
from pathlib import Path

from .config import load_env
from .project import Film, Project, new_project, save_project, load_project
from .script_gen import write_script, write_script_file
from .storyboard import build_storyboard
from .render import render_film


def _p(msg: str) -> None:
    print(msg, flush=True)


def plan_film(title: str, logline: str = "", genre: str = "drama", scenes: int = 3, shots: int = 2, duration: float = 4.0) -> Project:
    film = Film(title=title, logline=logline, genre=genre)
    write_script(film, scenes=scenes)
    project = new_project(title=title, logline=logline, genre=genre, credits=f"A {genre} short film. Made with AI Film Studio.")
    project.film = film
    build_storyboard(project, shots_per_scene=shots, shot_duration=duration)
    write_script_file(project)
    save_project(project)
    return project


def make_project(project: Project, shots: int = 0, duration: float = 4.0, model: str = "kling-3.0", on_status=None) -> Project:
    """Generate all assets for an existing planned project (images + videos).

    shots: 0 = every shot in the film; N = first N shots per scene.
    """
    load_env()
    from .config import VIDEO_MODELS
    from .higgsfield import generate_image, generate_video

    for scene in project.film.scenes:
        targets = scene.shots if shots <= 0 else scene.shots[: min(shots, len(scene.shots))]
        for shot in targets:
            _p(f"  → generating {model} for shot {shot.index + 1} (scene {scene.number})…")
            try:
                if model in VIDEO_MODELS:
                    shot.video_asset = generate_video(shot.prompt, model=model, on_status=on_status)
                    shot.local_asset = shot.video_asset
                else:
                    shot.image_asset = generate_image(shot.prompt, model=model, on_status=on_status)
                    shot.local_asset = shot.image_asset
            except Exception as exc:
                _p(f"    ⚠ generation failed for shot {shot.index + 1}: {exc}")
        save_project(project)
    return project


def produce_film(project: Project) -> Path:
    theme = project.root / "sound" / f"{project.film.slug}-theme.wav"
    if not theme.exists():
        _p("  → generating genre soundtrack…")
        try:
            from .soundtrack import generate_theme

            generate_theme(project)
        except Exception as exc:
            _p(f"    ⚠ soundtrack skipped: {exc}")
    _p("  → rendering final movie…")
    return render_film(project)
