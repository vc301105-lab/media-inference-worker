"""Project model: film, scenes, shots + folder layout and metadata."""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

FILMS_DIR = Path(__file__).resolve().parent.parent / "films"


def slugify(text: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower()).strip("-")
    return text or "film"


@dataclass
class Shot:
    index: int
    prompt: str
    duration: float = 4.0
    camera: str = "static"
    image_asset: str = ""
    video_asset: str = ""
    local_asset: str = ""


@dataclass
class Scene:
    number: int
    heading: str  # e.g. "EXT. CITY ROOFTOP - NIGHT"
    action: str
    narration: str = ""
    shots: list[Shot] = field(default_factory=list)


@dataclass
class Film:
    title: str
    logline: str = ""
    genre: str = "drama"
    scenes: list[Scene] = field(default_factory=list)
    credits: str = ""

    @property
    def slug(self) -> str:
        return slugify(self.title)

    @property
    def shots(self) -> list[Shot]:
        out: list[Shot] = []
        for scene in self.scenes:
            out.extend(scene.shots)
        return out

    @property
    def duration(self) -> float:
        return sum(s.duration for s in self.shots) + 6.0  # + title/credit cards


@dataclass
class Project:
    film: Film
    root: Path

    @property
    def shots(self) -> list[Shot]:
        out: list[Shot] = []
        for scene in self.film.scenes:
            out.extend(scene.shots)
        return out


def new_project(title: str, logline: str = "", genre: str = "drama", credits: str = "") -> Project:
    film = Film(title=title, logline=logline, genre=genre, credits=credits or f"A {genre} short film. Made with AI Film Studio.")
    root = FILMS_DIR / film.slug
    if root.exists():
        backup = FILMS_DIR / f"{film.slug}-{len(list(FILMS_DIR.glob(f'{film.slug}-*')))}"
        shutil.move(str(root), str(backup))
    for sub in ("script", "assets/images", "assets/videos", "voice", "render/clips", "movie"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    return Project(film=film, root=root)


def save_project(project: Project) -> None:
    """Persist film metadata as JSON (prompts, durations, asset paths, narration)."""
    data = {
        "title": project.film.title,
        "logline": project.film.logline,
        "genre": project.film.genre,
        "credits": project.film.credits,
        "slug": project.film.slug,
        "scenes": [],
    }
    for scene in project.film.scenes:
        data["scenes"].append(
            {
                "number": scene.number,
                "heading": scene.heading,
                "action": scene.action,
                "narration": scene.narration,
                "shots": [
                    {
                        "index": s.index,
                        "prompt": s.prompt,
                        "duration": s.duration,
                        "camera": s.camera,
                        "image_asset": s.image_asset,
                        "video_asset": s.video_asset,
                        "local_asset": s.local_asset,
                    }
                    for s in scene.shots
                ],
            }
        )
    (project.root / "film.json").write_text(json.dumps(data, indent=2, ensure_ascii=False))


def rename_project(root: Path, new_title: str) -> Project:
    """Update the film title (rewrites movie filename on next render) and save."""
    import shutil

    project = load_project(root)
    old_slug = project.film.slug
    project.film.title = new_title
    save_project(project)

    new_slug = project.film.slug
    if new_slug != old_slug:
        new_root = FILMS_DIR / new_slug
        if new_root.exists():
            shutil.rmtree(new_root)
        root.rename(new_root)
        project = load_project(new_root)
    return project


def delete_project(root: Path) -> None:
    import shutil

    if root.exists():
        shutil.rmtree(root)


def load_project(root: Path) -> Project:
    data = json.loads((root / "film.json").read_text())
    scenes = []
    for sc in data["scenes"]:
        scenes.append(
            Scene(
                number=sc["number"],
                heading=sc["heading"],
                action=sc["action"],
                narration=sc["narration"],
                shots=[
                    Shot(
                        index=s["index"],
                        prompt=s["prompt"],
                        duration=s["duration"],
                        camera=s["camera"],
                        image_asset=s.get("image_asset", ""),
                        video_asset=s.get("video_asset", ""),
                        local_asset=s.get("local_asset", ""),
                    )
                    for s in sc["shots"]
                ],
            )
        )
    film = Film(title=data["title"], logline=data["logline"], genre=data["genre"], credits=data["credits"], scenes=scenes)
    return Project(film=film, root=root)
