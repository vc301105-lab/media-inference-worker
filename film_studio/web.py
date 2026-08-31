"""Web UI for AI Film Studio — run the whole studio from a browser.

Usage:
    python -m film_studio.web [--host 0.0.0.0] [--port 8080]
"""

from __future__ import annotations

import argparse
import os
import queue
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

from flask import Flask, jsonify, redirect, request, send_from_directory, url_for
from werkzeug.utils import secure_filename

from .config import check_providers, load_env
from .pipeline import plan_film
from .project import FILMS_DIR, load_project
from .render import _ffmpeg
from .review import load_review

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Job manager — runs CLI pipeline steps in background, streams logs to UI
# ---------------------------------------------------------------------------
class JobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, dict] = {}
        self._lock = threading.Lock()

    def start(self, slug: str, action: str, extra: list[str]) -> str:
        key = f"{slug}::{action}::{int(time.time() * 1000)}"
        q: queue.Queue[str] = queue.Queue()
        with self._lock:
            self._jobs[key] = {"slug": slug, "action": action, "state": "running", "lines": [], "queue": q}
        t = threading.Thread(target=self._worker, args=(key, slug, action, extra, q), daemon=True)
        t.start()
        return key

    def _worker(self, key: str, slug: str, action: str, extra: list[str], q: queue.Queue) -> None:
        project = FILMS_DIR / slug
        cmd = [
            sys.executable, "-m", "film_studio", action, "--project", str(project), *extra,
        ]
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
            for line in proc.stdout:
                q.put(line.rstrip())
                with self._lock:
                    self._jobs[key]["lines"].append(line.rstrip())
            proc.wait()
            state = "done" if proc.returncode == 0 else "error"
        except Exception as exc:  # pragma: no cover
            state = "error"
            q.put(f"❌ {exc}")
            with self._lock:
                self._jobs[key]["lines"].append(f"❌ {exc}")
        with self._lock:
            if key in self._jobs:
                self._jobs[key]["state"] = state

    def status(self, key: str) -> dict | None:
        with self._lock:
            job = self._jobs.get(key)
            if not job:
                return None
            return {"key": key, "slug": job["slug"], "action": job["action"], "state": job["state"], "lines": job["lines"][-200:]}

    def running(self) -> bool:
        with self._lock:
            return any(j["state"] == "running" for j in self._jobs.values())


JOBS = JobManager()

ACTION_NAMES = {
    "build": "Generate Assets",
    "voice": "Voiceover",
    "sound": "Soundtrack",
    "render": "Render Movie",
    "postpro": "Post-Production",
    "plan": "Plan",
    "publish": "Publish to YouTube",
    "finish": "Cinematic Look",
    "review": "AI Review",
    "trailer": "Trailer",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def list_films() -> list[dict]:
    films = []
    if FILMS_DIR.exists():
        for d in sorted(FILMS_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
            if (d / "film.json").exists():
                try:
                    project = load_project(d)
                    movie = d / "movie" / f"{project.film.slug}.mp4"
                    films.append(
                        {
                            "slug": project.film.slug,
                            "title": project.film.title,
                            "genre": project.film.genre,
                            "lang": project.film.lang,
                            "logline": project.film.logline,
                            "scenes": len(project.film.scenes),
                            "shots": len(project.shots),
                            "duration": project.film.duration,
                            "movie": movie.exists(),
                            "movie_size": movie.stat().st_size if movie.exists() else 0,
                            "poster": (d / "movie" / "poster.png").exists(),
                            "srt": (d / "movie" / "subtitles.srt").exists(),
                            "exports": sorted(p.name for p in (d / "movie").glob("*-9x16.mp4") + list((d / "movie").glob("*-1x1.mp4"))),
                        }
                    )
                except Exception:
                    continue
    return films


def _movie_dir(slug: str) -> tuple[Path, str] | tuple[None, None]:
    root = FILMS_DIR / secure_filename(slug)
    if not (root / "film.json").exists():
        return None, None
    return root / "movie", "ok"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/")
def index():
    films = list_films()
    rows = "".join(_film_card(f) for f in films) or '<div class="empty">Abhi koi film nahi. Neeche form se pehli film shuru karo! 🎬</div>'
    return render_page(
        _INDEX_TMPL.format(films=rows, genres=" ".join(f'<option value="{g}">{g}</option>' for g in GENRES))
    )


def _film_card(f: dict) -> str:
    poster_url = url_for("movie_file", slug=f["slug"], filename="poster.png") if f["poster"] else ""
    thumb = (
        f'<img class="poster" src="{poster_url}" alt="poster" loading="lazy">'
        if poster_url
        else '<div class="poster placeholder">🎬</div>'
    )
    size = f"{f['movie_size']/1e6:.1f} MB" if f["movie_size"] else ""
    return f"""
    <a class="film-card" href="{url_for('film', slug=f['slug'])}">
      {thumb}
      <div class="film-info">
        <div class="film-title">{f['title']} {f'<span class="lang">(हि)</span>' if f['lang'] == 'hi' else ''}</div>
        <div class="film-meta">
          <span class="badge">{f['genre']}</span>
          <span>{f['scenes']} scenes · {f['shots']} shots</span>
          <span>~{f['duration']:.0f}s</span>
          {f'<span class="ok">✓ movie</span>' if f['movie'] else ''}
          {f'<span class="ok">{size}</span>' if size else ''}
        </div>
      </div>
    </a>"""


@app.post("/new")
def new():
    title = request.form.get("title", "").strip()
    if not title:
        return redirect(url_for("index"))
    genre = request.form.get("genre", "drama")
    lang = request.form.get("lang", "en")
    scenes = max(1, min(int(request.form.get("scenes", 3)), 12))
    shots = max(1, min(int(request.form.get("shots", 2)), 8))
    duration = max(2.0, min(float(request.form.get("duration", 4)), 15))
    project = plan_film(title, request.form.get("logline", ""), genre, scenes=scenes, shots=shots, duration=duration, lang=lang)
    return redirect(url_for("film", slug=project.film.slug))


@app.post("/film/<slug>/meta")
def update_meta(slug: str):
    root = FILMS_DIR / secure_filename(slug)
    if not (root / "film.json").exists():
        return redirect(url_for("index"))
    project = load_project(root)
    if request.form.get("title", "").strip():
        from .project import rename_project

        project = rename_project(root, request.form["title"].strip())
    film = project.film
    film.logline = request.form.get("logline", "")
    film.genre = request.form.get("genre", film.genre) or film.genre
    film.credits = request.form.get("credits", "") or film.credits
    from .project import save_project

    save_project(project)
    return redirect(url_for("film", slug=project.film.slug))


@app.post("/film/<slug>/shot")
def update_shot(slug: str):
    root = FILMS_DIR / secure_filename(slug)
    project = load_project(root)
    try:
        idx = int(request.form.get("index", "-1"))
    except ValueError:
        idx = -1
    shot = project.shots[idx]
    prompt = request.form.get("prompt", "").strip()
    duration = request.form.get("duration", "").strip()
    if prompt:
        shot.prompt = prompt
        shot.local_asset = ""  # changed prompt → asset stale, regenerate
    if duration:
        try:
            shot.duration = max(2.0, min(float(duration), 15.0))
        except ValueError:
            pass
    from .project import save_project

    save_project(project)
    return redirect(url_for("film", slug=slug))


@app.post("/film/<slug>/shot/move")
def move_shot(slug: str):
    root = FILMS_DIR / secure_filename(slug)
    project = load_project(root)
    try:
        idx = int(request.form.get("index", "-1"))
    except ValueError:
        idx = -1
    from .project import move_shot as _move, save_project

    _move(project, idx, request.form.get("dir", "right"))
    save_project(project)
    return redirect(url_for("film", slug=slug))


@app.post("/film/<slug>/shot/delete")
def delete_shot_route(slug: str):
    root = FILMS_DIR / secure_filename(slug)
    project = load_project(root)
    try:
        idx = int(request.form.get("index", "-1"))
    except ValueError:
        idx = -1
    from .project import delete_shot as _delete, save_project

    _delete(project, idx)
    save_project(project)
    return redirect(url_for("film", slug=slug))


@app.post("/film/<slug>/shot/add")
def add_shot_route(slug: str):
    root = FILMS_DIR / secure_filename(slug)
    project = load_project(root)
    try:
        scene_no = int(request.form.get("scene", "1"))
    except ValueError:
        scene_no = 1
    from .project import add_shot as _add, save_project

    _add(project, scene_no, duration=float(request.form.get("duration", 4)))
    save_project(project)
    return redirect(url_for("film", slug=slug))


@app.post("/film/<slug>/review")
def run_review(slug: str):
    root = FILMS_DIR / secure_filename(slug)
    project = load_project(root)
    from .review import review_project

    review_project(project)
    return redirect(url_for("film", slug=slug))


@app.post("/film/<slug>/delete")
def delete_film(slug: str):
    from .project import delete_project

    root = FILMS_DIR / secure_filename(slug)
    if (root / "film.json").exists():
        delete_project(root)
    return redirect(url_for("index"))


@app.get("/film/<slug>/shot/<int:index>/thumb")
def shot_thumb(slug: str, index: int):
    """Return a small preview image for a shot's generated asset (cached)."""
    root = FILMS_DIR / secure_filename(slug)
    if not (root / "film.json").exists():
        return ("not found", 404)
    try:
        project = load_project(root)
        shot = project.shots[index]
    except Exception:
        return ("not found", 404)
    asset = Path(shot.local_asset) if shot.local_asset else None
    if not asset or not asset.exists():
        return ("not found", 404)

    cache = root / "render" / "previews"
    cache.mkdir(parents=True, exist_ok=True)
    out = cache / f"thumb-{index:02d}.jpg"
    if not out.exists():
        try:
            if asset.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
                from PIL import Image

                img = Image.open(asset).convert("RGB")
                img.thumbnail((320, 200))
                img.save(out, quality=82)
            else:
                ffmpeg = _ffmpeg()
                subprocess.run(
                    [ffmpeg, "-y", "-ss", "0.8", "-i", str(asset), "-frames:v", "1", "-vf", "scale=320:-2", str(out)],
                    capture_output=True,
                )
        except Exception:
            return ("not found", 404)
    if not out.exists():
        return ("not found", 404)
    return send_from_directory(cache, out.name)


@app.get("/film/<slug>/movie/<path:filename>")
def movie_file(slug: str, filename: str):
    root, _ = _movie_dir(slug)
    if root is None:
        return ("not found", 404)
    safe = secure_filename(filename)
    if not safe or not (root / safe).exists():
        return ("not found", 404)
    return send_from_directory(root, safe, conditional=True)


@app.get("/film/<slug>")
def film(slug: str):
    root = FILMS_DIR / secure_filename(slug)
    if not (root / "film.json").exists():
        return redirect(url_for("index"))
    project = load_project(root)
    scenes_html = "".join(_scene_block(project, s) for s in project.film.scenes)
    movie = root / "movie" / f"{project.film.slug}.mp4"
    video = ""
    if movie.exists():
        poster = (
            url_for("movie_file", slug=slug, filename="poster.png")
            if (root / "movie" / "poster.png").exists()
            else ""
        )
        video = f"""
        <div class="player">
          <video controls preload="metadata" poster="{poster}">
            <source src="{url_for('movie_file', slug=slug, filename=movie.name)}" type="video/mp4">
          </video>
        </div>"""
    downloads = _download_links(root, slug)
    review = load_review(project)
    review_html = _review_html(review) if review else ""
    return render_page(
        _FILM_TMPL.format(
            title=project.film.title,
            genre=project.film.genre,
            logline=project.film.logline or "",
            credits=project.film.credits,
            genres=" ".join(
                f'<option value="{g}"{" selected" if g == project.film.genre else ""}>{g}</option>' for g in GENRES
            ),
            scenes=scenes_html,
            video=video,
            downloads=downloads,
            slug=slug,
            models=" ".join(f'<option value="{m}">{m}</option>' for m in MODELS),
            review_html=review_html,
        )
    )


def _review_html(review: dict) -> str:
    scores = " ".join(
        f'<span class="score { "ok" if float(r["score"]) >= 6.5 else ("weak" if float(r["score"]) >= 5 else "bad") }">#{r["shot"]} {r["score"]}</span>'
        for r in review.get("details", [])
        if r.get("score") is not None
    )
    recs = "".join(f"<li>{r}</li>" for r in review.get("recommendations", [])[:8]) or "<li>Sab shots strong — koi fix nahi chahiye ✅</li>"
    return f"""
    <div class="card">
      <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;">
        <h2 style="margin:0;">🔍 AI Director Review</h2>
        <span class="avg">Avg {review['average_score']}/10 · {review['shots_analyzed']} shots</span>
      </div>
      <div class="scores">{scores or '<span class="muted">Shots generate hone ke baad review karo</span>'}</div>
      <ul class="recs">{recs}</ul>
      <div style="margin-top:8px;">
        <form method="post" action="/film/{review['film']}/review" style="display:inline">
          <button class="small">🔄 Re-run Review</button>
        </form>
      </div>
    </div>"""


def _scene_block(project, scene) -> str:
    review = load_review(project)
    scores = {r["shot"]: r for r in (review or {}).get("details", [])}
    shots = ""
    for s in scene.shots:
        asset_ok = s.local_asset and Path(s.local_asset).exists()
        status = '<span class="ok">✓ asset</span>' if asset_ok else '<span class="muted">ℹ no asset</span>'
        thumb = (
            f'<img class="shot-thumb" src="{url_for("shot_thumb", slug=project.film.slug, index=s.index)}" loading="lazy">'
            if asset_ok
            else '<div class="shot-thumb ph">🎬</div>'
        )
        score = scores.get(s.index + 1)
        badge = ""
        if score and score.get("score") is not None:
            cls = "score-ok" if float(score["score"]) >= 6.5 else ("score-weak" if float(score["score"]) >= 5 else "score-bad")
            badge = f'<span class="shot-score {cls}" title="{"; ".join(score.get("flags") or [])}">{score["score"]}</span>'
        shots += f"""
        <div class="shot-row">
          {thumb}
          <form method="post" action="/film/{project.film.slug}/shot" class="shot-form">
            <input type="hidden" name="index" value="{s.index}">
            <span class="shot-id">#{s.index + 1}</span>
            <span class="shot-cam">{s.camera}</span>
            <input class="shot-prompt" name="prompt" value="{s.prompt}" placeholder="Prompt">
            <input class="shot-dur" name="duration" type="number" value="{s.duration}" step="0.5" min="2" max="15" title="seconds">
            <button class="small ghost" type="submit">💾</button>
            {status}
          </form>
          {badge}
          <form method="post" action="/film/{project.film.slug}/shot/move" style="display:inline">
            <input type="hidden" name="index" value="{s.index}">
            <input type="hidden" name="dir" value="left">
            <button class="mini" title="Move left">◀</button>
          </form>
          <form method="post" action="/film/{project.film.slug}/shot/move" style="display:inline">
            <input type="hidden" name="index" value="{s.index}">
            <input type="hidden" name="dir" value="right">
            <button class="mini" title="Move right">▶</button>
          </form>
          <form method="post" action="/film/{project.film.slug}/shot/delete" style="display:inline"
                onsubmit="return confirm('Shot delete karna hai?')">
            <input type="hidden" name="index" value="{s.index}">
            <button class="mini" title="Delete" style="color:#ff7b7b;">✕</button>
          </form>
        </div>"""
    return f"""
    <div class="scene">
      <div class="scene-head"><span class="scene-num">SCENE {scene.number}</span><span class="scene-heading">{scene.heading}</span></div>
      <div class="scene-action">{scene.action}</div>
      {f'<div class="scene-dialogue">🎤 {scene.dialogue}</div>' if scene.dialogue else ''}
      {f'<div class="scene-narr">🗣 {scene.narration}</div>' if scene.narration else ''}
      {shots}
      <div class="scene-actions">
        <form method="post" action="/film/{project.film.slug}/shot/add" style="display:inline">
          <input type="hidden" name="scene" value="{scene.number}">
          <input type="hidden" name="duration" value="{scene.shots[0].duration if scene.shots else 4}">
          <button class="small ghost">＋ Add Take</button>
        </form>
        <span class="muted">◀ ▶ reorder · ✕ delete · 💾 save prompt</span>
      </div>
    </div>"""


def _download_links(root: Path, slug: str) -> str:
    movie_dir = root / "movie"
    items = []
    for pattern, label in [(f"{slug}.mp4", "Movie"), ("poster.png", "Poster"), ("thumbnail.jpg", "Thumb"), ("subtitles.srt", "Subtitles"), ("*-9x16.mp4", "9:16"), ("*-1x1.mp4", "1:1")]:
        for p in sorted(movie_dir.glob(pattern)):
            items.append(f'<a class="dl" href="{url_for("movie_file", slug=slug, filename=p.name)}">{label} · {p.stat().st_size/1e6:.1f} MB</a>')
    return "".join(items) or '<span class="muted">Abhi koi output nahi — Render chalao.</span>'


@app.post("/film/<slug>/job")
def job(slug: str):
    slug = secure_filename(slug)
    action = request.form.get("action", "render")
    extra: list[str] = []
    if action == "build":
        extra = ["--model", request.form.get("model", "kling-3.0"), "--shots", request.form.get("shots_count", "0")]
    if action == "voice":
        extra = ["--lang", request.form.get("lang", "hi-IN")]
        if request.form.get("silent") == "1":
            extra.append("--silent")
    if action == "postpro" and request.form.get("ratios"):
        extra = ["--ratios", *request.form.get("ratios").split()]
    key = JOBS.start(slug, action, extra)
    return jsonify({"job": key})


@app.get("/api/jobs/<key>")
def job_status(key: str):
    data = JOBS.status(key)
    if data is None:
        return jsonify({"state": "unknown"}), 404
    return jsonify(data)


@app.get("/status")
def status():
    rows = "".join(f'<li><b>{s.name}</b> — {"✅ " if s.available else "❌ "}{s.detail}</li>' for s in check_providers())
    return render_page(_STATUS_TMPL.format(rows=rows))


# ---------------------------------------------------------------------------
# Page shell
# ---------------------------------------------------------------------------
GENRES = ["scifi", "action", "romance", "horror", "documentary", "commercial", "drama"]
MODELS = ["kling-3.0", "veo-3.1-fast", "ltx-2.5-pro", "minimax-h3", "qwen-image-3", "nano-banana-2", "gpt-image-2"]


def render_page(body: str) -> str:
    return _SHELL.replace("__BODY__", body)


_SHELL = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>🎬 AI Film Studio</title>
<style>
:root { --bg:#0b0d14; --card:#141826; --card2:#1b2032; --line:#262d45; --accent:#e05a5a; --accent2:#f5ebd2; --ok:#5ad08a; --muted:#8a90a8; }
* { box-sizing:border-box; }
body { margin:0; font-family:'Segoe UI',system-ui,sans-serif; background:linear-gradient(160deg,#0b0d14 0%,#101527 55%,#141018 100%); color:#e8e6f0; min-height:100vh; }
header { display:flex; align-items:center; gap:14px; padding:18px 28px; border-bottom:1px solid var(--line); background:rgba(10,12,20,.8); position:sticky; top:0; z-index:10; backdrop-filter:blur(8px); }
header h1 { font-size:20px; margin:0; letter-spacing:.5px; }
header .tag { font-size:11px; color:var(--muted); }
header a { color:var(--accent2); text-decoration:none; font-size:13px; margin-left:auto; }
main { max-width:1080px; margin:0 auto; padding:28px 20px 60px; }
.card { background:var(--card); border:1px solid var(--line); border-radius:14px; padding:20px; margin:18px 0; }
h2 { font-size:16px; margin:0 0 12px; color:var(--accent2); }
form.grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:12px; }
label { display:flex; flex-direction:column; gap:5px; font-size:12px; color:var(--muted); }
input,select { background:var(--card2); border:1px solid var(--line); color:#fff; border-radius:8px; padding:10px 12px; font-size:14px; }
input:focus,select:focus { outline:none; border-color:var(--accent); }
button { background:var(--accent); color:#fff; border:none; border-radius:8px; padding:11px 18px; font-size:14px; font-weight:600; cursor:pointer; }
button:hover { filter:brightness(1.12); }
button.ghost { background:var(--card2); border:1px solid var(--line); }
button.small { padding:7px 12px; font-size:12px; }
.film-card { display:flex; gap:16px; background:var(--card); border:1px solid var(--line); border-radius:14px; padding:14px; margin:12px 0; text-decoration:none; color:#e8e6f0; transition:transform .15s,border-color .15s; }
.film-card:hover { transform:translateY(-2px); border-color:var(--accent); }
.poster { width:128px; height:72px; object-fit:cover; border-radius:8px; flex-shrink:0; }
.poster.placeholder { display:flex; align-items:center; justify-content:center; background:var(--card2); font-size:28px; }
.film-title { font-size:16px; font-weight:700; margin-bottom:6px; }
.lang { font-size:11px; color:var(--accent); }
.film-meta { display:flex; gap:10px; flex-wrap:wrap; font-size:12px; color:var(--muted); }
.badge { background:rgba(224,90,90,.18); color:var(--accent); border-radius:20px; padding:2px 10px; font-weight:600; text-transform:uppercase; font-size:11px; }
.ok { color:var(--ok); }
.empty { color:var(--muted); text-align:center; padding:40px; }
.player video { width:100%; border-radius:12px; background:#000; }
.scene { border:1px solid var(--line); border-radius:10px; padding:14px; margin:12px 0; background:var(--card2); }
.scene-head { display:flex; gap:10px; align-items:center; margin-bottom:6px; }
.scene-num { color:var(--accent); font-size:11px; font-weight:700; letter-spacing:1px; }
.scene-heading { font-size:14px; font-weight:600; color:var(--accent2); }
.scene-action,.scene-narr { font-size:13px; color:#c8cade; margin:4px 0; }
.scene-dialogue { font-size:13px; color:var(--accent2); margin:6px 0; font-style:italic; }
.shot-row { display:flex; gap:12px; align-items:center; border-top:1px dashed var(--line); padding:8px 0 0; margin-top:8px; }
.shot-id { color:var(--muted); font-weight:700; }
.shot-cam { color:var(--accent2); min-width:110px; }
.shot-form { display:flex; gap:8px; align-items:center; flex-wrap:wrap; flex:1; }
.shot-prompt { flex:1; background:var(--card); font-size:12px; padding:7px 10px; min-width:220px; }
.shot-dur { width:70px; padding:7px 8px; }
.shot-thumb { width:110px; height:62px; object-fit:cover; border-radius:6px; border:1px solid var(--line); flex-shrink:0; }
.shot-thumb.ph { display:flex; align-items:center; justify-content:center; background:var(--card2); font-size:20px; }
button.mini { background:var(--card2); border:1px solid var(--line); color:var(--accent2); border-radius:6px; width:28px; height:28px; padding:0; font-size:13px; cursor:pointer; }
button.mini:hover { border-color:var(--accent); }
.shot-score { min-width:34px; text-align:center; border-radius:6px; padding:3px 6px; font-weight:700; font-size:12px; }
.score-ok { background:rgba(90,208,138,.18); color:#5ad08a; }
.score-weak { background:rgba(224,178,90,.18); color:#e0b25a; }
.score-bad { background:rgba(224,90,90,.22); color:#ff7b7b; }
.scores { display:flex; gap:8px; flex-wrap:wrap; margin:10px 0; }
.score { border-radius:16px; padding:4px 12px; font-size:12px; font-weight:700; }
.score.ok { background:rgba(90,208,138,.18); color:#5ad08a; }
.score.weak { background:rgba(224,178,90,.18); color:#e0b25a; }
.score.bad { background:rgba(224,90,90,.22); color:#ff7b7b; }
.avg { font-size:12px; color:var(--muted); }
.recs { margin:8px 0 0; padding-left:18px; font-size:13px; color:#c8cade; }
.recs li { margin:3px 0; }
.scene-actions { display:flex; gap:8px; margin-top:10px; align-items:center; }
a.danger { color:#ff7b7b; font-size:12px; }
textarea { background:var(--card2); border:1px solid var(--line); color:#fff; border-radius:8px; padding:10px 12px; font-size:14px; width:100%; resize:vertical; }
.dl { display:inline-block; background:var(--card2); border:1px solid var(--line); color:var(--accent2); text-decoration:none; border-radius:8px; padding:8px 12px; font-size:12px; margin:4px 6px 0 0; }
.dl:hover { border-color:var(--accent); }
.actions { display:flex; gap:10px; flex-wrap:wrap; margin:16px 0; }
#log { background:#05070c; border:1px solid var(--line); border-radius:10px; padding:12px; font-family:'Consolas',monospace; font-size:12px; max-height:260px; overflow:auto; white-space:pre-wrap; color:#b9f9c9; }
.muted { color:var(--muted); font-size:12px; }
.note { font-size:12px; color:var(--muted); margin-top:8px; }
ul.status { list-style:none; padding:0; }
ul.status li { padding:8px 0; border-bottom:1px dashed var(--line); font-size:13px; }
</style>
</head>
<body>
<header>
  <h1>🎬 AI FILM STUDIO</h1>
  <span class="tag">script → shots → voice → music → edit → render</span>
  <a href="/status">Provider Status</a>
</header>
<main>__BODY__</main>
</body>
</html>"""

_INDEX_TMPL = """
<div class="card">
  <h2>🎞 Naya Film Banao</h2>
  <form class="grid" method="post" action="/new">
    <label style="grid-column:span 2">Title <input name="title" required placeholder="Neon Rain"></label>
    <label>Genre <select name="genre">{genres}</select></label>
    <label>Language <select name="lang"><option value="en">English</option><option value="hi">हिन्दी</option></select></label>
    <label>Scenes <input name="scenes" type="number" value="3" min="1" max="12"></label>
    <label>Shots/scene <input name="shots" type="number" value="2" min="1" max="8"></label>
    <label>Shot duration (s) <input name="duration" type="number" value="4" step="0.5" min="2" max="15"></label>
    <label style="grid-column:span 3">Logline <input name="logline" placeholder="A young dreamer crosses the city on the last night before everything changes."></label>
    <div style="grid-column:1/-1"><button>🚀 Plan Film</button></div>
  </form>
</div>

<div class="card">
  <h2>📁 Aapke Films</h2>
  {films}
</div>
"""

_FILM_TMPL = """
<a href="/" style="color:var(--muted);font-size:13px;">← All films</a>
<div class="card">
  <h2>✏ Film Details</h2>
  <form method="post" action="/film/{slug}/meta" class="grid">
    <label style="grid-column:span 2">Title <input name="title" value="{title}"></label>
    <label>Genre <select name="genre">{genres}</select></label>
    <label style="grid-column:span 3">Logline <input name="logline" value="{logline}"></label>
    <label style="grid-column:span 3">Credits <input name="credits" value="{credits}"></label>
    <div style="grid-column:1/-1"><button class="small">💾 Save</button></div>
  </form>
</div>

<div class="card">
  <h2>🎛 Studio Controls</h2>
  <div class="actions">
    <button class="small" onclick="runJob('build')">🎥 Generate Assets</button>
    <button class="small" onclick="runJob('voice')">🗣 Voiceover</button>
    <button class="small" onclick="runJob('sound')">🎵 Soundtrack</button>
    <button class="small" onclick="runJob('render')">🎞 Render Movie</button>
    <button class="small" onclick="runJob('trailer')">🍿 Trailer</button>
    <button class="small" onclick="runJob('finish')">🎬 Cinematic Look</button>
    <button class="small" onclick="runJob('review')">🔍 AI Review</button>
    <button class="small" onclick="runJob('postpro')">🖼 Poster + Subtitles</button>
    <button class="small ghost" onclick="runJob('export')">📱 9:16 + 1:1 Export</button>
    <button class="small ghost" onclick="runJob('publish')">📤 Publish to YouTube</button>
  </div>
  <div class="note">
    Model: <select id="job-model">{models}</select>
    &nbsp; Voice lang: <select id="job-lang"><option>hi-IN</option><option>en-IN</option><option>en-US</option></select>
    &nbsp; <label style="display:inline"><input type="checkbox" id="job-silent"> offline silent</label>
    &nbsp; <span class="muted">* dissolve transitions + sfx + grade auto-apply on render</span>
  </div>
  <div id="logbox" style="display:none;margin-top:12px;"><div id="log"></div></div>
</div>

<div class="card">
  <h2>▶ Player</h2>
  {video}
  <div style="margin-top:10px;"><b class="muted">Downloads:</b> {downloads}</div>
</div>

{review_html}

<div class="card">
  <h2>📋 Timeline Editor <span class="muted">— reorder, add take, delete, edit prompt</span></h2>
  {scenes}
</div>
<p class="note">💡 Tip: 🔍 AI Review chalao — weak shots par score <b style="color:#ff7b7b">red</b> dikhega. Unhe regen karne ke liye CLI: <code>film_studio shot 3 --model kling-3.0</code></p>

<div class="card">
  <h2>🗑 Danger</h2>
  <form method="post" action="/film/{slug}/delete" onsubmit="return confirm('Film permanently delete honi hai?')">
    <button class="small" style="background:#7b2a2a;">🗑 Delete Film</button>
  </form>
</div>

<script>
const SLUG = {slug};
let current = null;
async function runJob(action) {{
  const extra = new URLSearchParams();
  extra.set('action', action);
  if (action === 'voice') {{ extra.set('lang', document.getElementById('job-lang').value);
     if (document.getElementById('job-silent').checked) extra.set('silent','1'); }}
  if (action === 'build') {{ extra.set('model', document.getElementById('job-model').value); }}
  if (action === 'postpro') {{ extra.set('ratios', '9:16 1:1'); }}
  const r = await fetch(`/film/${{SLUG}}/job`, {{method:'POST', body: extra}});
  const {{job}} = await r.json();
  current = job;
  document.getElementById('logbox').style.display = 'block';
  poll();
}}
async function poll() {{
  if (!current) return;
  const r = await fetch('/api/jobs/' + current);
  const d = await r.json();
  if (d.lines) document.getElementById('log').textContent = d.lines.slice(-60).join('\\n');
  if (d.state === 'done') {{ document.getElementById('log').textContent += '\\n✅ DONE — refresh page to see output.'; current = null; return; }}
  if (d.state === 'error') {{ document.getElementById('log').textContent += '\\n❌ ERROR'; current = null; return; }}
  setTimeout(poll, 1200);
}}
</script>
"""

_STATUS_TMPL = """
<a href="/" style="color:var(--muted);font-size:13px;">← Back</a>
<div class="card">
  <h2>🔌 Provider Status</h2>
  <ul class="status">{rows}</ul>
</div>
"""


def main() -> int:
    load_env()
    parser = argparse.ArgumentParser(description="AI Film Studio web UI")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    print(f"🎬 AI Film Studio web UI → http://{args.host}:{args.port}", flush=True)
    app.run(host=args.host, port=args.port, debug=False, threaded=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
