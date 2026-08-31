"""MCP server — let any AI agent (Claude Desktop, Cursor, OpenCode…) direct your studio.

Tools expose the whole pipeline: plan → assets → voice → sound → render → trailer.
Run (stdio transport, same pattern as the official Runway/Sora/Kling/ElevenLabs MCPs):

    .venv/bin/python -m film_studio.mcp_server

Config in Claude Desktop (~/.config/Claude/claude_desktop_config.json):

    "mcpServers": {
      "ai-film-studio": {
        "command": "/path/to/media-inference-worker/.venv/bin/python",
        "args": ["-m", "film_studio.mcp_server"],
        "cwd": "/path/to/media-inference-worker"
      }
    }
"""

from __future__ import annotations

from pathlib import Path

from mcp.server.fastmcp import FastMCP

from .config import check_providers, load_env
from .pipeline import make_project, plan_film, produce_film
from .project import FILMS_DIR, load_project, save_project
from .render import build_subtitle_cues, export_aspect, make_poster, write_srt
from .soundtrack import generate_theme
from .trailer import make_trailer
from .voice import generate_narration

mcp = FastMCP(
    "ai-film-studio",
    instructions=(
        "AI Film Studio: script → AI shots → voiceover → soundtrack → render → trailer. "
        "Use list_films to find an existing film, plan_new_film to start one, then "
        "generate_assets, voiceover, soundtrack, render_final, postproduction and make_trailer."
    ),
)

GENRES = ["scifi", "action", "romance", "horror", "documentary", "commercial", "drama"]
MODELS = ["kling-3.0", "veo-3.1-fast", "ltx-2.5-pro", "minimax-h3", "qwen-image-3", "nano-banana-2", "gpt-image-2"]


def _project(slug: str):
    root = FILMS_DIR / Path(slug).name
    if not (root / "film.json").exists():
        raise ValueError(f"Film '{slug}' nahi mila. list_films() se slug check karo.")
    return load_project(root)


@mcp.tool()
def studio_status() -> list[dict]:
    """Check which providers/keys are available (higgsfield, elevenlabs, edge-tts, renderer)."""
    return [
        {"name": s.name, "available": s.available, "detail": s.detail}
        for s in check_providers()
    ]


@mcp.tool()
def list_films() -> list[dict]:
    """List all film projects with title, genre, scenes/shots, and whether a movie exists."""
    out = []
    if FILMS_DIR.exists():
        for d in sorted(FILMS_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
            if (d / "film.json").exists():
                try:
                    p = load_project(d)
                    movie = d / "movie" / f"{p.film.slug}.mp4"
                    out.append(
                        {
                            "slug": p.film.slug,
                            "title": p.film.title,
                            "genre": p.film.genre,
                            "scenes": len(p.film.scenes),
                            "shots": len(p.shots),
                            "movie_ready": movie.exists(),
                        }
                    )
                except Exception:
                    continue
    return out


@mcp.tool()
def plan_new_film(
    title: str,
    genre: str = "drama",
    logline: str = "",
    scenes: int = 3,
    shots: int = 2,
    duration: float = 4.0,
    lang: str = "en",
) -> dict:
    """Create a new film: generates script + storyboard prompts (lang: en|hi). Returns slug + prompts."""
    if genre not in GENRES:
        raise ValueError(f"genre must be one of {GENRES}")
    if lang not in ("en", "hi"):
        raise ValueError("lang must be en|hi")
    project = plan_film(title, logline, genre, scenes=max(1, scenes), shots=max(1, shots), duration=max(2.0, min(duration, 15)), lang=lang)
    return {
        "slug": project.film.slug,
        "title": project.film.title,
        "genre": project.film.genre,
        "scenes": len(project.film.scenes),
        "shots": len(project.shots),
        "screenplay": str(project.root / "script" / "screenplay.txt"),
        "prompts": [s.prompt for s in project.shots],
    }


@mcp.tool()
def generate_assets(film_slug: str, model: str = "kling-3.0", shots_per_scene: int = 0, workers: int = 1) -> dict:
    """Generate AI image/video assets for every shot (or N per scene). workers>1 = parallel."""
    if model not in MODELS:
        raise ValueError(f"model must be one of {MODELS}")
    project = _project(film_slug)
    make_project(project, shots=shots_per_scene, model=model, workers=min(max(workers, 1), 4))
    save_project(project)
    return {"slug": film_slug, "model": model, "assets": [s.local_asset for s in project.shots if s.local_asset]}


@mcp.tool()
def voiceover(film_slug: str, lang: str = "hi-IN", voice: str = "auto", force_silent: bool = False) -> dict:
    """Generate per-scene narration audio (ElevenLabs → edge-tts → silent fallback)."""
    project = _project(film_slug)
    paths = generate_narration(project, voice=voice, lang=lang, force_silent=force_silent)
    return {"slug": film_slug, "tracks": paths}


@mcp.tool()
def soundtrack(film_slug: str) -> dict:
    """Generate a genre-based ambient music bed and mix it into the rendered movie."""
    project = _project(film_slug)
    theme = generate_theme(project)
    movie = project.root / "movie" / f"{project.film.slug}.mp4"
    if movie.exists():
        from .render import mix_music

        mix_music(project, movie, theme)
    return {"slug": film_slug, "theme": str(theme)}


@mcp.tool()
def render_final(film_slug: str, transition: str = "dissolve", sfx: bool = True) -> dict:
    """Render the complete movie (transitions + music + sfx + subtitles + cinematic look)."""
    project = _project(film_slug)
    movie = produce_film(project, transition=transition, sfx=sfx)
    return {"slug": film_slug, "movie": str(movie), "size_mb": round(movie.stat().st_size / 1e6, 2)}


@mcp.tool()
def postproduction(film_slug: str, export_ratios: list[str] | None = None) -> dict:
    """Create poster + thumbnail + subtitles.srt; optionally export 9:16 and 1:1 versions."""
    project = _project(film_slug)
    movie = project.root / "movie" / f"{project.film.slug}.mp4"
    if not movie.exists():
        raise ValueError("Movie render nahi hui. Pehle render_final() chalao.")
    poster = make_poster(project, movie)
    srt = write_srt(project, build_subtitle_cues(project))
    exports = []
    for ratio in (export_ratios or []):
        if ratio in ("9:16", "1:1"):
            exports.append(str(export_aspect(project, movie, ratio)))
    return {"slug": film_slug, "poster": str(poster), "subtitles": str(srt), "exports": exports}


@mcp.tool()
def review_film(film_slug: str, threshold: float = 6.0) -> dict:
    """AI quality review: score every generated shot; weak shots recommended for regenerate."""
    project = _project(film_slug)
    from .review import review_project

    report = review_project(project, threshold=threshold)
    return {
        "slug": film_slug,
        "average_score": report["average_score"],
        "weak_shots": report["weak_shots"],
        "recommendations": report["recommendations"],
    }


@mcp.tool()
def timeline_edit(
    film_slug: str,
    action: str,
    shot_index: int,
    direction: str = "right",
    duration: float = 4.0,
) -> dict:
    """Timeline edit: 'move' (left/right), 'delete', or 'add' a take to a scene (shot_index = scene number for add)."""
    project = _project(film_slug)
    from .project import add_shot, delete_shot, move_shot, save_project

    if action == "move":
        ok = move_shot(project, shot_index, direction)
    elif action == "delete":
        ok = delete_shot(project, shot_index)
    elif action == "add":
        ok = add_shot(project, shot_index, duration=duration)
    else:
        raise ValueError("action must be move|delete|add")
    if not ok:
        raise ValueError(f"{action} failed — invalid index or would leave empty scene")
    save_project(project)
    return {"slug": film_slug, "action": action, "shots": len(project.shots)}


@mcp.tool()
def cinematic_look(film_slug: str, grain: int = 6, letterbox: bool = True) -> dict:
    """Apply 2.35:1 letterbox + film grain + vignette to the rendered movie (cinematic finish)."""
    project = _project(film_slug)
    movie = project.root / "movie" / f"{project.film.slug}.mp4"
    if not movie.exists():
        raise ValueError("Movie render nahi hui. Pehle render_final() chalao.")
    from .finish import apply_film_look

    apply_film_look(movie, grain=grain, bars=letterbox)
    return {"slug": film_slug, "movie": str(movie), "look": "letterbox+grain+vignette"}


@mcp.tool()
def make_trailer_tool(film_slug: str) -> dict:
    """Build a fast-cut teaser trailer (COMING SOON) with the film's genre music."""
    project = _project(film_slug)
    trailer = make_trailer(project)
    return {"slug": film_slug, "trailer": str(trailer), "size_mb": round(trailer.stat().st_size / 1e6, 2)}


@mcp.tool()
def direct_all_in_one(
    title: str,
    genre: str = "drama",
    logline: str = "",
    scenes: int = 3,
    shots: int = 2,
    model: str = "kling-3.0",
    lang: str = "hi-IN",
    make_trailer_flag: bool = True,
) -> dict:
    """One-shot full production: plan → assets → voice → sound → render → (trailer)."""
    project = plan_film(title, logline, genre, scenes=max(1, scenes), shots=max(1, shots))
    make_project(project, model=model)
    generate_narration(project, lang=lang)
    movie = produce_film(project)
    trail = str(make_trailer(project)) if make_trailer_flag else ""
    return {"slug": project.film.slug, "movie": str(movie), "trailer": trail}


def main() -> None:
    load_env()
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
