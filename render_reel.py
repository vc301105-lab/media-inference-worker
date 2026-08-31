#!/usr/bin/env python3
import os
import math
import subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

WIDTH = 1080
HEIGHT = 1920
FPS = 30
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

def create_text_card(text, highlight_words=None, font_size=46, max_width=920):
    font = ImageFont.truetype(FONT_PATH, font_size)
    words = text.split()
    lines = []
    current_line = []
    
    # Simple word wrap
    dummy_img = Image.new('RGBA', (10, 10))
    dummy_draw = ImageDraw.Draw(dummy_img)
    
    for word in words:
        test_line = " ".join(current_line + [word])
        bbox = dummy_draw.textbbox((0, 0), test_line, font=font)
        w = bbox[2] - bbox[0]
        if w > max_width and current_line:
            lines.append(" ".join(current_line))
            current_line = [word]
        else:
            current_line.append(word)
    if current_line:
        lines.append(" ".join(current_line))
        
    line_height = int(font_size * 1.35)
    card_w = max_width + 80
    card_h = len(lines) * line_height + 60
    
    # Render pill overlay
    card = Image.new('RGBA', (card_w, card_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(card)
    
    # Rounded dark translucent box with glowing border
    pill_shape = [(10, 10), (card_w - 10, card_h - 10)]
    draw.rounded_rectangle(pill_shape, radius=32, fill=(15, 23, 42, 210), outline=(56, 189, 248, 200), width=3)
    
    y_offset = 28
    for line in lines:
        l_bbox = draw.textbbox((0, 0), line, font=font)
        lw = l_bbox[2] - l_bbox[0]
        x_offset = (card_w - lw) // 2
        
        # Draw shadow
        draw.text((x_offset + 2, y_offset + 2), line, font=font, fill=(0, 0, 0, 180))
        # Draw text with bright white & cyan tint
        draw.text((x_offset, y_offset), line, font=font, fill=(255, 255, 255, 255))
        y_offset += line_height
        
    return card

def render_scene(image_path, audio_path, subtitles, output_video_path, zoom_mode="in"):
    # Load base image
    img = Image.open(image_path).convert('RGB')
    orig_w, orig_h = img.size
    
    # Calculate audio duration
    cmd = ['ffmpeg', '-i', audio_path]
    res = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    import re
    match = re.search(r'Duration:\s*(\d+):(\d+):(\d+\.\d+)', res.stderr)
    if match:
        h, m, s = match.groups()
        duration = int(h)*3600 + int(m)*60 + float(s)
    else:
        duration = 5.0
        
    total_frames = int(duration * FPS)
    
    # Start ffmpeg pipe for video writing
    ffmpeg_cmd = [
        'ffmpeg', '-y',
        '-f', 'rawvideo',
        '-vcodec', 'rawvideo',
        '-s', f'{WIDTH}x{HEIGHT}',
        '-pix_fmt', 'rgb24',
        '-r', str(FPS),
        '-i', '-',
        '-i', audio_path,
        '-c:v', 'libx264',
        '-preset', 'fast',
        '-crf', '18',
        '-c:a', 'aac',
        '-b:a', '192k',
        '-pix_fmt', 'yuv420p',
        '-shortest',
        output_video_path
    ]
    
    proc = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE)
    
    # Pre-render subtitle cards
    pre_subtitles = []
    for (start_t, end_t, text) in subtitles:
        card = create_text_card(text)
        pre_subtitles.append((start_t, end_t, card))
    
    for f in range(total_frames):
        t = f / FPS
        progress = t / duration if duration > 0 else 0
        
        # Dynamic camera motion (Ken Burns effect)
        if zoom_mode == "in":
            scale = 1.0 + 0.12 * progress
            cx = orig_w / 2
            cy = orig_h / 2
        elif zoom_mode == "out":
            scale = 1.15 - 0.12 * progress
            cx = orig_w / 2
            cy = orig_h / 2
        else: # pan
            scale = 1.08
            cx = orig_w / 2 + math.sin(progress * math.pi) * (orig_w * 0.04)
            cy = orig_h * (0.45 + 0.1 * progress)
            
        crop_w = orig_w / scale
        crop_h = orig_h / scale
        x1 = max(0, min(orig_w - crop_w, cx - crop_w / 2))
        y1 = max(0, min(orig_h - crop_h, cy - crop_h / 2))
        x2 = x1 + crop_w
        y2 = y1 + crop_h
        
        frame_img = img.crop((x1, y1, x2, y2)).resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
        
        # Check active subtitle
        active_card = None
        for (start_t, end_t, card) in pre_subtitles:
            if start_t <= t < end_t:
                active_card = card
                break
                
        if active_card:
            # Alpha composite card at bottom (y = 1380)
            card_x = (WIDTH - active_card.width) // 2
            card_y = 1420
            frame_rgba = frame_img.convert('RGBA')
            frame_rgba.paste(active_card, (card_x, card_y), active_card)
            frame_img = frame_rgba.convert('RGB')
            
        # Draw header badge "AI GENERATED REEL"
        draw = ImageDraw.Draw(frame_img)
        header_font = ImageFont.truetype(FONT_PATH, 28)
        tag_text = "⚡ AI CREATIVE STUDIO"
        t_bbox = draw.textbbox((0, 0), tag_text, font=header_font)
        tw = t_bbox[2] - t_bbox[0]
        tx = (WIDTH - tw) // 2
        # Header capsule
        draw.rounded_rectangle([(tx - 20, 100), (tx + tw + 20, 150)], radius=25, fill=(0, 0, 0, 180), outline=(234, 179, 8, 220), width=2)
        draw.text((tx, 110), tag_text, font=header_font, fill=(253, 224, 71))
        
        # Draw dynamic progress bar at the very bottom
        bar_y = HEIGHT - 20
        draw.rectangle([(0, bar_y), (WIDTH, bar_y + 10)], fill=(30, 41, 59))
        draw.rectangle([(0, bar_y), (int(WIDTH * progress), bar_y + 10)], fill=(56, 189, 248))
        
        proc.stdin.write(frame_img.tobytes())
        
    proc.stdin.close()
    proc.wait()
    print(f"Scene rendered: {output_video_path}")

def main():
    scenes = [
        {
            "img": "/home/user/media-inference-worker/scene1.png",
            "audio": "/home/user/media-inference-worker/voice1.mp3",
            "subtitles": [
                (0.0, 2.3, "AI ne content creation ki duniya ko"),
                (2.3, 4.9, "Hamesha ke liye badal diya hai! 🚀")
            ],
            "zoom": "in",
            "out": "/home/user/media-inference-worker/clip1.mp4"
        },
        {
            "img": "/home/user/media-inference-worker/scene2.png",
            "audio": "/home/user/media-inference-worker/voice2.mp3",
            "subtitles": [
                (0.0, 3.2, "Ab aap sirf ek simple prompt se..."),
                (3.2, 6.5, "Cinematic visuals & viral reels create kar sakte hain! ✨")
            ],
            "zoom": "out",
            "out": "/home/user/media-inference-worker/clip2.mp4"
        },
        {
            "img": "/home/user/media-inference-worker/scene3.png",
            "audio": "/home/user/media-inference-worker/voice3.mp3",
            "subtitles": [
                (0.0, 2.2, "Aapka agla creative idea kya hai?"),
                (2.2, 4.6, "Apni imagination ko video me badaliye! 🔥")
            ],
            "zoom": "pan",
            "out": "/home/user/media-inference-worker/clip3.mp4"
        }
    ]
    
    for s in scenes:
        render_scene(s["img"], s["audio"], s["subtitles"], s["out"], s["zoom"])
        
    # Concatenate clips with background music
    concat_list = "/home/user/media-inference-worker/clips.txt"
    with open(concat_list, "w") as f:
        for s in scenes:
            f.write(f"file '{s['out']}'\n")
            
    # Step 1: Concatenate scenes
    merged_video = "/home/user/media-inference-worker/merged_raw.mp4"
    cmd_concat = [
        'ffmpeg', '-y',
        '-f', 'concat',
        '-safe', '0',
        '-i', concat_list,
        '-c', 'copy',
        merged_video
    ]
    subprocess.run(cmd_concat, check=True)
    
    # Step 2: Mix background music with voiceover
    final_video = "/home/user/media-inference-worker/ai_reel_sample.mp4"
    cmd_mix = [
        'ffmpeg', '-y',
        '-i', merged_video,
        '-i', '/home/user/media-inference-worker/bg_music.wav',
        '-filter_complex', '[1:a]volume=0.18[bg];[0:a][bg]amix=inputs=2:duration=first:dropout_transition=2[aout]',
        '-map', '0:v',
        '-map', '[aout]',
        '-c:v', 'copy',
        '-c:a', 'aac',
        '-b:a', '192k',
        final_video
    ]
    subprocess.run(cmd_mix, check=True)
    print(f"FINAL VIDEO READY: {final_video}")

if __name__ == "__main__":
    main()
