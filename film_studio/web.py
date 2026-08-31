"""Web UI for AI Film Studio — run the whole studio from a browser.

Usage:
    python -m film_studio.web [--host 0.0.0.0] [--port 8080]
"""

from __future__ import annotations

import argparse
import os
import queue
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
        <div class="film-title">{f['title']}</div>
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
    scenes = max(1, min(int(request.form.get("scenes", 3)), 12))
    shots = max(1, min(int(request.form.get("shots", 2)), 8))
    duration = max(2.0, min(float(request.form.get("duration", 4)), 15))
    project = plan_film(title, request.form.get("logline", ""), genre, scenes=scenes, shots=shots, duration=duration)
    return redirect(url_for("film", slug=project.film.slug))


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
        video = f'''
        <div class="player">
          <video controls preload="metadata" poster="{url_for('movie_file', slug=slug, filename='poster.png') if (root/'movie'/'poster.png').exists() else ''}">
            <source src="{url_for('movie_file', slug=slug, filename=movie.name)}" type="video/mp4">
          </video>
        </div>'''
    downloads = _download_links(root, slug)
    return render_page(
        _FILM_TMPL.format(
            title=project.film.title,
            genre=project.film.genre,
            logline=project.film.logline or "(no logline)",
            scenes=scenes_html,
            video=video,
            downloads=downloads,
            slug=slug,
            models=" ".join(f'<option value="{m}">{m}</option>' for m in MODELS),
        )
    )


def _scene_block(project, scene) -> str:
    shots = ""
    for s in scene.shots:
        shots += f'<div class="shot"><span class="shot-id">#{s.index+1}</span><span class="shot-cam">{s.camera}</span><span class="shot-prompt">{s.prompt}</span></div>'
    return f"""
    <div class="scene">
      <div class="scene-head"><span class="scene-num">SCENE {scene.number}</span><span class="scene-heading">{scene.heading}</span></div>
      <div class="scene-action">{scene.action}</div>
      {f'<div class="scene-narr">🗣 {scene.narration}</div>' if scene.narration else ''}
      {shots}
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


@app.get("/film/<slug>/movie/<path:filename>")
def movie_file(slug: str, filename: str):
    root, _ = _movie_dir(slug)
    if root is None:
        return ("not found", 404)
    safe = secure_filename(filename)
    if not safe or not (root / safe).exists():
        return ("not found", 404)
    return send_from_directory(root, safe, conditional=True)


@app.get("/status")
def status():
    rows = "".join(f'<li><b>{s.name}</b> — {"✅ " if s.available else "❌ "}{s.detail}</li>' for s in check_providers())
    return render_page(_STATUS_TMPL.format(rows=rows))


# ---------------------------------------------------------------------------
# Page shell
# ---------------------------------------------------------------------------
GENRES = ["scifi", "action", "romance", "horror", "documentary", "commercial", "drama"]
MODELS = ["kling-3.0", "veo-3.1-fast", "ltx-2.5-pro", "minimax-h3", "qwen-image-3", "nano-banana-2", "gpt-image-2"]


def json_safe(v: str) -> str:
    import json
    return json.dumps(v)


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
.shot { display:flex; gap:10px; align-items:baseline; font-size:12px; border-top:1px dashed var(--line); padding:7px 0 0; margin-top:7px; }
.shot-id { color:var(--muted); font-weight:700; }
.shot-cam { color:var(--accent2); min-width:110px; }
.shot-prompt { color:var(--muted); }
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
  <span class="tag">script → shots → voice → music → render</span>
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
  <div style="display:flex;align-items:center;gap:14px;">
    <h2 style="font-size:22px;margin:0;">{title}</h2>
    <span class="badge">{genre}</span>
  </div>
  <p class="muted">{logline}</p>
</div>

<div class="card">
  <h2>🎛 Studio Controls</h2>
  <div class="actions">
    <button class="small" onclick="runJob('build')">🎥 Generate Assets</button>
    <button class="small" onclick="runJob('voice')">🗣 Voiceover (Hindi)</button>
    <button class="small" onclick="runJob('sound')">🎵 Soundtrack</button>
    <button class="small" onclick="runJob('render')">🎞 Render Movie</button>
    <button class="small" onclick="runJob('postpro')">🖼 Poster + Subtitles</button>
    <button class="small ghost" onclick="runJob('export')">📱 9:16 + 1:1 Export</button>
  </div>
  <div class="note">
    Assets model: <select id="job-model">{models}</select>
    &nbsp; Voice lang: <select id="job-lang"><option>hi-IN</option><option>en-IN</option><option>en-US</option></select>
    &nbsp; <label style="display:inline"><input type="checkbox" id="job-silent"> offline silent</label>
  </div>
  <div id="logbox" style="display:none;margin-top:12px;"><div id="log"></div></div>
</div>

<div class="card">
  <h2>▶ Player</h2>
  {video}
  <div style="margin-top:10px;"><b class="muted">Downloads:</b> {downloads}</div>
</div>

<div class="card">
  <h2>📋 Storyboard</h2>
  {scenes}
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
