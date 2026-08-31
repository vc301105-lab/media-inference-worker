"""Render: images/videos/audio -> final film with ffmpeg (captions + title/credits)."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .project import Film, Project

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def _ffmpeg() -> str:
    import imageio_ffmpeg

    exe = imageio_ffmpeg.get_ffmpeg_exe()
    if not exe or not Path(exe).exists():
        raise RuntimeError("ffmpeg not found — pip install imageio-ffmpeg")
    return exe


def _font(size: int, bold: bool = False):
    path = FONT_BOLD if bold else FONT
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


def _wrap(text: str, font, max_w: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for word in words:
        trial = (cur + " " + word).strip()
        if ImageDraw.Draw(Image.new("RGB", (1, 1))).textlength(trial, font=font) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def make_title_card(text: str, sub: str, out: Path, w: int = 1280, h: int = 720) -> Path:
    img = Image.new("RGB", (w, h), (8, 10, 16))
    draw = ImageDraw.Draw(img)
    # subtle vignette frame
    for i in range(0, 140, 4):
        draw.rectangle([i, i, w - i, h - i], outline=(10 + i // 6, 12 + i // 8, 20 + i // 6))
    title_font = _font(62, bold=True)
    sub_font = _font(28)
    lines = _wrap(text.upper(), title_font, w - 160)
    line_h = 74
    y = h / 2 - (len(lines) * line_h) / 2 - 30
    for line in lines:
        tw = draw.textlength(line, font=title_font)
        draw.text(((w - tw) / 2, y), line, font=title_font, fill=(235, 220, 190))
        y += line_h
    if sub:
        sw = draw.textlength(sub, font=sub_font)
        draw.text(((w - sw) / 2, h / 2 + 60), sub, font=sub_font, fill=(160, 160, 175))
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    return out


def make_credit_card(text: str, out: Path, w: int = 1280, h: int = 720) -> Path:
    img = Image.new("RGB", (w, h), (8, 10, 16))
    draw = ImageDraw.Draw(img)
    font = _font(38, bold=True)
    lines = _wrap(text, font, w - 160) if len(text) > 70 else (text.splitlines() or [text])
    y = h / 2 - (len(lines) * 55) / 2
    for line in lines:
        ww = draw.textlength(line, font=font)
        draw.text(((w - ww) / 2, y), line, font=font, fill=(220, 205, 180))
        y += 55
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    return out


def _probe_duration(path: Path) -> float:
    ffmpeg = _ffmpeg()
    cmd = [
        ffmpeg, "-i", str(path), "-f", "null", "-",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    import re

    m = re.search(r"Duration: (\d+):(\d+):(\d+\.?\d*)", proc.stderr)
    if not m:
        return 4.0
    h, mn, s = int(m.group(1)), int(m.group(2)), float(m.group(3))
    return h * 3600 + mn * 60 + s


def probe_duration(path: Path) -> float:
    return _probe_duration(path)


def make_silent_audio(duration: float, out: Path) -> Path:
    """Generate a silent audio track (keeps film timing when no TTS available)."""
    ffmpeg = _ffmpeg()
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg, "-y",
        "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo",
        "-t", f"{max(duration, 1.0):.3f}",
        "-c:a", "libmp3lame", "-q:a", "9", str(out),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not out.exists():
        raise RuntimeError(f"silent audio failed: {proc.stderr[-300:]}")
    return out


def _prep_image(src: Path, caption: str, work: Path) -> Path:
    """Center-crop to 16:9, resize, and burn a caption with Pillow (no drawtext needed)."""
    img = Image.open(src).convert("RGB")
    w, h = img.size
    target = 16 / 9
    if w / h > target:
        new_h = h
        new_w = int(h * target)
        x = (w - new_w) // 2
        img = img.crop((x, 0, x + new_w, h))
    else:
        new_w = w
        new_h = int(w / target)
        y = (h - new_h) // 2
        img = img.crop((0, y, w, y + new_h))
    img = img.resize((1280, 720), Image.LANCZOS)

    if caption:
        safe = caption.replace(":", " ").replace("\n", " ").strip()[:52]
        draw = ImageDraw.Draw(img)
        font = _font(30, bold=True)
        text_w = draw.textlength(safe, font=font)
        pad_x, pad_y = 16, 10
        box_w = int(text_w) + pad_x * 2
        box_h = 46
        x0 = (1280 - box_w) // 2
        y0 = 720 - 90
        box = Image.new("RGBA", (box_w, box_h), (0, 0, 0, 130))
        img.paste(box, (x0, y0), box)
        draw.text((x0 + pad_x, y0 + pad_y - 2), safe, font=font, fill=(255, 255, 255))

    work.mkdir(parents=True, exist_ok=True)
    out = work / f"prep-{src.stem}.png"
    img.save(out)
    return out


def _make_clip(
    image: Path,
    audio: Path | None,
    duration: float,
    out: Path,
    caption: str = "",
    fps: int = 24,
    work: Path | None = None,
    kenburns: bool = True,
) -> Path:
    """Still image -> motion clip (Ken Burns pan) with optional audio and caption."""
    ffmpeg = _ffmpeg()
    out.parent.mkdir(parents=True, exist_ok=True)
    prepared = _prep_image(image, caption, work or out.parent)

    if kenburns:
        # Slow zoom-in starting from full frame (never crops edges at t=0)
        vf = f"zoompan=z='min(zoom+0.0008,1.08)':d={int(duration*fps)}:s=1280x720:fps={fps}"
    else:
        vf = "scale=1280:720"

    cmd = [ffmpeg, "-y", "-loop", "1", "-i", str(prepared), "-t", f"{duration:.3f}"]
    if audio and Path(audio).exists():
        cmd += ["-i", str(audio)]
        cmd += ["-c:v", "libx264", "-preset", "fast", "-tune", "stillimage", "-c:a", "aac", "-b:a", "192k", "-shortest"]
    else:
        cmd += ["-c:v", "libx264", "-preset", "fast", "-tune", "stillimage", "-an"]
    cmd += ["-vf", vf, "-r", str(fps), "-pix_fmt", "yuv420p", str(out)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not out.exists():
        raise RuntimeError(f"clip render failed: {proc.stderr[-500:]}")
    return out


def _make_video_clip(video: Path, audio: Path | None, duration: float, out: Path) -> Path:
    """Use an existing video asset: trim to duration and normalize (no drawtext)."""
    ffmpeg = _ffmpeg()
    out.parent.mkdir(parents=True, exist_ok=True)
    vf = "scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720"
    cmd = [ffmpeg, "-y", "-i", str(video), "-t", f"{duration:.3f}", "-vf", vf]
    if audio and Path(audio).exists():
        cmd += ["-i", str(audio), "-c:v", "libx264", "-preset", "fast", "-c:a", "aac", "-shortest"]
    else:
        cmd += ["-c:v", "libx264", "-preset", "fast", "-an"]
    cmd += ["-r", "24", "-pix_fmt", "yuv420p", str(out)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not out.exists():
        raise RuntimeError(f"video clip failed: {proc.stderr[-400:]}")
    return out


def _concat(parts: list[Path], out: Path) -> Path:
    ffmpeg = _ffmpeg()
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
        for p in parts:
            fh.write(f"file '{p.resolve()}'\n")
        listfile = fh.name
    cmd = [ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", listfile, "-c", "copy", str(out)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not out.exists():
        raise RuntimeError(f"concat failed: {proc.stderr[-500:]}")
    return out


# ---------------------------------------------------------------------------
# Post-production: music mix, subtitles, poster, platform exports
# ---------------------------------------------------------------------------

def mix_music(project: Project, movie: Path, theme: Path) -> Path:
    """Mux the genre soundtrack under the film's audio at low volume."""
    ffmpeg = _ffmpeg()
    tmp = movie.with_suffix(".music.mkv")
    cmd = [
        ffmpeg, "-y",
        "-i", str(movie), "-i", str(theme),
        "-filter_complex",
        "[0:a]volume=1.0[voice];[1:a]volume=0.22[music];"
        "[voice][music]amix=inputs=2:duration=first:dropout_transition=2:normalize=0[a]",
        "-map", "0:v", "-map", "[a]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", str(tmp),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not tmp.exists():
        raise RuntimeError(f"music mix failed: {proc.stderr[-400:]}")
    tmp.replace(movie)
    return movie


def build_subtitle_cues(project: Project) -> list[tuple[float, float, str]]:
    """Recompute subtitle cues from the deterministic render timeline."""
    cues: list[tuple[float, float, str]] = []
    cursor = 3.0  # title card
    narration = {p.stem.replace("scene-", ""): p for p in (project.root / "voice").glob("scene-*.mp3")}
    for scene in project.film.scenes:
        scene_len = sum(s.duration for s in scene.shots)
        if scene.narration:
            start = cursor
            end = cursor + scene_len
            audio = narration.get(str(scene.number))
            if audio and Path(audio).exists():
                d = _probe_duration(audio)
                if d > 0:
                    end = min(start + d, start + scene_len)
            cues.append((start, end, scene.narration))
        cursor += scene_len
    return cues


def write_srt(project: Project, cues: list[tuple[float, float, str]]) -> Path:
    """Write subtitles.srt from (start, end, text) cues."""
    def ts(sec: float) -> str:
        h, rem = divmod(max(sec, 0), 3600)
        m, s = divmod(rem, 60)
        return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int((s % 1) * 1000):03d}"

    lines = []
    for i, (start, end, text) in enumerate(cues, 1):
        lines += [str(i), f"{ts(start)} --> {ts(end)}", text, ""]
    out = project.root / "movie" / "subtitles.srt"
    out.write_text("\n".join(lines))
    return out


def make_poster(project: Project, movie: Path) -> Path:
    """Extract a frame from the first scene and overlay title + genre badge."""
    ffmpeg = _ffmpeg()
    frame = project.root / "render" / "poster-base.png"
    subprocess.run(
        [ffmpeg, "-y", "-ss", "4", "-i", str(movie), "-frames:v", "1", str(frame)],
        capture_output=True,
    )
    if not frame.exists():
        raise RuntimeError("poster frame extraction failed")

    img = Image.open(frame).convert("RGB")
    img = img.resize((1280, 720), Image.LANCZOS)
    draw = ImageDraw.Draw(img)
    # dark gradient at bottom for title legibility
    for y in range(300, 720):
        alpha = int(140 * (y - 300) / 420)
        draw.line([(0, y), (1280, y)], fill=(0, 0, 0, alpha))
    film = project.film
    title_font = _font(64, bold=True)
    badge_font = _font(28, bold=True)
    lines = _wrap(film.title.upper(), title_font, 1160)
    y = 470
    for line in lines:
        tw = draw.textlength(line, font=title_font)
        draw.text(((1280 - tw) / 2, y), line, font=title_font, fill=(245, 235, 210))
        y += 72
    badge = f"  {film.genre.upper()}  |  AI FILM STUDIO  "
    bw = draw.textlength(badge, font=badge_font) + 20
    bx, by = (1280 - bw) / 2, min(y + 8, 660)
    box = Image.new("RGBA", (int(bw), 44), (200, 60, 60, 220))
    img.paste(box, (int(bx), int(by)), box)
    draw.text((int(bx) + 10, int(by) + 6), badge, font=badge_font, fill=(255, 255, 255))

    poster = project.root / "movie" / "poster.png"
    img.save(poster)
    thumb = project.root / "movie" / "thumbnail.jpg"
    img.resize((640, 360), Image.LANCZOS).save(thumb, quality=85)
    return poster


def export_aspect(project: Project, movie: Path, ratio: str = "9:16") -> Path:
    """Export vertical (9:16) or square (1:1) version with blurred background."""
    ffmpeg = _ffmpeg()
    sizes = {"9:16": (720, 1280), "1:1": (1080, 1080)}
    if ratio not in sizes:
        raise RuntimeError(f"unsupported ratio {ratio} (use 9:16 or 1:1)")
    w, h = sizes[ratio]
    fg_w = w if w < 1280 else 1280
    fg_h = int(fg_w * 9 / 16)
    out = project.root / "movie" / f"{project.film.slug}-{ratio.replace(':', 'x')}.mp4"
    fc = (
        f"[0:v]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},"
        f"boxblur=24:2[bg];"
        f"[0:v]scale={fg_w}:{fg_h}[fg];"
        f"[bg][fg]overlay=(W-w)/2:(H-h)/2[v]"
    )
    cmd = [
        ffmpeg, "-y", "-i", str(movie),
        "-filter_complex", fc,
        "-map", "[v]", "-map", "0:a?",
        "-c:v", "libx264", "-preset", "fast", "-c:a", "aac", "-b:a", "160k",
        "-r", "24", "-pix_fmt", "yuv420p", str(out),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not out.exists():
        raise RuntimeError(f"export failed: {proc.stderr[-400:]}")
    return out


def render_film(project: Project, with_music: bool = True, cinematic: bool = True, transition: str = "dissolve", sfx: bool = True) -> Path:
    """Render the whole film: title card + per-shot clips (+ narration where available).

    - Narration longer than the scene → last shot auto-extends (voice never cut off).
    - transition: dissolve/fade-soft/wipe/circle between shots.
    - sfx=True adds whooshes at scene boundaries + riser at title.
    - cinematic=True applies genre grade + 2.35:1 letterbox + grain + vignette.
    Also writes subtitles.srt and mixes the genre soundtrack if it exists.
    """
    film = project.film
    render_dir = project.root / "render"
    clips_dir = render_dir / "clips"
    deliverable = project.root / "movie" / f"{film.slug}.mp4"
    deliverable.parent.mkdir(parents=True, exist_ok=True)

    parts: list[Path] = []
    cues: list[tuple[float, float, str]] = []
    sfx_events: list[tuple[float, str]] = []
    cursor = 0.0

    title = make_title_card(film.title.upper(), film.logline or film.genre, render_dir / "title.png")
    title_silent = make_silent_audio(3.0, render_dir / "title-silent.mp3")
    parts.append(_make_clip(title, title_silent, 3.0, clips_dir / "title.mp4", kenburns=False))
    cursor += 3.0

    narration = {
        p.stem.replace("scene-", ""): p for p in (project.root / "voice").glob("scene-*.mp3")
    }

    sfx_events.append((0.0, "riser"))
    for scene in film.scenes:
        scene_audio = narration.get(str(scene.number))
        # Sync: if narration audio is longer than the scene's shots, extend the last shot
        if scene_audio and Path(scene_audio).exists():
            need = _probe_duration(Path(scene_audio))
            have = sum(s.duration for s in scene.shots)
            if need > have + 0.4:
                scene.shots[-1].duration += (need - have)
        if scene.number > 1:
            sfx_events.append((cursor, "whoosh"))
        scene_start = cursor
        scene_len = 0.0
        for shot in scene.shots:
            asset = Path(shot.local_asset) if shot.local_asset else None
            if not asset or not asset.exists():
                # fallback: render a placeholder gradient card from the prompt
                asset = make_title_card("SHOT", shot.prompt[:70], render_dir / f"shot-{shot.index}.png")
            clip_name = f"shot-{shot.index:02d}.mp4"
            audio_path = scene_audio if scene_audio and Path(scene_audio).exists() else None
            if asset.suffix.lower() in {".mp4", ".mov", ".webm", ".m4v"}:
                clip = _make_video_clip(asset, audio_path, shot.duration, clips_dir / clip_name)
            else:
                clip = _make_clip(
                    asset,
                    audio_path,
                    shot.duration,
                    clips_dir / clip_name,
                    caption=scene.heading if scene.heading else "",
                    work=render_dir / "prep",
                )
            parts.append(clip)
            scene_len += shot.duration
            scene_audio = None  # narration overlaid once per scene

        # subtitle cue: use real narration length when available
        if scene.narration:
            end = scene_start + scene_len
            if scene_audio_dur := _probe_duration(narration.get(str(scene.number))) if narration.get(str(scene.number)) else 0:
                end = min(scene_start + scene_audio_dur, scene_start + scene_len)
            cues.append((scene_start, end, scene.narration))
        cursor += scene_len

    credit = make_credit_card(film.credits, render_dir / "credits.png")
    credit_silent = make_silent_audio(3.0, render_dir / "credits-silent.mp3")
    parts.append(_make_clip(credit, credit_silent, 3.0, clips_dir / "credits.mp4", kenburns=False))
    cursor += 3.0

    if transition != "none" and len(parts) > 1:
        from .transitions import apply_transitions

        movie = apply_transitions(parts, deliverable, transition=transition, duration=0.4)
    else:
        movie = _concat(parts, deliverable)

    if sfx and sfx_events:
        from .soundfx import mix_sfx

        mix_sfx(movie, sfx_events, render_dir / "sfx")

    # sound design + subtitles
    theme = project.root / "sound" / f"{film.slug}-theme.wav"
    if with_music and theme.exists():
        mix_music(project, movie, theme)
    if cues:
        write_srt(project, cues)

    # cinematic finish: genre grade + letterbox + grain + vignette
    if cinematic:
        from .finish import apply_film_look

        apply_film_look(movie, genre=film.genre)
    return movie
