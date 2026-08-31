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


def plan_film(title: str, logline: str = "", genre: str = "drama", scenes: int = 3, shots: int = 2, duration: float = 4.0, lang: str = "en") -> Project:
    film = Film(title=title, logline=logline, genre=genre, lang=lang)
    write_script(film, scenes=scenes, lang=lang)
    project = new_project(title=title, logline=logline, genre=genre, credits=f"A {genre} short film. Made with AI Film Studio.", lang=lang)
    project.film = film
    build_storyboard(project, shots_per_scene=shots, shot_duration=duration)
    write_script_file(project, lang=lang)
    save_project(project)
    return project


def make_project(project: Project, shots: int = 0, duration: float = 4.0, model: str = "kling-3.0", on_status=None, workers: int = 1) -> Project:
    """Generate all assets for an existing planned project (images + videos).

    shots: 0 = every shot in the film; N = first N shots per scene.
    workers: N > 1 → generate N shots concurrently (faster, uses more API quota).
    """
    load_env()
    from concurrent.futures import ThreadPoolExecutor, as_completed

    from .config import VIDEO_MODELS
    from .higgsfield import generate_image, generate_video

    targets: list = []
    for scene in project.film.scenes:
        sel = scene.shots if shots <= 0 else scene.shots[: min(shots, len(scene.shots))]
        targets.extend((scene, shot) for shot in sel)

    def gen(scene, shot):
        if model in VIDEO_MODELS:
            return shot, generate_video(shot.prompt, model=model, on_status=on_status)
        return shot, generate_image(shot.prompt, model=model, on_status=on_status)

    if workers > 1 and len(targets) > 1:
        with ThreadPoolExecutor(max_workers=min(workers, len(targets))) as pool:
            futures = {pool.submit(gen, sc, sh): (sc, sh) for sc, sh in targets}
            for fut in as_completed(futures):
                sc, sh = futures[fut]
                try:
                    shot, asset = fut.result()
                    shot.video_asset = asset if model in VIDEO_MODELS else shot.video_asset
                    shot.image_asset = asset if model not in VIDEO_MODELS else shot.image_asset
                    shot.local_asset = asset
                    _p(f"  ✓ {model} → shot {shot.index + 1}")
                except Exception as exc:
                    _p(f"    ⚠ generation failed for shot {sh.index + 1}: {exc}")
        save_project(project)
        return project

    for scene, shot in targets:
        _p(f"  → generating {model} for shot {shot.index + 1} (scene {scene.number})…")
        try:
            shot, asset = gen(scene, shot)
            if model in VIDEO_MODELS:
                shot.video_asset = asset
            else:
                shot.image_asset = asset
            shot.local_asset = asset
        except Exception as exc:
            _p(f"    ⚠ generation failed for shot {shot.index + 1}: {exc}")
        save_project(project)
    return project


def regenerate_shot(project: Project, shot_index: int, model: str = "kling-3.0", on_status=None) -> Shot:
    """Regenerate a single shot asset by 0-based index; returns the updated shot."""
    load_env()
    from .config import VIDEO_MODELS
    from .higgsfield import generate_image, generate_video

    shot = project.shots[shot_index]
    try:
        if model in VIDEO_MODELS:
            shot.video_asset = generate_video(shot.prompt, model=model, on_status=on_status)
            shot.local_asset = shot.video_asset
        else:
            shot.image_asset = generate_image(shot.prompt, model=model, on_status=on_status)
            shot.local_asset = shot.image_asset
        save_project(project)
    except Exception as exc:
        raise RuntimeError(f"shot {shot_index + 1} regeneration failed: {exc}") from exc
    return shot


def produce_film(project: Project, cinematic: bool = True, with_music: bool = True, transition: str = "dissolve", sfx: bool = True, watermark: bool = True) -> Path:
    theme = project.root / "sound" / f"{project.film.slug}-theme.wav"
    if with_music and not theme.exists():
        _p("  → generating genre soundtrack…")
        try:
            from .music import generate_theme

            generate_theme(project)
        except Exception as exc:
            _p(f"    ⚠ soundtrack skipped: {exc}")
    _p("  → rendering final movie…")
    return render_film(project, with_music=with_music, cinematic=cinematic, transition=transition, sfx=sfx, watermark=watermark)
