"""AI quality review: analyze every shot (brightness, contrast, sharpness, saturation)
and give a director-style score + recommendation. Fully offline (PIL + ffmpeg).

Score guide:
  9-10  HERO shot — master shot
  7-8   Solid — usable
  5-6   Acceptable but weak — consider regenerate
  <5    Bad — regenerate recommended
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageFilter, ImageStat

from .project import Project
from .render import _ffmpeg


# ---------------------------------------------------------------------------
# Frame extraction (video assets) & metric computation
# ---------------------------------------------------------------------------
def _grab_frame(asset: Path) -> Image.Image:
    if asset.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".bmp"}:
        return Image.open(asset).convert("RGB")
    # video → frame at ~1s
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as fh:
        tmp = Path(fh.name)
    subprocess.run(
        [_ffmpeg(), "-y", "-ss", "1.0", "-i", str(asset), "-frames:v", "1", str(tmp)],
        capture_output=True,
    )
    if not tmp.exists():
        raise RuntimeError(f"could not extract frame from {asset.name}")
    img = Image.open(tmp).convert("RGB")
    tmp.unlink(missing_ok=True)
    return img


def _laplacian_variance(img: Image.Image) -> float:
    gray = img.convert("L")
    laplacian = gray.filter(ImageFilter.Kernel((3, 3), [0, 1, 0, 1, -4, 1, 0, 1, 0], scale=1, offset=0))
    stat = ImageStat.Stat(laplacian)
    return stat.stddev[0]


def analyze_image(img: Image.Image) -> dict:
    rgb = img.convert("RGB")
    gray = rgb.convert("L")
    small = rgb.resize((256, 144))
    hsv = small.convert("HSV")

    g = ImageStat.Stat(gray)
    s = ImageStat.Stat(hsv)
    # colorfulness estimate (Hasler–Süsstrunk style, simple)
    rg = ImageStat.Stat(rgb).mean
    contrast = g.stddev[0]

    metrics = {
        "brightness": g.mean[0],
        "contrast": contrast,
        "saturation": s.mean[1],
        "sharpness": _laplacian_variance(rgb),
        "red_bias": rg[0] - rg[2],  # warm (+) vs cool (-)
        "width": img.width,
        "height": img.height,
    }
    return metrics, _score(metrics)


def _score(m: dict) -> tuple[float, list[str], str]:
    score = 7.0
    flags: list[str] = []

    if m["brightness"] < 22:
        score -= 1.6
        flags.append("TOO DARK")
    elif m["brightness"] > 228:
        score -= 1.2
        flags.append("BLOWN OUT")
    if m["contrast"] < 24:
        score -= 1.0
        flags.append("LOW CONTRAST / FLAT")
    if m["sharpness"] < 8:
        score -= 2.2
        flags.append("BLURRY / SOFT")
    if m["saturation"] < 22:
        score -= 0.6
        flags.append("DESATURATED")
    elif m["saturation"] > 180:
        score -= 0.8
        flags.append("OVERSATURATED")
    if abs(m["red_bias"]) > 80:
        flags.append("COLOR CAST")

    score = max(1.0, min(10.0, score))
    if score >= 8.5:
        note = "HERO shot — keep it"
    elif score >= 6.5:
        note = "Solid — usable"
    elif score >= 5:
        note = "Weak — consider regenerate"
    else:
        note = "BAD — regenerate recommended"
    return round(score, 1), flags, note


def _analyze_asset(asset: Path) -> dict:
    try:
        metrics, (score, flags, note) = analyze_image(_grab_frame(asset))
        return {"asset": str(asset), "score": score, "flags": flags, "note": note, "metrics": {k: round(v, 1) for k, v in metrics.items()}}
    except Exception as exc:
        return {"asset": str(asset), "score": None, "flags": ["ERROR"], "note": str(exc)[:80], "metrics": {}}


# ---------------------------------------------------------------------------
# Project-level review
# ---------------------------------------------------------------------------
def review_project(project: Project, threshold: float = 6.0) -> dict:
    """Analyze all generated shot assets; write render/review.json; return report."""
    results = []
    for shot in project.shots:
        if shot.local_asset and Path(shot.local_asset).exists():
            r = _analyze_asset(Path(shot.local_asset))
            r["shot"] = shot.index + 1
            r["prompt"] = shot.prompt[:60]
            results.append(r)

    scored = [r for r in results if r.get("score") is not None]
    avg = round(sum(r["score"] for r in scored) / len(scored), 1) if scored else 0
    weak = [r for r in scored if r["score"] < threshold]

    report = {
        "film": project.film.slug,
        "shots_analyzed": len(scored),
        "average_score": avg,
        "weak_shots": [r["shot"] for r in weak],
        "recommendations": [
            f"Shot #{r['shot']} ({r['score']}/10): {r['note']} — {'; '.join(r['flags'])}"
            for r in weak
        ],
        "details": results,
    }
    out = project.root / "render" / "review.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    return report


def load_review(project: Project) -> dict | None:
    p = project.root / "render" / "review.json"
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            return None
    return None
