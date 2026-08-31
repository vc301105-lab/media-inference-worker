# 🎬 AI Film Studio

Ek **complete AI film production studio** — script se lekar final rendered movie tak,
sab kuch ek hi command se. Higgsfield platform (Kling, Veo, LTX, MiniMax, Qwen, GPT-Image)
ka use karta hai, aur voiceover ke liye ElevenLabs / edge-tts.

## ✨ Pipeline (4 steps)

```text
1. SCRIPT      → film_studio new "Film Title" --genre scifi
2. SHOTS       → film_studio build --model kling-3.0     (AI images/videos)
3. VOICE       → film_studio voice                        (narration)
4. RENDER      → film_studio render                       (final .mp4)
```

Ya sab ek saath → `film_studio all "Title" --genre drama`

## 🚀 Quick Start

```bash
# 1. Setup (ek baar)
./setup_studio.sh

# 2. Web UI shuru karo (browser dashboard) 🖥
./start_studio.sh
# → open http://localhost:8080

# 3. Ya CLI se — provider status + film banao
.venv/bin/python -m film_studio status
.venv/bin/python -m film_studio all "Chandni Ki Aakhri Raat" --genre drama --scenes 3 --shots 2
```

## 🖥 Web UI (Browser Dashboard)

`./start_studio.sh` kholne ke baad browser mein:

| Screen | Kya kar sakte ho |
|--------|------------------|
| **Home** | Naya film plan karo (title, genre, scenes, shots) + saari films ki list |
| **Film page** | 🎥 Generate Assets · 🗣 Voiceover · 🎵 Soundtrack · 🎞 Render · 🖼 Poster/Subtitles · 📱 9:16/1:1 Export — sab buttons se |
| **Player** | Rendered movie turant play karo + downloads |
| **Storyboard** | Saari scenes, prompts, camera moves |
| **/status** | Provider keys ki live status |

Sab actions background mein chalte hain aur log live update hota hai — page refresh ki zaroorat nahi.

## 📚 Commands

| Command | Kaam |
|---------|------|
| `new "Title" --genre X` | Naya project plan karo (script + storyboard) |
| `plan` | Pura storyboard dekho |
| `build --model M` | AI se shots generate karo (images/videos) |
| `voice` | Narration generate karo (voiceover) |
| `render` | Final movie render karo (music + subtitles + cinematic look ke saath) |
| `finish --grain 6` | Movie par 2.35:1 letterbox + grain + vignette apply karo |
| `trailer` | Fast-cut teaser trailer banao (COMING SOON + music) |
| `shot 3 --model kling-3.0` | Sirf ek shot regenerate karo |
| `rename "Naya Title"` | Film ka naam badlo |
| `delete --yes` | Film project delete karo |
| `publish --privacy public` | YouTube par upload karo |
| `sound` | Genre soundtrack generate karo + movie mein mix karo |
| `postpro --ratios 9:16 1:1` | Poster + subtitles + platform exports |
| `export --ratio 9:16` | Vertical / square export (Reels, Shorts) |
| `all` | Poora pipeline ek saath |
| `status` | Provider/api keys status |

### Models (Higgsfield platform)

| Model | Type | Endpoint |
|-------|------|----------|
| `kling-3.0` | video | Kling AI (Kuaishou) |
| `veo-3.1-fast` | video | Google Veo 3.1 |
| `ltx-2.5-pro` | video | Lightricks LTX |
| `minimax-h3` | video | MiniMax |
| `qwen-image-3` | image | Alibaba Qwen |
| `nano-banana-2` | image | Google |
| `gpt-image-2` | image | OpenAI |

### Genres

`scifi` · `action` · `romance` · `horror` · `documentary` · `commercial` · `drama`

## 📁 Project Structure

```text
films/<film-slug>/
├── film.json              # metadata (prompts, durations, assets)
├── script/screenplay.txt  # readable screenplay
├── assets/images/         # AI generated images
├── assets/videos/         # AI generated videos
├── voice/                 # narration mp3s
├── render/clips/          # rendered clips
└── movie/<film>.mp4       # ✅ FINAL MOVIE
```

## 🔊 Voiceover

- `ELEVENLABS_API_KEY` set hai → ElevenLabs use hota hai
- Nahi hai → free edge-tts (Microsoft neural voices, en-IN available)
- Network blocked → **silent track** fallback (film phir bhi render hoti hai)

Keys `.env` mein add karo:
```bash
ELEVENLABS_API_KEY=your_key_here
RUNWAY_API_KEY=your_key_here    # (plugin optional)
```

## 🤖 MCP Server — AI Agent se film banao

Studio ab **MCP server** hai (same style jaise Runway/Sora/Kling/ElevenLabs official MCPs).
Koi bhi AI agent (Claude Desktop, Cursor, OpenCode…) seedha film bana sakta hai:

```bash
.venv/bin/python -m film_studio.mcp_server
```

**Tools (10):** `studio_status` · `list_films` · `plan_new_film` · `generate_assets` ·
`voiceover` · `soundtrack` · `render_final` · `postproduction` · `make_trailer_tool` · `direct_all_in_one`

**Claude Desktop config** (`~/.config/Claude/claude_desktop_config.json`):
```json
"mcpServers": {
  "ai-film-studio": {
    "command": "/home/user/media-inference-worker/.venv/bin/python",
    "args": ["-m", "film_studio.mcp_server"],
    "cwd": "/home/user/media-inference-worker"
  }
}
```

Uske baad Claude se bolo: *"Ek sci-fi short film banao 'Neon Rain' — 4 scenes, kling-3.0, Hindi narration, trailer ke saath"* — agent khud pipeline chalayega.

## 📤 YouTube Publish

Film direct YouTube par upload karo (CLI + Web button):

```bash
# 1. Google Cloud Console → OAuth Desktop app → client_secret.json download karo
#    Save as: youtube_client_secret.json (repo root mein)
# 2. Google API libraries install karo
.venv/bin/pip install google-api-python-client google-auth-oauthlib google-auth-httplib2

# 3. Publish
.venv/bin/python -m film_studio publish --project films/neon-rain --privacy public
```

Pehli baar browser mein consent dena padta hai — token `films/<slug>/youtube_token.json` mein cache
hota hai, phir silent upload. Web UI mein bhi **📤 Publish to YouTube** button hai.

## 🧩 Plugins (optional)

- `film_studio/plugins/runway.py` — Runway API plugin (RUNWAY_API_KEY)

## 🖥️ Full Production Example

```bash
# 2-minute cinematic sci-fi film — 5 scenes, 3 shots each, Kling videos
.venv/bin/python -m film_studio all "Neon Rain" \
  --genre scifi --scenes 5 --shots 3 --model kling-3.0 --duration 5 \
  --voice auto --lang en-IN --poster --ratios 9:16 1:1
```

## 🎥 Demo

Demo film: [`films/chandni-ki-aakhri-raat/movie/`](films/chandni-ki-aakhri-raat/movie/)
(cinematic mock — real AI assets generate karne ke liye `build` command chalao)

> ⚠️ **Note:** AI generation APIs ko network chahiye. Render (offline) hamesha
> kaam karta hai — Pillow + ffmpeg ke saath.
