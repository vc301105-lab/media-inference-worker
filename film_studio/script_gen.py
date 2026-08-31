"""Screenplay drafting: genre-aware 3-act templates with deterministic output."""

from __future__ import annotations

import hashlib
import random

from .project import Film, Scene

# ---------------------------------------------------------------------------
# Genre flavour: locations, moods, colour grades, shot styles
# ---------------------------------------------------------------------------
GENRES = {
    "scifi": {
        "locations": ["EXT. NEO-MUMBAI SKYLINE - NIGHT", "INT. ORBITAL STATION DECK - NIGHT", "EXT. CRYPTIC DESERT - DAWN"],
        "moods": ["electric neon haze", "cold blue steel", "vast, silent wonder"],
        "grade": "teal and magenta neon",
        "style": "cinematic sci-fi, anamorphic lens flare, volumetric fog",
    },
    "action": {
        "locations": ["EXT. RAIN-SOAKED STREET - NIGHT", "INT. ABANDONED WAREHOUSE - DAY", "EXT. HIGHWAY OVERPASS - DUSK"],
        "moods": ["raw adrenaline", "tense stillness before chaos", "smoke and amber firelight"],
        "grade": "high-contrast gritty teal-orange",
        "style": "intense blockbuster action, handheld energy, 35mm grain",
    },
    "romance": {
        "locations": ["EXT. STATION PLATFORM - GOLDEN HOUR", "INT. WARM CAFE - EVENING", "EXT. RIVERSIDE PROMENADE - NIGHT"],
        "moods": ["soft golden light", "intimate, hopeful", "bittersweet glow"],
        "grade": "warm amber and rose",
        "style": "dreamy romantic cinema, shallow depth of field, soft halo",
    },
    "horror": {
        "locations": ["EXT. FOGGY FOREST ROAD - MIDNIGHT", "INT. OLD BUNGALOW HALLWAY - NIGHT", "EXT. OVERGROWN BACKYARD - DARK"],
        "moods": ["oppressive dread", "whispering shadows", "cold terror",
],
        "grade": "desaturated sickly green",
        "style": "slow dread horror, flickering practical light, deep blacks",
    },
    "documentary": {
        "locations": ["EXT. FISHING HARBOUR - DAWN", "INT. GRANDMA'S KITCHEN - DAY", "EXT. VILLAGE STREETS - AFTERNOON"],
        "moods": ["honest, warm", "timeless patience", "quiet resilience"],
        "grade": "natural filmic color",
        "style": "documentary realism, natural light, steady tripod",
    },
    "commercial": {
        "locations": ["EXT. ROOFTOP CAFE - MORNING", "INT. MODERN STUDIO - DAY", "EXT. CITY STREET - GOLDEN HOUR"],
        "moods": ["bright and energetic", "premium quality", "feel-good finish"],
        "grade": "clean bright commercial grade",
        "style": "polished ad cinematography, snappy motion, hero product focus",
    },
    "drama": {
        "locations": ["EXT. CITY ROOFTOP - NIGHT", "INT. FAMILY LIVING ROOM - EVENING", "EXT. TRAIN STATION - DAWN"],
        "moods": ["quiet melancholy", "unspoken tension", "hopeful resolve"],
        "grade": "muted cinematic grade",
        "style": "intimate drama, slow push-ins, naturalistic light",
    },
}

CAMERA_MOVES = ["slow push-in", "slow dolly right", "gentle crane up", "handheld drift", "orbit around subject", "static wide"]


def _seed_rng(film: Film) -> random.Random:
    digest = hashlib.sha256((film.title + film.logline + film.genre).encode()).hexdigest()
    return random.Random(int(digest[:12], 16))


def write_script(film: Film, scenes: int = 3) -> Film:
    """Fill film.scenes from logline using a 3-act template."""
    rng = _seed_rng(film)
    spec = GENRES.get(film.genre, GENRES["drama"])
    logline = film.logline or "A young dreamer crosses the city on the last night before everything changes."

    # 3-act narrative + optional extra scenes
    acts = [
        ("THE WORLD", logline.rstrip(".") + "."),
        ("THE TURN", "A single choice changes everything, and the world begins to push back."),
        ("THE RESOLUTION", "At dawn, something has changed — and a new story is ready to begin."),
    ]
    beats = [
        f"{a}: {b}"
        for a, b in (acts + [("AFTERGLOW", "The camera holds on a final image that says everything without a word.")])[: max(scenes, 3)]
    ]

    film.scenes = []
    for i, beat in enumerate(beats[:scenes]):
        heading = spec["locations"][i % len(spec["locations"])]
        mood = spec["moods"][i % len(spec["moods"])]
        film.scenes.append(
            Scene(
                number=i + 1,
                heading=heading,
                action=f"We find the world in {mood}. {beat}",
                narration=beat.replace(": ", ", ").replace(". ", ". ").strip(),
            )
        )
    return film


def write_script_file(project) -> Path:
    """Write a readable screenplay .txt next to the JSON metadata."""
    lines = [project.film.title.upper(), f"A {project.film.genre} short film", "", "FADE IN:"]
    for scene in project.film.scenes:
        lines += ["", scene.heading.upper(), "", scene.action, ""]
        if scene.narration:
            lines += [f"NARRATOR: {scene.narration}", ""]
    lines += ["FADE OUT.", "", "— THE END —", "", project.film.credits]
    path = project.root / "script" / "screenplay.txt"
    path.write_text("\n".join(lines))
    return path
