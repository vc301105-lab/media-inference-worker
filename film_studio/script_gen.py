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

# Hindi narration templates (film_studio new ... --lang hi)
HINDI_BEATS = [
    "दुनिया: यह शहर, यह रात... ज़िंदगी बदलने वाली आख़िरी रात।",
    "मोड़: एक छोटा-सा फ़ैसला... और सब कुछ बदल जाता है।",
    "निष्कर्ष: सुबह होते ही... एक नई कहानी शुरू होती है।",
    "उपसंहार: कैमरा रुकता है उस आख़िरी तस्वीर पर... जो सब कुछ कहती है।",
]

DIALOGUE_POOL = {
    "scifi": [
        ('AARAV', "Kya tumne woh signal dekha? Iska matlab hai... woh aa rahe hain."),
        ('MEERA', "Agar yeh raat bach gayi, toh kal sab kuch alag hoga."),
    ],
    "action": [
        ('VIKRAM', "Ruk ja! Agent wale log aa rahe hain — mujh par bharosa kar."),
        ('ZARA', "Plan toh aisa tha ki koi nahi marega."),
    ],
    "romance": [
        ('KABIR', "Mujhe bas yeh ek baat karni thi... tumse."),
        ('TARA', "Woh ek baat kya hai, KABIR?"),
    ],
    "horror": [
        ('RAVI', "Sun raha hai na? ... Ya phir koi aur sun raha hai."),
        ('POOJA', "Humne woh darwaza band kiya tha. Band. Kiya. Tha."),
    ],
    "documentary": [
        ('NARRATOR', "Har subah yahan sab kuch pehle jaisa nahi hota."),
        ('GRANDMA', "Mere bachpan mein yeh gali kisi aur duniya jaisi lagti thi."),
    ],
    "commercial": [
        ('VOICEOVER', "Naya. Zyada tazaa. Zyada aapke liye."),
        ('HOST', "Dekho, order karte hi 30 minute mein aapke darwaze par."),
    ],
    "drama": [
        ('AARAV', "Main is sheher ko chhod raha hoon, MEERA."),
        ('MEERA', "Toh jaane se pehle... ek aakhri baar gaana sun le."),
    ],
}


def _seed_rng(film: Film) -> random.Random:
    digest = hashlib.sha256((film.title + film.logline + film.genre).encode()).hexdigest()
    return random.Random(int(digest[:12], 16))


def write_script(film: Film, scenes: int = 3, lang: str = "en") -> Film:
    """Fill film.scenes from logline using a 3-act template (lang: en|hi)."""
    rng = _seed_rng(film)
    spec = GENRES.get(film.genre, GENRES["drama"])
    logline = film.logline or "A young dreamer crosses the city on the last night before everything changes."

    # 3-act narrative + optional extra scenes
    if lang == "hi":
        beats = list(HINDI_BEATS)[: max(scenes, 3)][:scenes]
        dialogue = DIALOGUE_POOL.get(film.genre, DIALOGUE_POOL["drama"])
    else:
        acts = [
            ("THE WORLD", logline.rstrip(".") + "."),
            ("THE TURN", "A single choice changes everything, and the world begins to push back."),
            ("THE RESOLUTION", "At dawn, something has changed — and a new story is ready to begin."),
        ]
        beats = [
            f"{a}: {b}"
            for a, b in (acts + [("AFTERGLOW", "The camera holds on a final image that says everything without a word.")])[: scenes]
        ]
        dialogue = DIALOGUE_POOL.get(film.genre, DIALOGUE_POOL["drama"])

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
                dialogue=f"{dialogue[i % len(dialogue)][0]}: {dialogue[i % len(dialogue)][1]}",
            )
        )
    return film


def write_script_file(project, lang: str = "en") -> Path:
    """Write a readable screenplay .txt next to the JSON metadata."""
    lines = [project.film.title.upper(), f"A {project.film.genre} short film" + (" (हिन्दी)" if lang == "hi" else ""), "", "FADE IN:"]
    for scene in project.film.scenes:
        lines += ["", scene.heading.upper(), "", scene.action, ""]
        if scene.dialogue:
            who, what = scene.dialogue.split(": ", 1)
            lines += [f"{who}: {what}", ""]
            lines += ["(beat)", ""]
        if scene.narration:
            lines += ["", f"NARRATOR: {scene.narration}", ""]
    lines += ["FADE OUT.", "", "— THE END —", "", project.film.credits]
    path = project.root / "script" / "screenplay.txt"
    path.write_text("\n".join(lines))
    return path
