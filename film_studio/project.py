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
    dialogue: str = ""
    shots: list[Shot] = field(default_factory=list)


@dataclass
class Film:
    title: str
    logline: str = ""
    genre: str = "drama"
    lang: str = "en"
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


def new_project(title: str, logline: str = "", genre: str = "drama", credits: str = "", lang: str = "en") -> Project:
    film = Film(title=title, logline=logline, genre=genre, lang=lang, credits=credits or f"A {genre} short film. Made with AI Film Studio.")
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
        "lang": project.film.lang,
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
                "dialogue": scene.dialogue,
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


def reindex_shots(project: Project) -> None:
    """Reset shot.index to sequential 0-based numbering across all scenes."""
    idx = 0
    for scene in project.film.scenes:
        for shot in scene.shots:
            shot.index = idx
            idx += 1


def move_shot(project: Project, index: int, direction: str) -> bool:
    """Move a shot one step left/right across scenes; returns True if moved."""
    flat = project.shots
    if not (0 <= index < len(flat)) or direction not in ("left", "right"):
        return False
    target = index - 1 if direction == "left" else index + 1
    if not (0 <= target < len(flat)):
        return False
    # find owning scenes
    def locate(pos):
        count = 0
        for scene in project.film.scenes:
            if count <= pos < count + len(scene.shots):
                return scene, pos - count
            count += len(scene.shots)
        return None, -1

    s1, i1 = locate(index)
    s2, i2 = locate(target)
    if s1 is None or s2 is None:
        return False
    s1.shots[i1], s2.shots[i2] = s2.shots[i2], s1.shots[i1]
    reindex_shots(project)
    return True


def delete_shot(project: Project, index: int) -> bool:
    """Remove a shot (keeps at least one shot per scene); returns True if removed."""
    count = 0
    for scene in project.film.scenes:
        if count <= index < count + len(scene.shots):
            if len(scene.shots) <= 1:
                return False
            del scene.shots[index - count]
            reindex_shots(project)
            return True
        count += len(scene.shots)
    return False


def add_shot(project: Project, scene_number: int, duration: float = 4.0, alt: bool = True) -> bool:
    """Duplicate the scene's last shot as an alternate take; returns True if added."""
    scene = next((s for s in project.film.scenes if s.number == scene_number), None)
    if scene is None or not scene.shots:
        return False
    src = scene.shots[-1]
    new = Shot(
        index=0,
        prompt=src.prompt + (", alternate take, slightly different framing" if alt else ""),
        duration=duration,
        camera=src.camera,
    )
    scene.shots.append(new)
    reindex_shots(project)
    return True
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
                narration=sc.get("narration", ""),
                dialogue=sc.get("dialogue", ""),
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
    film = Film(
        title=data["title"],
        logline=data.get("logline", ""),
        genre=data.get("genre", "drama"),
        lang=data.get("lang", "en"),
        credits=data.get("credits", ""),
        scenes=scenes,
    )
    return Project(film=film, root=root)
