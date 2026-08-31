"""Music Engine 2.0 — real chord progressions (bass + pad + arpeggio) per genre.

Synthesized offline with numpy → WAV. Each genre has its own key, chord
progression, and tempo so every film's score feels like a real composition.
"""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

SR = 44100
A4 = 440.0

# note names for readability (octave 4 = A4)
_SEMI = {"C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4, "F": 5, "F#": 6, "Gb": 6,
         "G": 7, "G#": 8, "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11}


def _note(name: str) -> float:
    """'A3' -> frequency in Hz."""
    letter = name[:-1]
    octave = int(name[-1])
    midi = 12 * (octave + 1) + _SEMI[letter]
    return A4 * 2 ** ((midi - 69) / 12)


# per genre: (chord progression as [root, quality], tempo BPM, arp pattern 0-7)
# chord = root note like "A3" + quality m/M; pattern indexes chord tones [root,3rd,5th,oct]
SCORES = {
    "drama":       ([("A3", "m"), ("F3", "M"), ("C4", "M"), ("G3", "M")], 84,  [0, 1, 2, 1, 0, 2, 3, 2]),
    "scifi":       ([("D3", "m"), ("Bb3", "M"), ("F4", "M"), ("C4", "m")], 104, [0, 2, 1, 3, 0, 2, 1, 2]),
    "romance":     ([("C4", "M"), ("G3", "M"), ("A3", "m"), ("F3", "M")], 92,  [0, 1, 2, 3, 2, 1, 0, 1]),
    "horror":      ([("D3", "m"), ("D3", "m"), ("Bb3", "M"), ("A2", "m")], 66,  [0, 0, 1, 0, 0, 2, 0, 1]),
    "action":      ([("E3", "m"), ("C4", "M"), ("G3", "M"), ("D4", "M")], 126, [0, 2, 3, 2, 0, 1, 2, 3]),
    "commercial":  ([("C4", "M"), ("A3", "m"), ("F3", "M"), ("G3", "M")], 112, [0, 1, 2, 3, 3, 2, 1, 0]),
    "documentary": ([("G3", "M"), ("C4", "M"), ("D4", "m"), ("G3", "M")], 88,  [0, 2, 1, 0, 2, 3, 2, 1]),
}

_INTERVALS = {"m": [0, 3, 7, 12], "M": [0, 4, 7, 12]}


def _env(n: int, attack: float = 0.25, release: float = 0.6) -> np.ndarray:
    """Attack/release envelope (0..1)."""
    t = np.arange(n) / SR
    a = np.minimum(t / max(attack, 0.01), 1.0)
    r = np.minimum((n / SR - t) / max(release, 0.05), 1.0)
    return np.clip(a * r, 0, 1)


def _chord_pad(freqs: list[float], dur: float, detune: float = 1.5) -> np.ndarray:
    n = int(dur * SR)
    t = np.arange(n) / SR
    env = _env(n, attack=0.5, release=0.8)
    left = np.zeros(n)
    right = np.zeros(n)
    for f in freqs:
        for harm, amp in ((1, 0.55), (2, 0.18), (0.5, 0.35)):  # half-harmonic = warm
            det = 1 + detune / 100 * (harm - 1) * 0.3
            left += amp * np.sin(2 * np.pi * f * harm / det * t) * 0.22
            right += amp * np.sin(2 * np.pi * f * harm * det * t) * 0.22
    return left.astype(np.float32) * env, right.astype(np.float32) * env


def _bass(freq: float, dur: float) -> np.ndarray:
    n = int(dur * SR)
    t = np.arange(n) / SR
    env = _env(n, attack=0.12, release=0.5).astype(np.float32)
    sig = (np.sin(2 * np.pi * freq * t) + 0.35 * np.sin(2 * np.pi * freq * 2 * t)) * 0.30
    return sig * env


def _arp(freqs: list[float], pattern: list[int], bpm: int, dur: float, seed: float = 0.0) -> np.ndarray:
    step = 60.0 / bpm / 2  # eighth notes
    n_steps = max(1, int(dur / step))
    n = int(dur * SR)
    sig = np.zeros(n, dtype=np.float32)
    for i in range(n_steps):
        idx = pattern[i % len(pattern)]
        f = freqs[min(idx, len(freqs) - 1)]
        start = int(i * step * SR)
        length = int(step * SR * 0.85)
        if start + length > n:
            length = n - start
        if length <= 0:
            break
        t = np.arange(length) / SR
        pluck = np.exp(-t * 6.5) * np.sin(2 * np.pi * f * t + seed)
        sig[start:start + length] += (pluck * 0.16).astype(np.float32)
    return sig


def generate_theme(project, duration: float | None = None, filename: str | None = None) -> Path:
    """Compose a genre score for the film → sound/<slug>-theme.wav (or filename)."""
    film = project.film
    dur = float(duration if duration else film.duration + 2)
    progression, bpm, pattern = SCORES.get(film.genre, SCORES["drama"])

    out_dir = project.root / "sound"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / (filename or f"{film.slug}-theme.wav")

    chord_dur = 2.0  # seconds per chord; loop to cover duration
    seq: list[np.ndarray] = []
    i = 0
    while (len(seq) + 1) * chord_dur < dur + chord_dur:
        root_name, quality = progression[i % len(progression)]
        root = _note(root_name)
        tones = [root * 2 ** (s / 12) for s in _INTERVALS[quality]]
        l, r = _chord_pad(tones, chord_dur)
        b = _bass(root / 2, chord_dur)
        a = _arp(tones + [tones[0] * 2], pattern, bpm, chord_dur, seed=i * 0.7)
        seq.append((l + b + a).astype(np.float32))
        seq.append((r + b + a).astype(np.float32))
        i += 1

    total = int(dur * SR)
    left = np.zeros(total, dtype=np.float32)
    right = np.zeros(total, dtype=np.float32)
    pos = 0
    for j in range(0, len(seq), 2):
        if pos >= total:
            break
        chunk = min(total - pos, len(seq[j]))
        left[pos:pos + chunk] += seq[j][:chunk]
        right[pos:pos + chunk] += seq[j + 1][:chunk]
        pos += chunk

    # gentle room noise + master fades
    t = np.arange(total) / SR
    noise = np.random.default_rng(7).normal(0, 0.012, total).astype(np.float32)
    left += noise
    right += noise
    fade_in = np.minimum(t / 1.2, 1.0)
    fade_out = np.minimum((dur - t) / 1.6, 1.0)
    master = (fade_in * fade_out * 0.9).astype(np.float32)
    peak = max(np.abs(left).max(), np.abs(right).max(), 1e-6)
    left = left / peak * master * 0.75
    right = right / peak * master * 0.75

    pcm = np.stack([left, right], axis=1)
    pcm16 = (np.clip(pcm, -1, 1) * 32767).astype("<i2")
    with wave.open(str(out), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(pcm16.tobytes())
    return out
