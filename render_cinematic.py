#!/usr/bin/env python3
import os
import math
import subprocess
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont

WIDTH = 1920
HEIGHT = 1080
FPS = 30
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

def get_audio_duration(path):
    cmd = ['ffmpeg', '-i', path]
    res = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    import re
    match = re.search(r'Duration:\s*(\d+):(\d+):(\d+\.\d+)', res.stderr)
    if match:
        h, m, s = match.groups()
        return int(h)*3600 + int(m)*60 + float(s)
    return 4.0

def create_cinematic_subtitle(text, font_size=36):
    font = ImageFont.truetype(FONT_PATH, font_size)
    dummy_img = Image.new('RGBA', (10, 10))
    dummy_draw = ImageDraw.Draw(dummy_img)
    
    bbox = dummy_draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    
    card_w = tw + 80
    card_h = th + 36
    card = Image.new('RGBA', (card_w, card_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(card)
    
    # Subtle dark blur backplate
    draw.rounded_rectangle([(0, 0), (card_w, card_h)], radius=18, fill=(0, 0, 0, 160))
    draw.text((42, 18), text, font=font, fill=(0, 0, 0, 220))
    draw.text((40, 16), text, font=font, fill=(245, 245, 240, 255))
    return card

def render_cinematic_scene(img_path, audio_path, subtitles, output_path, motion_type="dolly_in"):
    base_img = cv2.imread(img_path)
    base_h, base_w, _ = base_img.shape
    
    duration = get_audio_duration(audio_path)
    total_frames = int(duration * FPS)
    
    # Rain particles
    num_particles = 220
    rain_x = np.random.uniform(0, WIDTH, num_particles)
    rain_y = np.random.uniform(0, HEIGHT, num_particles)
    rain_speed = np.random.uniform(22, 40, num_particles)
    rain_length = np.random.uniform(20, 45, num_particles)
    
    ffmpeg_cmd = [
        'ffmpeg', '-y',
        '-f', 'rawvideo',
        '-vcodec', 'rawvideo',
        '-s', f'{WIDTH}x{HEIGHT}',
        '-pix_fmt', 'bgr24',
        '-r', str(FPS),
        '-i', '-',
        '-i', audio_path,
        '-c:v', 'libx264',
        '-preset', 'fast',
        '-profile:v', 'main',
        '-level', '4.0',
        '-movflags', '+faststart',
        '-crf', '20',
        '-c:a', 'aac',
        '-ar', '44100',
        '-ac', '2',
        '-b:a', '192k',
        '-pix_fmt', 'yuv420p',
        output_path
    ]
    
    proc = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE)
    sub_cards = [(st, et, create_cinematic_subtitle(txt)) for (st, et, txt) in subtitles]
    
    for f in range(total_frames):
        t = f / FPS
        prog = t / duration if duration > 0 else 0
        
        # 1. Realistic Camera Movement (Handheld breathing + dolly)
        handheld_x = math.sin(t * 1.5) * 8 + math.sin(t * 3.2) * 3
        handheld_y = math.cos(t * 1.2) * 6 + math.sin(t * 2.8) * 2
        
        if motion_type == "dolly_in":
            scale = 1.0 + 0.12 * prog
            cx = base_w / 2 + handheld_x
            cy = base_h / 2 + handheld_y
        elif motion_type == "dolly_out":
            scale = 1.15 - 0.12 * prog
            cx = base_w / 2 + handheld_x
            cy = base_h / 2 + handheld_y
        elif motion_type == "pan_right":
            scale = 1.08
            cx = base_w * (0.44 + 0.12 * prog) + handheld_x
            cy = base_h / 2 + handheld_y
        else:
            scale = 1.05 + 0.08 * math.sin(prog * math.pi)
            cx = base_w * (0.5 + 0.06 * math.sin(prog * math.pi))
            cy = base_h / 2 + handheld_y
            
        crop_w = base_w / scale
        crop_h = base_h / scale
        x1 = int(max(0, min(base_w - crop_w, cx - crop_w / 2)))
        y1 = int(max(0, min(base_h - crop_h, cy - crop_h / 2)))
        x2 = int(x1 + crop_w)
        y2 = int(y1 + crop_h)
        
        cropped = base_img[y1:y2, x1:x2]
        frame = cv2.resize(cropped, (WIDTH, HEIGHT), interpolation=cv2.INTER_LANCZOS4)
        
        # 2. Dynamic Rain Streaks
        rain_layer = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)
        rain_y += rain_speed
        rain_x += rain_speed * 0.12
        rain_y = np.mod(rain_y, HEIGHT)
        rain_x = np.mod(rain_x, WIDTH)
        
        for p in range(num_particles):
            px1 = int(rain_x[p])
            py1 = int(rain_y[p])
            px2 = int(px1 + rain_length[p] * 0.12)
            py2 = int(py1 + rain_length[p])
            cv2.line(rain_layer, (px1, py1), (px2, py2), (180, 210, 245), 1)
            
        frame = cv2.addWeighted(frame, 1.0, rain_layer, 0.22, 0)
        
        # 3. Anamorphic lens flare glow
        flare_pulse = 0.5 + 0.5 * math.sin(t * 3.0)
        if flare_pulse > 0.72:
            flare_intensity = (flare_pulse - 0.72) / 0.28 * 0.14
            flare = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)
            cv2.line(flare, (0, HEIGHT//2), (WIDTH, HEIGHT//2), (255, 190, 90), 2)
            flare = cv2.GaussianBlur(flare, (101, 15), 0)
            frame = cv2.addWeighted(frame, 1.0, flare, flare_intensity, 0)
            
        # 4. 35mm Film Grain
        grain = np.random.normal(0, 4, (HEIGHT, WIDTH, 3)).astype(np.int16)
        frame_grain = np.clip(frame.astype(np.int16) + grain, 0, 255).astype(np.uint8)
        frame = frame_grain
        
        # 5. Cinematic 2.39:1 Letterbox
        bar_height = int(HEIGHT * 0.08)
        frame[0:bar_height, :] = 0
        frame[HEIGHT - bar_height:HEIGHT, :] = 0
        
        # 6. Overlay Subtitle
        active_card = None
        for (st, et, card) in sub_cards:
            if st <= t < et:
                active_card = card
                break
                
        if active_card:
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_frame = Image.fromarray(frame_rgb)
            cx = (WIDTH - active_card.width) // 2
            cy = HEIGHT - bar_height - active_card.height - 20
            pil_frame.paste(active_card, (cx, cy), active_card)
            frame = cv2.cvtColor(np.array(pil_frame), cv2.COLOR_RGB2BGR)
            
        try:
            proc.stdin.write(frame.tobytes())
        except (BrokenPipeError, IOError):
            break
            
    proc.stdin.close()
    proc.wait()
    print(f"Cinematic Scene Rendered: {output_path}")

def main():
    scenes = [
        {
            "img": "/home/user/media-inference-worker/cine_scene1.png",
            "audio": "/home/user/media-inference-worker/cine_voice1.mp3",
            "subtitles": [
                (0.2, 3.2, "Kayi saalon tak humne socha tha ki bhavishya door hai...")
            ],
            "motion": "dolly_in",
            "out": "/home/user/media-inference-worker/cine_clip1.mp4"
        },
        {
            "img": "/home/user/media-inference-worker/cine_scene2.png",
            "audio": "/home/user/media-inference-worker/cine_voice2.mp3",
            "subtitles": [
                (0.2, 4.4, "Lekin jab sach saamne aaya, tab ehsaas hua... waqt khatam ho chuka hai.")
            ],
            "motion": "dolly_out",
            "out": "/home/user/media-inference-worker/cine_clip2.mp4"
        },
        {
            "img": "/home/user/media-inference-worker/cine_scene3.png",
            "audio": "/home/user/media-inference-worker/cine_voice3.mp3",
            "subtitles": [
                (0.2, 3.2, "Ab shuru hoti hai insaniyat ki aakhiri udaan.")
            ],
            "motion": "pan_right",
            "out": "/home/user/media-inference-worker/cine_clip3.mp4"
        }
    ]
    
    for s in scenes:
        render_cinematic_scene(s["img"], s["audio"], s["subtitles"], s["out"], s["motion"])
        
    concat_list = "/home/user/media-inference-worker/cine_clips.txt"
    with open(concat_list, "w") as f:
        for s in scenes:
            f.write(f"file '{s['out']}'\n")
            
    merged_raw = "/home/user/media-inference-worker/cine_merged_raw.mp4"
    subprocess.run(['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', concat_list, '-c', 'copy', merged_raw], check=True)
    
    final_output = "/home/user/media-inference-worker/cinematic_movie_trailer.mp4"
    subprocess.run([
        'ffmpeg', '-y',
        '-i', merged_raw,
        '-i', '/home/user/media-inference-worker/cine_soundtrack.wav',
        '-filter_complex', '[1:a]volume=0.55[bg];[0:a][bg]amix=inputs=2:duration=first:dropout_transition=2[aout]',
        '-map', '0:v',
        '-map', '[aout]',
        '-c:v', 'libx264',
        '-profile:v', 'main',
        '-level', '4.0',
        '-movflags', '+faststart',
        '-c:a', 'aac',
        '-ar', '44100',
        '-ac', '2',
        '-b:a', '192k',
        final_output
    ], check=True)
    
    print(f"CINEMATIC MOVIE TRAILER READY: {final_output}")

if __name__ == "__main__":
    main()
