#!/usr/bin/env python3
import os
import re
import math
import mimetypes
import subprocess
import numpy as np
from flask import Flask, Response, request, jsonify, send_file, send_from_directory
from flask_cors import CORS

app = Flask(__name__, static_folder="static", template_folder="templates")
CORS(app)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
OUTPUTS_DIR = os.path.join(BASE_DIR, "outputs")
os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(OUTPUTS_DIR, exist_ok=True)

def send_file_partial(path):
    """
    Simple and robust range request handler for video streaming
    """
    range_header = request.headers.get('Range', None)
    if not range_header:
        return send_file(path, mimetype="video/mp4", conditional=True)
    
    size = os.path.getsize(path)
    byte1, byte2 = 0, None
    
    m = re.search(r'bytes=(\d+)-(\d*)', range_header)
    if m:
        g = m.groups()
        byte1 = int(g[0])
        if g[1]:
            byte2 = int(g[1])
            
    if byte2 is None:
        byte2 = size - 1
        
    length = byte2 - byte1 + 1
    
    with open(path, 'rb') as f:
        f.seek(byte1)
        data = f.read(length)
        
    resp = Response(
        data,
        206,
        mimetype="video/mp4",
        direct_passthrough=True
    )
    resp.headers.add('Content-Range', f'bytes {byte1}-{byte2}/{size}')
    resp.headers.add('Accept-Ranges', 'bytes')
    resp.headers.add('Content-Length', str(length))
    return resp

@app.route("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")

@app.route("/api/video-info")
def video_info():
    sample_path = os.path.join(BASE_DIR, "ai_reel_sample.mp4")
    exists = os.path.exists(sample_path)
    file_size = os.path.getsize(sample_path) if exists else 0
    
    return jsonify({
        "status": "ready" if exists else "generating",
        "title": "The Future of AI & Innovation (Hindi AI Reel)",
        "duration": 15.6,
        "resolution": "1080x1920 (9:16 Vertical Reel)",
        "file_size_mb": round(file_size / (1024 * 1024), 2),
        "video_url": "/video/ai_reel_sample.mp4",
        "video_720p_url": "/video/ai_reel_720p.mp4",
        "scenes": [
            {
                "id": 1,
                "title": "Scene 1: Future Cyber City",
                "image_url": "/images/scene1.png",
                "audio_url": "/audio/voice1.mp3",
                "script": "AI ne content creation ki duniya ko hamesha ke liye badal kar rakh diya hai.",
                "duration": "4.8s",
                "tags": ["Cyberpunk", "Tokyo 2142", "Neon Sunset", "Zoom-in Motion"]
            },
            {
                "id": 2,
                "title": "Scene 2: AI Android Hologram",
                "image_url": "/images/scene2.png",
                "audio_url": "/audio/voice2.mp3",
                "script": "Ab aap sirf ek prompt se cinematic visuals, lifelike voiceover aur viral reels create kar sakte hain.",
                "duration": "6.4s",
                "tags": ["Futuristic Android", "Holographic UI", "Glass Studio", "Zoom-out Motion"]
            },
            {
                "id": 3,
                "title": "Scene 3: Quantum Neural Network",
                "image_url": "/images/scene3.png",
                "audio_url": "/audio/voice3.mp3",
                "script": "Aapka agla creative idea kya hai? Apni imagination ko video me badaliye!",
                "duration": "4.5s",
                "tags": ["Neural Brain", "Golden Sparks", "Sci-Fi Climax", "Dynamic Pan Motion"]
            }
        ]
    })

@app.route("/video/<path:filename>")
def serve_video(filename):
    file_path = os.path.join(BASE_DIR, filename)
    if not os.path.exists(file_path):
        return jsonify({"error": "Video not found"}), 404
    return send_file_partial(file_path)

@app.route("/images/<path:filename>")
def serve_image(filename):
    return send_from_directory(BASE_DIR, filename)

@app.route("/audio/<path:filename>")
def serve_audio(filename):
    return send_from_directory(BASE_DIR, filename)

@app.route("/api/presets")
def get_presets():
    presets = [
        {
            "id": "ai_future",
            "title": "🚀 AI & Future Tech Reel",
            "description": "Futuristic neon cities, robotic avatars, glowing neural networks, high-energy tech vibe.",
            "language": "Hinglish / Hindi",
            "scenes": [
                "Cyberpunk futuristic neon city with flying cars at twilight",
                "Humanoid AI android interacting with glowing holographic displays",
                "Golden radiant neural network brain pulsing with cosmic energy"
            ]
        },
        {
            "id": "motivational",
            "title": "🔥 Morning Motivation & Success",
            "description": "Epic mountain peaks at sunrise, luxury penthouse, disciplined lifestyle aesthetic.",
            "language": "Hindi / Urdu",
            "scenes": [
                "Cinematic sunrise over misty golden mountain peaks with eagle soaring",
                "Silhouette of a determined thinker looking out modern glass skyscraper at dawn",
                "Powerful glowing golden compass with cosmic starlight in background"
            ]
        },
        {
            "id": "luxury_cars",
            "title": "🏎️ Luxury Supercars & Speed",
            "description": "Hypercars in rain, neon reflection, aerodynamic smoke, ultra-dramatic reels.",
            "language": "Hindi / English",
            "scenes": [
                "Matte black electric hypercar drifting through wet neon Tokyo streets",
                "Close-up of glowing futuristic digital speedometer reaching 300 km/h",
                "Sleek sports car parked in front of futuristic glass mansion at twilight"
            ]
        },
        {
            "id": "cosmic_mystery",
            "title": "🌌 Space & Cosmic Wonders",
            "description": "Black holes, vibrant nebulas, interstellar voyages, deep curiosity hook.",
            "language": "Hindi / English",
            "scenes": [
                "Vibrant colorful nebula glowing with purple, cyan and gold cosmic dust",
                "Massive glowing black hole bending spacetime with accretion disk",
                "Astronaut floating towards ancient alien planetary portal"
            ]
        }
    ]
    return jsonify(presets)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000, debug=False)
