"""Storyboard: turn scenes into concrete shots with model-ready prompts."""

from __future__ import annotations

import hashlib
import random

from .project import Film, Project, Shot
from .script_gen import CAMERA_MOVES, GENRES

STYLE_SUFFIX = ", ultra detailed, cinematic lighting, shot on ARRI Alexa, film grain, 8k"


def _rng(seed_text: str) -> random.Random:
    return random.Random(int(hashlib.sha256(seed_text.encode()).hexdigest()[:12], 16))


def build_storyboard(project: Project, shots_per_scene: int = 2, shot_duration: float = 4.0) -> Project:
    spec = GENRES.get(project.film.genre, GENRES["drama"])
    idx = 0
    for scene in project.film.scenes:
        rng = _rng(f"{project.film.title}-{scene.number}")
        scene.shots = []
        for k in range(max(1, shots_per_scene)):
            camera = CAMERA_MOVES[(idx + k) % len(CAMERA_MOVES)]
            subject = scene.action.rstrip(".").split(", ")[-1].strip()
            prompt = (
                f"{scene.heading.replace(' - ', '. ')}. {subject}. "
                f"{spec['moods'][scene.number % len(spec['moods'])]}, "
                f"{spec['style']}, {spec['grade']}, {camera}"
                + STYLE_SUFFIX
            )
            scene.shots.append(Shot(index=idx, prompt=prompt, duration=shot_duration, camera=camera))
            idx += 1
    return project


def scene_duration(scene) -> float:
    return sum(s.duration for s in scene.shots)
