"""film-studio CLI — the whole studio from one command."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import check_providers, load_env
from .pipeline import make_project, plan_film, produce_film
from .project import load_project
from .voice import EDGE_VOICES, generate_narration


def _p(msg: str) -> None:
    print(msg, flush=True)


def _find_project(args) -> Path:
    if args.project:
        root = Path(args.project)
        if root.is_file():
            root = root.parent
        return root
    films = Path(__file__).resolve().parent.parent / "films"
    if films.exists():
        projects = sorted([d for d in films.iterdir() if (d / "film.json").exists()], key=lambda d: d.stat().st_mtime, reverse=True)
        if projects:
            return projects[0]
    raise SystemExit("No project found. Run: python -m film_studio new \"My Film\"")


def cmd_new(args) -> int:
    _p(f"🎬 Planning film: {args.title!r} ({args.genre}, {args.lang})")
    project = plan_film(args.title, args.logline, args.genre, scenes=args.scenes, shots=args.shots, duration=args.duration, lang=args.lang)
    if args.lang == "hi":
        _p("   📝 Hindi screenplay + dialogue ready (Devanagari)")
    _p(f"   Project folder: {project.root}")
    _p(f"   Scenes: {len(project.film.scenes)} | Shots: {len(project.shots)}")
    _p(f"   Screenplay: {project.root / 'script' / 'screenplay.txt'}")
    _p("   Next: film-studio build --model kling-3.0")
    return 0


def cmd_plan(args) -> int:
    project = load_project(_find_project(args))
    _p(f"📋 {project.film.title} — {len(project.film.scenes)} scenes, {len(project.shots)} shots")
    for scene in project.film.scenes:
        _p(f"  Scene {scene.number}: {scene.heading}")
        for shot in scene.shots:
            _p(f"    [{shot.index + 1}] {shot.duration:.1f}s {shot.camera} — {shot.prompt[:110]}…")
    return 0


def cmd_build(args) -> int:
    load_env()
    project = load_project(_find_project(args))
    _p(f"🎥 Generating assets for {project.film.title} (model: {args.model}, workers={args.workers})")
    make_project(project, shots=args.shots, duration=args.duration, model=args.model, workers=args.workers, on_status=lambda s: _p(f"      status: {s}"))
    _p("✅ Assets generated. Next: film-studio voice")
    return 0


def cmd_voice(args) -> int:
    project = load_project(_find_project(args))
    _p("🎙 Generating narration…")
    paths = generate_narration(project, voice=args.voice, lang=args.lang, force_silent=args.silent)
    for k, v in paths.items():
        _p(f"   Scene {k}: {v}")
    _p("✅ Voiceover done. Next: film-studio render")
    return 0


def cmd_render(args) -> int:
    project = load_project(_find_project(args))
    _p(f"🎞 Rendering final film… ({args.transition} transitions, sfx={not args.no_sfx}, watermark={not args.no_watermark})")
    out = produce_film(project, cinematic=not args.no_look, transition=args.transition, sfx=not args.no_sfx, watermark=not args.no_watermark)
    _p(f"✅ Movie ready: {out}")
    _p(f"   Runtime: {project.film.duration:.0f}s | {out.stat().st_size / 1e6:.1f} MB")
    return 0


def cmd_finish(args) -> int:
    project = load_project(_find_project(args))
    movie = project.root / "movie" / f"{project.film.slug}.mp4"
    if not movie.exists():
        _p("❌ Movie not rendered yet. Run: film-studio render")
        return 1
    _p(f"🎬 Applying cinematic look (grain={args.grain}, bars={not args.no_bars})…")
    from .finish import apply_film_look

    apply_film_look(movie, grain=args.grain, bars=not args.no_bars)
    _p(f"✅ Cinematic finish done → {movie}")
    return 0


def cmd_shot(args) -> int:
    project = load_project(_find_project(args))
    shot = project.shots[args.index - 1]
    _p(f"🎯 Regenerating shot #{args.index}…\n   Prompt: {shot.prompt[:90]}")
    from .pipeline import regenerate_shot

    updated = regenerate_shot(project, args.index - 1, model=args.model, on_status=lambda s: _p(f"      status: {s}"))
    _p(f"✅ Shot updated → {updated.local_asset}")
    return 0


def cmd_rename(args) -> int:
    project = load_project(_find_project(args))
    _p(f"✏ Renaming '{project.film.title}' → '{args.title}'")
    from .project import rename_project

    updated = rename_project(project.root, args.title)
    _p(f"✅ {updated.film.title} ({updated.film.slug})")
    return 0


def cmd_delete(args) -> int:
    project = load_project(_find_project(args))
    if not args.yes:
        _p(f"⚠ '{project.film.title}' delete karna hai? '--yes' ke saath chalao.")
        return 1
    from .project import delete_project

    delete_project(project.root)
    _p("🗑 Deleted.")
    return 0


def cmd_scene(args) -> int:
    project = load_project(_find_project(args))
    scenes = project.film.scenes
    if not (1 <= args.number <= len(scenes)):
        _p(f"❌ Scene 1-{len(scenes)} hi valid hai")
        return 1
    scene = scenes[args.number - 1]
    if args.heading is not None:
        scene.heading = args.heading
    if args.action is not None:
        scene.action = args.action
    if args.narration is not None:
        scene.narration = args.narration
    if args.dialogue is not None:
        scene.dialogue = args.dialogue
    from .project import save_project

    save_project(project)
    _p(f"✅ Scene {scene.number} updated")
    return 0


def cmd_review(args) -> int:
    project = load_project(_find_project(args))
    _p(f"🔍 AI review of '{project.film.title}'…")
    from .review import review_project

    report = review_project(project, threshold=args.threshold)
    _p(f"   Shots analyzed: {report['shots_analyzed']} | Average: {report['average_score']}/10")
    weak = report["weak_shots"]
    if weak:
        _p(f"   ⚠{len(weak)} weak shots: {weak} — regenerate karne ke liye: film_studio shot <no>")
        for rec in report["recommendations"][:10]:
            _p(f"     • {rec}")
    else:
        _p("   ✅ Sab shots strong hain!")
    _p(f"   Report: {project.root / 'render' / 'review.json'}")
    return 0


def cmd_publish(args) -> int:
    project = load_project(_find_project(args))
    movie = project.root / "movie" / f"{project.film.slug}.mp4"
    if not movie.exists():
        _p("❌ Movie not rendered yet. Run: film-studio render")
        return 1
    _p(f"📤 Uploading '{project.film.title}' to YouTube…")
    from .youtube import upload_film

    url = upload_film(project, movie, title=args.title or None, privacy=args.privacy, tags=args.tags.split(",") if args.tags else None)
    _p(f"✅ LIVE: {url}")
    return 0


def cmd_trailer(args) -> int:
    project = load_project(_find_project(args))
    _p("🎬 Making trailer (fast cuts + music + COMING SOON)…")
    from .trailer import make_trailer

    out = make_trailer(project)
    _p(f"✅ Trailer ready: {out}")
    return 0


def cmd_sound(args) -> int:
    project = load_project(_find_project(args))
    _p(f"🎵 Generating {project.film.genre} soundtrack…")
    from .music import generate_theme

    theme = generate_theme(project)
    _p(f"   Theme: {theme}")
    movie = project.root / "movie" / f"{project.film.slug}.mp4"
    if movie.exists():
        _p("   Mixing into existing movie…")
        from .render import mix_music

        mix_music(project, movie, theme)
        _p("✅ Music mixed")
    else:
        _p("✅ Theme ready (run 'render' to mix it)")
    return 0


def cmd_postpro(args) -> int:
    project = load_project(_find_project(args))
    movie = project.root / "movie" / f"{project.film.slug}.mp4"
    if not movie.exists():
        _p("❌ Movie not rendered yet. Run: film-studio render")
        return 1
    from .render import build_subtitle_cues, export_aspect, make_poster, write_srt

    _p("🖼 Creating poster + thumbnail…")
    poster = make_poster(project, movie)
    _p(f"   {poster}")

    _p("📝 Writing subtitles…")
    srt = write_srt(project, build_subtitle_cues(project))
    _p(f"   {srt}")

    if args.ratios:
        for ratio in args.ratios:
            _p(f"   Exporting {ratio}…")
            out = export_aspect(project, movie, ratio)
            _p(f"   {out}")
    _p("✅ Post-production done")
    return 0


def cmd_export(args) -> int:
    project = load_project(_find_project(args))
    movie = project.root / "movie" / f"{project.film.slug}.mp4"
    if not movie.exists():
        _p("❌ Movie not rendered yet. Run: film-studio render")
        return 1
    from .render import export_aspect

    out = export_aspect(project, movie, args.ratio)
    _p(f"✅ Exported: {out}")
    return 0


def cmd_all(args) -> int:
    load_env()
    _p("=" * 60)
    _p("🎬 AI FILM STUDIO — FULL PRODUCTION")
    _p("=" * 60)
    project = plan_film(args.title, args.logline, args.genre, scenes=args.scenes, shots=args.shots, duration=args.duration, lang=args.lang)
    _p(f"[1/4] Project planned → {project.root}")

    _p("[2/4] Generating shots…")
    make_project(project, shots=args.shots, duration=args.duration, model=args.model, workers=args.workers, on_status=lambda s: _p(f"      status: {s}"))

    _p("[3/4] Generating narration…")
    generate_narration(project, voice=args.voice, lang=args.voice_lang, force_silent=args.silent)

    _p("[4/4] Rendering film (transitions + music + sfx + subtitles)…")
    out = produce_film(project, transition=args.transition, sfx=not args.no_sfx)
    _p("=" * 60)
    _p(f"✅ FILM COMPLETE: {out}")
    _p(f"   Runtime ~{project.film.duration:.0f}s | {out.stat().st_size / 1e6:.1f} MB")

    if args.poster:
        from .render import make_poster

        poster = make_poster(project, out)
        _p(f"   Poster: {poster}")
    if args.ratios:
        from .render import export_aspect

        for ratio in args.ratios:
            exported = export_aspect(project, out, ratio)
            _p(f"   {ratio} export: {exported}")
    _p("=" * 60)
    return 0


def cmd_status(args) -> int:
    _p("🔌 Provider status:")
    for st in check_providers():
        mark = "✅" if st.available else ("⚠️" if st.name.startswith("edge") else "❌")
        _p(f"  {mark} {st.name}: {st.detail}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--project", help="Project folder (default: latest film)")

    parser = argparse.ArgumentParser(prog="film-studio", description="AI Film Studio — script → shots → voice → render")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("new", help="Create a new film project", parents=[common])
    sp.add_argument("title")
    sp.add_argument("--logline", default="")
    sp.add_argument("--genre", default="drama", choices=["scifi", "action", "romance", "horror", "documentary", "commercial", "drama"])
    sp.add_argument("--lang", default="en", choices=["en", "hi"], help="Screenplay/narration language")
    sp.add_argument("--scenes", type=int, default=3)
    sp.add_argument("--shots", type=int, default=2)
    sp.add_argument("--duration", type=float, default=4.0)

    sub.add_parser("plan", help="Show the storyboard plan", parents=[common])

    sp = sub.add_parser("build", help="Generate shot assets (images/videos)", parents=[common])
    sp.add_argument("--model", default="kling-3.0", choices=["kling-3.0", "veo-3.1-fast", "ltx-2.5-pro", "minimax-h3", "qwen-image-3", "nano-banana-2", "gpt-image-2"])
    sp.add_argument("--shots", type=int, default=0, help="Shots per scene (0 = all shots)")
    sp.add_argument("--workers", type=int, default=1, help="Parallel generations (1-4)")
    sp.add_argument("--duration", type=float, default=4.0)

    sp = sub.add_parser("voice", help="Generate voiceover narration", parents=[common])
    sp.add_argument("--voice", default="auto", help="edge-tts voice or ElevenLabs name")
    sp.add_argument("--lang", default="en-IN")
    sp.add_argument("--silent", action="store_true", help="Force silent tracks (offline mode)")

    sp = sub.add_parser("render", help="Render the final movie", parents=[common])
    sp.add_argument("--no-look", action="store_true", help="Skip cinematic letterbox/grain")
    sp.add_argument("--no-sfx", action="store_true", help="Skip whoosh/riser sound effects")
    sp.add_argument("--no-watermark", action="store_true", help="Skip corner watermark")
    sp.add_argument("--transition", default="dissolve", choices=["dissolve", "fade-soft", "wipe", "circle", "none"])

    sp = sub.add_parser("finish", help="Apply cinematic look to rendered movie", parents=[common])
    sp.add_argument("--grain", type=int, default=6, help="Film grain strength (0=off)")
    sp.add_argument("--no-bars", action="store_true", help="Skip 2.35:1 letterbox")

    sub.add_parser("trailer", help="Make a fast-cut teaser trailer", parents=[common])

    sp = sub.add_parser("shot", help="Regenerate one shot by number", parents=[common])
    sp.add_argument("index", type=int, help="1-based shot number")
    sp.add_argument("--model", default="kling-3.0", choices=["kling-3.0", "veo-3.1-fast", "ltx-2.5-pro", "minimax-h3", "qwen-image-3", "nano-banana-2", "gpt-image-2"])

    sp = sub.add_parser("rename", help="Rename the film", parents=[common])
    sp.add_argument("title")

    sp = sub.add_parser("delete", help="Delete the film project", parents=[common])
    sp.add_argument("--yes", action="store_true")

    sp = sub.add_parser("publish", help="Upload the movie to YouTube", parents=[common])
    sp.add_argument("--title", default="")
    sp.add_argument("--privacy", default="public", choices=["public", "unlisted", "private"])
    sp.add_argument("--tags", default="AI film, short film, AI generated")

    sp = sub.add_parser("review", help="AI quality review of all shots", parents=[common])
    sp.add_argument("--threshold", type=float, default=6.0, help="Score below this = weak")

    sp = sub.add_parser("scene", help="Edit scene metadata (heading/action/narration/dialogue)", parents=[common])
    sp.add_argument("number", type=int)
    sp.add_argument("--heading")
    sp.add_argument("--action")
    sp.add_argument("--narration")
    sp.add_argument("--dialogue")
    sub.add_parser("sound", help="Generate genre soundtrack + mix into movie", parents=[common])

    sp = sub.add_parser("postpro", help="Poster + subtitles + platform exports", parents=[common])
    sp.add_argument("--ratios", nargs="*", default=[], choices=["9:16", "1:1"], help="Export aspect ratios")

    sp = sub.add_parser("export", help="Export a platform version (9:16 / 1:1)", parents=[common])
    sp.add_argument("--ratio", default="9:16", choices=["9:16", "1:1"])

    sp = sub.add_parser("all", help="Full pipeline in one command", parents=[common])
    sp.add_argument("title")
    sp.add_argument("--logline", default="")
    sp.add_argument("--genre", default="drama", choices=["scifi", "action", "romance", "horror", "documentary", "commercial", "drama"])
    sp.add_argument("--lang", default="en", choices=["en", "hi"])
    sp.add_argument("--scenes", type=int, default=3)
    sp.add_argument("--shots", type=int, default=2)
    sp.add_argument("--workers", type=int, default=1, help="Parallel generations (1-4)")
    sp.add_argument("--duration", type=float, default=4.0)
    sp.add_argument("--model", default="kling-3.0", choices=["kling-3.0", "veo-3.1-fast", "ltx-2.5-pro", "minimax-h3", "qwen-image-3", "nano-banana-2", "gpt-image-2"])
    sp.add_argument("--transition", default="dissolve", choices=["dissolve", "fade-soft", "wipe", "circle", "none"])
    sp.add_argument("--no-sfx", action="store_true")
    sp.add_argument("--voice", default="auto")
    sp.add_argument("--voice-lang", default="hi-IN", help="en-IN, hi-IN, en-US, en-GB…")
    sp.add_argument("--silent", action="store_true", help="Force silent tracks (offline mode)")
    sp.add_argument("--poster", action="store_true", help="Also make poster + thumbnail")
    sp.add_argument("--ratios", nargs="*", default=[], choices=["9:16", "1:1"], help="Extra platform exports")

    sub.add_parser("status", help="Show provider/key status")
    return parser


def main(argv=None) -> int:
    load_env()
    args = build_parser().parse_args(argv)
    try:
        return {
            "new": cmd_new,
            "plan": cmd_plan,
            "build": cmd_build,
            "voice": cmd_voice,
            "render": cmd_render,
            "finish": cmd_finish,
            "trailer": cmd_trailer,
            "shot": cmd_shot,
            "rename": cmd_rename,
            "delete": cmd_delete,
            "publish": cmd_publish,
            "review": cmd_review,
            "scene": cmd_scene,
            "sound": cmd_sound,
            "postpro": cmd_postpro,
            "export": cmd_export,
            "all": cmd_all,
            "status": cmd_status,
        }[args.cmd](args)
    except KeyboardInterrupt:
        _p("\nStopped.")
        return 130
    except Exception as exc:
        _p(f"❌ {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
