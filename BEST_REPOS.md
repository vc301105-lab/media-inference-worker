# World's Best Repositories — Media AI Stack

Curated list of the best GitHub repositories for the media AI tools in this pipeline:
**Higgsfield · Runway · Midjourney · Sora · Kling · ElevenLabs**.

Star counts as of 2026-08-31. ✅ = official repo, 🥇 = my top pick per tool.

> **Note:** Midjourney, Sora, Kling and Runway's Gen models are closed-source services.
> They have **no official open-source model repos** — so for those I list the official
> API/SDK/MCP repos, the best unofficial clients, and the best open-source alternatives.

---

## 🎬 Higgsfield

| Stars | Repo | What it is |
|------:|------|-----------|
| 4,121 | [higgsfield-ai/higgsfield](https://github.com/higgsfield-ai/higgsfield) | ✅ Official — GPU orchestration + ML training framework (the company's core engine) |
| 822 | [higgsfield-ai/skills](https://github.com/higgsfield-ai/skills) | ✅ Official — AI agent skills for Higgsfield video generation |
| 477 | [higgsfield-ai/cli](https://github.com/higgsfield-ai/cli) | ✅ Official — Higgsfield CLI |
| 73 | [higgsfield-ai/higgsfield-client](https://github.com/higgsfield-ai/higgsfield-client) | ✅ Official — Python SDK for the Higgsfield API |
| 33 | [higgsfield-ai/higgsfield-js](https://github.com/higgsfield-ai/higgsfield-js) | ✅ Official — Node.js / TypeScript SDK |
| 1,405 | [SegFault42/HeliosGen](https://github.com/SegFault42/HeliosGen) | 🥇 Self-hosted alternative to Higgsfield / OpenArt / Freepik |
| 1,091 | [wide-trace/open-higgsfield](https://github.com/wide-trace/open-higgsfield) | Open studio: one prompt bar, many models, gallery of finished runs |
| 795 | [beshuaxian/higgsfield-seedance2-jineng](https://github.com/beshuaxian/higgsfield-seedance2-jineng) | 15 Claude skills for cinematic Higgsfield prompts (Seedance 2.0) |

**Top pick:** `higgsfield-ai/higgsfield-client` (Python SDK) for API work, `higgsfield-ai/skills` for agent-driven generation.

---

## 🎥 Runway

| Stars | Repo | What it is |
|------:|------|-----------|
| 22 | [runwayml/runway-api-mcp-server](https://github.com/runwayml/runway-api-mcp-server) | ✅ Official — MCP server for the Runway API (Gen video) |
| 1 | [runwayml/openapi](https://github.com/runwayml/openapi) | ✅ Official — Runway API OpenAPI spec |
| 242 | [runwayml/guided-inpainting](https://github.com/runwayml/guided-inpainting) | ✅ Official research — unified keyframe propagation models |
| 196 | [runwayml/RunwayML-for-Unity](https://github.com/runwayml/RunwayML-for-Unity) | ✅ Official — RunwayML for Unity |
| 139 | [runwayml/learn](https://github.com/runwayml/learn) | ✅ Official — tutorials, guides, examples |
| 165 | [vericontext/vibeframe](https://github.com/vericontext/vibeframe) | 🥇 Runway + Seedance + Veo + Kling in one CLI/MCP, your own keys, cost caps |
| 25 | [fabriciocarraro/runway-shopify-pipeline](https://github.com/fabriciocarraro/runway-shopify-pipeline) | Shopify catalog → product videos with Runway API (gen4.5 i2v) |
| 2 | [tryAGI/Runway](https://github.com/tryAGI/Runway) | C# / .NET SDK for Runway API |
| 2 | [AbdelStark/runway-rs](https://github.com/AbdelStark/runway-rs) | Unofficial Rust SDK |

**Top pick:** `runwayml/runway-api-mcp-server` (official, direct API access) + `runwayml/openapi` for the spec.

---

## 🖼️ Midjourney

| Stars | Repo | What it is |
|------:|------|-----------|
| 12,289 | [willwulfken/MidJourney-Styles-and-Keywords-Reference](https://github.com/willwulfken/MidJourney-Styles-and-Keywords-Reference) | 🥇 The legendary styles/keywords/reference bible for MJ prompts |
| 6,786 | [Dooy/chatgpt-web-midjourney-proxy](https://github.com/Dooy/chatgpt-web-midjourney-proxy) | One UI for MJ + Suno + Runway + Pika + Flux + Ideogram + more (Web/PWA/desktop) |
| 5,346 | [novicezk/midjourney-proxy](https://github.com/novicezk/midjourney-proxy) | Discord → API proxy for Midjourney (most popular) |
| 1,872 | [zcpua/midjourney-api](https://github.com/zcpua/midjourney-api) | Unofficial Node.js client |
| 811 | [trueai-org/midjourney-proxy](https://github.com/trueai-org/midjourney-proxy) | High-volume MJ drawing API proxy (1M+ daily generations) |
| 419 | [George-iam/Midjourney_api](https://github.com/George-iam/Midjourney_api) | Unofficial Midjourney API |
| 87 | [ezioruan/midjourney-python-api](https://github.com/ezioruan/midjourney-python-api) | Python client for the unofficial MJ API |
| 4,534 | [luban-agi/Awesome-AIGC-Tutorials](https://github.com/luban-agi/Awesome-AIGC-Tutorials) | Curated AIGC / AI-painting tutorials |

**Top pick:** `willwulfken/MidJourney-Styles-and-Keywords-Reference` for prompts; `novicezk/midjourney-proxy` to call MJ from code.

---

## 🌀 Sora (OpenAI)

| Stars | Repo | What it is |
|------:|------|-----------|
| 260 | [Curated-Awesome-Lists/Awesome-Open-AI-Sora](https://github.com/Curated-Awesome-Lists/Awesome-Open-AI-Sora) | 🥇 Curated hub: articles, videos, prompts, news about Sora |
| 208 | [Doriandarko/sora-mcp](https://github.com/Doriandarko/sora-mcp) | MCP server to use Sora video generation APIs |
| 1,153 | [all-in-aigc/sorafm](https://github.com/all-in-aigc/sorafm) | Sora FM — video generator UI |
| 99 | [xjpp22/awesome--sora-prompts](https://github.com/xjpp22/awesome--sora-prompts) | Visual-style + editing-style prompt reference |
| 37 | [SoraWeb/sora-next-web](https://github.com/SoraWeb/sora-next-web) | Next.js Sora video generator web app |
| 8 | [hitchhiker11/sora2-free-api](https://github.com/hitchhiker11/sora2-free-api) | Free Sora API via browser automation |

**Open-source alternatives to Sora (self-host):**

| Stars | Repo | What it is |
|------:|------|-----------|
| 29,325 | [hpcaitech/Open-Sora](https://github.com/hpcaitech/Open-Sora) | 🥇 The leading open Sora-style text-to-video model |
| 16,917 | [Wan-Video/Wan2.1](https://github.com/Wan-Video/Wan2.1) | Alibaba Wan — large-scale open video generation |
| 10,919 | [Lightricks/LTX-Video](https://github.com/Lightricks/LTX-Video) | Fast real-time text/image-to-video |
| 12,986 | [THUDM/CogVideo](https://github.com/THUDM/CogVideo) | CogVideoX text/image-to-video |

---

## 🎞️ Kling (Kuaishou)

| Stars | Repo | What it is |
|------:|------|-----------|
| 40 | [199-mcp/mcp-kling](https://github.com/199-mcp/mcp-kling) | 🥇 First MCP server for Kling AI video generation |
| 27 | [maciejdzierzek/kling-ai-prompt-generator](https://github.com/maciejdzierzek/kling-ai-prompt-generator) | Claude plugin — Kling prompt generator (i2v, t2v, motion control) |
| 13 | [M0r41/Kling-AI-Webui](https://github.com/M0r41/Kling-AI-Webui) | Kling WebUI |
| 157 | [chenwr727/KLing-Video-WatermarkRemover-Enhancer](https://github.com/chenwr727/KLing-Video-WatermarkRemover-Enhancer) | Enhance/clean Kling output (watermark removal, upscaling) |
| 2 | [WaveSpeedAI/awesome-kling-api](https://github.com/WaveSpeedAI/awesome-kling-api) | Kling v3.0/o3 API quick-start, model variants & prompts |
| 3 | [ddokkang2/openmontage-mcp-providers](https://github.com/ddokkang2/openmontage-mcp-providers) | Official Kling MCP provider bridge for OpenMontage |

---

## 🔊 ElevenLabs

| Stars | Repo | What it is |
|------:|------|-----------|
| 3,082 | [elevenlabs/elevenlabs-python](https://github.com/elevenlabs/elevenlabs-python) | ✅ Official Python SDK |
| 1,534 | [elevenlabs/elevenlabs-mcp](https://github.com/elevenlabs/elevenlabs-mcp) | ✅ Official MCP server (voice, TTS, dubbing) |
| 440 | [elevenlabs/elevenlabs-js](https://github.com/elevenlabs/elevenlabs-js) | ✅ Official Node.js SDK |
| 427 | [elevenlabs/skills](https://github.com/elevenlabs/skills) | ✅ Official agent skills |
| 112 | [elevenlabs/packages](https://github.com/elevenlabs/packages) | ✅ Official Agents SDK (TypeScript) |
| 2,367 | [elevenlabs/ui](https://github.com/elevenlabs/ui) | ✅ UI component library (shadcn/ui based) |
| 81 | [elevenlabs/cli](https://github.com/elevenlabs/cli) | ✅ Official CLI |

**Open-source alternatives (self-host / free):**

| Stars | Repo | What it is |
|------:|------|-----------|
| 12,188 | [debpalash/VoiceStudio](https://github.com/debpalash/VoiceStudio) | 🥇 Fully-local ElevenLabs alternative — voice cloning, dubbing, dictation, audiobooks |
| 32,476 | [fishaudio/fish-speech](https://github.com/fishaudio/fish-speech) | SOTA open-source TTS (voice cloning) |
| 8,628 | [hexgrad/kokoro](https://github.com/hexgrad/kokoro) | Kokoro-82M — tiny, excellent open TTS |
| 45,972 | [coqui-ai/TTS](https://github.com/coqui-ai/TTS) | The classic battle-tested TTS toolkit (XTTS) |
| 6,527 | [souzatharsis/podcastfy](https://github.com/souzatharsis/podcastfy) | NotebookLM-style podcast generation from any content |

---

## 🧰 Everything-in-one (covers most of the above)

| Stars | Repo | What it is |
|------:|------|-----------|
| 54,715 | [calesthio/OpenMontage](https://github.com/calesthio/OpenMontage) | 🥇 World's first open-source **agentic video production system** — 12 pipelines, 100+ tools, 700+ skills; integrates Kling, ElevenLabs, etc. |
| 4,194 | [SamurAIGPT/Generative-Media-Skills](https://github.com/SamurAIGPT/Generative-Media-Skills) | High-quality image/video/audio generation skills for AI agents |
| 6,786 | [Dooy/chatgpt-web-midjourney-proxy](https://github.com/Dooy/chatgpt-web-midjourney-proxy) | One UI: Midjourney + Suno + Runway + Flux + Ideogram + Pika |
| 164,746 | [AUTOMATIC1111/stable-diffusion-webui](https://github.com/AUTOMATIC1111/stable-diffusion-webui) | The most popular local image-gen web UI |
| 25,932 | [black-forest-labs/flux](https://github.com/black-forest-labs/flux) | Official FLUX.1 inference repo (state-of-the-art open images) |
| 27,279 | [stability-ai/generative-models](https://github.com/stability-ai/generative-models) | Stability AI open models (image/video) |

---

## Quick-start commands

```bash
# Clone the top pick for each tool
git clone https://github.com/higgsfield-ai/higgsfield-client.git
git clone https://github.com/runwayml/runway-api-mcp-server.git
git clone https://github.com/novicezk/midjourney-proxy.git
git clone https://github.com/Doriandarko/sora-mcp.git
git clone https://github.com/199-mcp/mcp-kling.git
git clone https://github.com/elevenlabs/elevenlabs-python.git
git clone https://github.com/calesthio/OpenMontage.git   # everything-in-one
```
