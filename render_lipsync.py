#!/usr/bin/env python3
import os
import math
import subprocess
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont
import wave

FPS = 30
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

def extract_audio_energy(audio_path, total_frames):
    # Convert audio to mono wav 16kHz for analysis
    temp_wav = "/home/user/media-inference-worker/temp_eval.wav"
    subprocess.run(['ffmpeg', '-y', '-i', audio_path, '-ar', '16000', '-ac', '1', temp_wav], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    
    with wave.open(temp_wav, 'rb') as wf:
        sample_rate = wf.getframerate()
        n_samples = wf.getnframes()
        raw_data = wf.readframes(n_samples)
        samples = np.frombuffer(raw_data, dtype=np.int16).astype(np.float32) / 32768.0
        
    samples_per_frame = int(sample_rate / FPS)
    energies = []
    
    for f in range(total_frames):
        start_s = f * samples_per_frame
        end_s = min(len(samples), (f + 1) * samples_per_frame)
        if start_s < len(samples) and end_s > start_s:
            chunk = samples[start_s:end_s]
            rms = np.sqrt(np.mean(chunk**2))
            energies.append(rms)
        else:
            energies.append(0.0)
            
    energies = np.array(energies)
    # Normalize with dynamic noise floor
    max_e = np.percentile(energies, 95) if len(energies) > 0 else 1.0
    if max_e > 0.001:
        energies = np.clip((energies - 0.015) / (max_e - 0.015 + 1e-6), 0.0, 1.0)
    else:
        energies = np.zeros_like(energies)
        
    # Smooth with asymmetric attack/decay
    smoothed = np.zeros_like(energies)
    curr = 0.0
    for i in range(len(energies)):
        target = energies[i]
        if target > curr:
            curr += (target - curr) * 0.75 # fast attack
        else:
            curr += (target - curr) * 0.35 # smooth decay
        smoothed[i] = curr
        
    # Boost speaking open factor
    smoothed = np.power(smoothed, 0.85) * 1.2
    smoothed = np.clip(smoothed, 0.0, 1.0)
    return smoothed

def animate_mouth_and_eyes(base_bgr, mouth_box, eyes_box, open_val, blink_val, is_anime=False):
    """
    Morphs mouth & jaw open/close, adds oral cavity/teeth, and blinks eyes seamlessly
    """
    img = base_bgr.copy()
    h, w, _ = img.shape
    mx, my, mw, mh = mouth_box
    
    if open_val > 0.04:
        # Mouth open amount in pixels
        max_jaw_drop = 22 if not is_anime else 14
        jaw_drop = int(open_val * max_jaw_drop)
        
        # Crop mouth ROI with generous margin
        pad_y = 40
        pad_x = 30
        roi_y1 = max(0, my - pad_y)
        roi_y2 = min(h, my + mh + pad_y + jaw_drop)
        roi_x1 = max(0, mx - pad_x)
        roi_x2 = min(w, mx + mw + pad_x)
        
        mouth_roi = img[roi_y1:roi_y2, roi_x1:roi_x2].copy()
        rh, rw, _ = mouth_roi.shape
        
        # Create displacement grid for mesh warp
        grid_y, grid_x = np.mgrid[0:rh, 0:rw].astype(np.float32)
        
        # Center of mouth in ROI
        cmx = (mx - roi_x1) + mw // 2
        cmy = (my - roi_y1) + mh // 2
        
        # Radial distance from mouth center
        dx = (grid_x - cmx) / (mw * 0.65)
        dy = (grid_y - cmy) / (mh * 0.85)
        dist = dx**2 + dy**2
        
        # Influence mask
        influence = np.exp(-dist * 1.8)
        
        # Upper lip moves slightly UP
        upper_mask = (grid_y < cmy) * influence
        grid_y -= upper_mask * (jaw_drop * 0.28)
        
        # Lower lip and jaw move DOWN
        lower_mask = (grid_y >= cmy) * influence
        grid_y += lower_mask * (jaw_drop * 0.95)
        
        # Horizontal stretch / narrowing
        stretch_mask = influence * 0.15
        grid_x += stretch_mask * (grid_x - cmx) * (open_val * 0.2)
        
        # Remap warped skin
        warped_roi = cv2.remap(mouth_roi, grid_x, grid_y, cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_REFLECT)
        
        # Draw realistic inner mouth aperture (oral cavity + teeth)
        cavity_w = int(mw * (0.35 + 0.35 * open_val))
        cavity_h = int(jaw_drop * 0.75)
        
        if cavity_h > 2:
            cavity_cx = int(cmx)
            cavity_cy = int(cmy + jaw_drop * 0.2)
            
            # Dark oral cavity ellipse
            cv2.ellipse(warped_roi, (cavity_cx, cavity_cy), (cavity_w // 2, cavity_h // 2), 0, 0, 360, (15, 8, 25), -1)
            
            if not is_anime:
                # Realistic upper teeth highlight
                teeth_w = int(cavity_w * 0.65)
                teeth_h = max(2, int(cavity_h * 0.35))
                teeth_y = cavity_cy - cavity_h // 2 + teeth_h // 2
                cv2.ellipse(warped_roi, (cavity_cx, teeth_y), (teeth_w // 2, teeth_h // 2), 0, 0, 180, (220, 225, 230), -1)
                
                # Pink tongue gradient at bottom
                tongue_w = int(cavity_w * 0.55)
                tongue_h = max(2, int(cavity_h * 0.35))
                tongue_y = cavity_cy + cavity_h // 2 - tongue_h // 2
                cv2.ellipse(warped_roi, (cavity_cx, tongue_y), (tongue_w // 2, tongue_h // 2), 0, 180, 360, (70, 50, 130), -1)
                
            # Soft blur on inner cavity boundary
            warped_roi = cv2.GaussianBlur(warped_roi, (3, 3), 0.5)
            
        # Seamlessly blend ROI back into main image
        mask_blend = np.clip(np.exp(-dist * 1.5) * 1.2, 0, 1)[:, :, np.newaxis]
        img[roi_y1:roi_y2, roi_x1:roi_x2] = (warped_roi * mask_blend + mouth_roi * (1.0 - mask_blend)).astype(np.uint8)

    # 2. Eye Blinking
    if blink_val > 0.05:
        ex, ey, ew, eh = eyes_box
        # Skin tone sample above eyes
        skin_color = np.mean(img[ey-25:ey-10, ex:ex+ew], axis=(0, 1))
        
        # Eyelid closure
        eyelid_h = int(eh * blink_val)
        y_top = ey
        y_bottom = ey + eyelid_h
        
        # Overlay eyelid fold
        for yi in range(y_top, min(h, y_bottom + 4)):
            prog = (yi - y_top) / max(1, eyelid_h)
            color = skin_color * (0.85 + 0.15 * math.sin(prog * math.pi))
            alpha = min(1.0, blink_val * 1.4)
            img[yi, ex:ex+ew] = (img[yi, ex:ex+ew] * (1 - alpha) + color * alpha).astype(np.uint8)
            
    return img

def create_styled_subtitle(text, font_size=38):
    font = ImageFont.truetype(FONT_PATH, font_size)
    dummy_img = Image.new('RGBA', (10, 10))
    dummy_draw = ImageDraw.Draw(dummy_img)
    
    bbox = dummy_draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    
    card_w = tw + 70
    card_h = th + 36
    card = Image.new('RGBA', (card_w, card_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(card)
    
    draw.rounded_rectangle([(0, 0), (card_w, card_h)], radius=18, fill=(10, 15, 30, 190), outline=(56, 189, 248, 180), width=2)
    draw.text((37, 18), text, font=font, fill=(0, 0, 0, 220))
    draw.text((35, 16), text, font=font, fill=(255, 255, 255, 255))
    return card

def render_talking_avatar_video(image_path, audio_path, mouth_box, eyes_box, subtitles, output_path, is_anime=False, target_w=1920, target_h=1080):
    base_img = cv2.imread(image_path)
    orig_h, orig_w, _ = base_img.shape
    
    # Calculate audio duration
    cmd = ['ffmpeg', '-i', audio_path]
    res = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    import re
    match = re.search(r'Duration:\s*(\d+):(\d+):(\d+\.\d+)', res.stderr)
    duration = int(match.group(1))*3600 + int(match.group(2))*60 + float(match.group(3)) if match else 8.5
    
    total_frames = int(duration * FPS)
    energies = extract_audio_energy(audio_path, total_frames)
    
    # Pre-calculate blink events (at 2.2s and 5.8s and 7.8s)
    blink_curve = np.zeros(total_frames)
    blink_times = [2.2, 5.5, 7.8]
    for bt in blink_times:
        bf = int(bt * FPS)
        for i in range(-3, 4):
            if 0 <= bf + i < total_frames:
                # Triangular blink shape
                blink_curve[bf + i] = max(0, 1.0 - abs(i) / 3.5)
                
    ffmpeg_cmd = [
        'ffmpeg', '-y',
        '-f', 'rawvideo',
        '-vcodec', 'rawvideo',
        '-s', f'{target_w}x{target_h}',
        '-pix_fmt', 'bgr24',
        '-r', str(FPS),
        '-i', '-',
        '-i', audio_path,
        '-c:v', 'libx264',
        '-preset', 'fast',
        '-profile:v', 'main',
        '-level', '4.0',
        '-movflags', '+faststart',
        '-crf', '19',
        '-c:a', 'aac',
        '-ar', '44100',
        '-ac', '2',
        '-b:a', '192k',
        '-pix_fmt', 'yuv420p',
        output_path
    ]
    
    proc = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE)
    sub_cards = [(st, et, create_styled_subtitle(txt)) for (st, et, txt) in subtitles]
    
    for f in range(total_frames):
        t = f / FPS
        open_val = energies[f] if f < len(energies) else 0.0
        blink_val = blink_curve[f] if f < len(blink_curve) else 0.0
        
        # 1. Animate Mouth & Eyes
        frame_anim = animate_mouth_and_eyes(base_img, mouth_box, eyes_box, open_val, blink_val, is_anime)
        
        # 2. Natural Camera & Head Motion
        head_nod = math.sin(t * 2.2) * 4 * (0.3 + 0.7 * open_val) # nods with speech
        head_sway = math.cos(t * 1.4) * 3
        breathe = math.sin(t * 1.8) * 2
        
        scale = 1.02 + 0.015 * math.sin(t * 0.8)
        cw = orig_w / scale
        ch = orig_h / scale
        cx = orig_w / 2 + head_sway
        cy = orig_h / 2 + head_nod + breathe
        
        x1 = int(max(0, min(orig_w - cw, cx - cw / 2)))
        y1 = int(max(0, min(orig_h - ch, cy - ch / 2)))
        x2 = int(x1 + cw)
        y2 = int(y1 + ch)
        
        frame_cropped = frame_anim[y1:y2, x1:x2]
        frame = cv2.resize(frame_cropped, (target_w, target_h), interpolation=cv2.INTER_LANCZOS4)
        
        # 3. 35mm Film Grain & Cinematic Atmosphere
        grain = np.random.normal(0, 3.5, (target_h, target_w, 3)).astype(np.int16)
        frame = np.clip(frame.astype(np.int16) + grain, 0, 255).astype(np.uint8)
        
        # 4. Cinematic Widescreen Letterbox
        bar_height = int(target_h * 0.07)
        frame[0:bar_height, :] = 0
        frame[target_h - bar_height:target_h, :] = 0
        
        # 5. Overlay Subtitle
        active_card = None
        for (st, et, card) in sub_cards:
            if st <= t < et:
                active_card = card
                break
                
        if active_card:
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_frame = Image.fromarray(frame_rgb)
            cx = (target_w - active_card.width) // 2
            cy = target_h - bar_height - active_card.height - 18
            pil_frame.paste(active_card, (cx, cy), active_card)
            frame = cv2.cvtColor(np.array(pil_frame), cv2.COLOR_RGB2BGR)
            
        try:
            proc.stdin.write(frame.tobytes())
        except (BrokenPipeError, IOError):
            break
            
    proc.stdin.close()
    proc.wait()
    print(f"Talking Character Video Ready: {output_path}")

def main():
    # 1. Generate Realistic Cinematic Commander Lip Sync (1080p Widescreen)
    print("Rendering Cinematic Realistic Talking Character...")
    render_talking_avatar_video(
        image_path="/home/user/media-inference-worker/talker_cinematic.png",
        audio_path="/home/user/media-inference-worker/lipsync_voice.mp3",
        mouth_box=(355, 655, 140, 60), # mx, my, mw, mh
        eyes_box=(290, 480, 270, 50),
        subtitles=[
            (0.1, 2.5, "Namaste dosto! 🎙️"),
            (2.5, 6.2, "Ab aap AI se realistic cinematic video aur lip-sync bana sakte hain."),
            (6.2, 8.8, "Ye bilkul real aur cinematic lagta hai! ✨")
        ],
        output_path="/home/user/media-inference-worker/ai_lipsync_cinematic.mp4",
        is_anime=False,
        target_w=1920,
        target_h=1080
    )
    
    # 2. Generate Anime Lip Sync (1080p Widescreen)
    print("Rendering Anime Talking Character...")
    render_talking_avatar_video(
        image_path="/home/user/media-inference-worker/talker_anime.png",
        audio_path="/home/user/media-inference-worker/lipsync_voice.mp3",
        mouth_box=(665, 315, 80, 45),
        eyes_box=(600, 220, 210, 45),
        subtitles=[
            (0.1, 2.5, "Namaste dosto! 🎙️"),
            (2.5, 6.2, "Ab aap AI se realistic cinematic video aur lip-sync bana sakte hain."),
            (6.2, 8.8, "Ye bilkul real aur cinematic lagta hai! ✨")
        ],
        output_path="/home/user/media-inference-worker/ai_lipsync_anime.mp4",
        is_anime=True,
        target_w=1920,
        target_h=1080
    )

if __name__ == "__main__":
    main()
