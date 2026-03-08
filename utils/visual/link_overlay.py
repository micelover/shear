from utils.core.config import DIR_PATH, DATA_PATH, SOURCE_PATH, UTILS_PATH
from utils.core.edit import open_ai_generation

from moviepy import (
    VideoClip, ImageClip
)
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import json




video_size = (1280, 720)

nunito_bold = f"{SOURCE_PATH}/font/Nunito/Nunito-Bold.ttf"

with open(f"{UTILS_PATH}/prompts/links.txt", "r") as f:
    orignial_links_prompt = f.read()

def _overlay_time_range(srt_path):
    with open(srt_path, "r", encoding="utf-8") as f:
        srt_text = f.read().strip()

    intro_info_prompt = orignial_links_prompt.replace("{srt}", srt_text)
    response = open_ai_generation(intro_info_prompt, model="gpt-4.1", temperature=0.5).strip()

    try:
        overlay_times = json.loads(response)
    except Exception as e:
        print("Error parsing overlay times JSON:", e)
        return False

    return overlay_times

def _generate_link_overlay(
    text,
    duration=3.5,
    reveal_time=0.25,   # expand speed
    hide_time=0.25,     # collapse speed
    size=(800, 150),
    radius=40,
    bg_color = (230, 184, 40),
    text_color=(248, 248, 248),
    font_path=None,
    font_size=70,
):
    W, H = size
    MIN_W = 6

    # -----------------------
    # PIL render (once)
    # -----------------------
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    draw.rounded_rectangle((0, 0, W, H), radius=radius, fill=bg_color)

    font = ImageFont.truetype(font_path, font_size) if font_path else ImageFont.load_default()
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]

    draw.text(((W - tw) // 2, ((H - th) // 2) - 10), text, font=font, fill=text_color)


    arr = np.array(img)

    rgb = arr[:, :, :3]                 # image pixels
    alpha = arr[:, :, 3] / 255.0        # 2D transparency mask

    clip = ImageClip(rgb).with_duration(duration)


    # -----------------------
    # Mask with expand + collapse
    # -----------------------
    def ease_out(p):
        return 1 - (1 - p) ** 3

    def combined_mask(t):
        # expand → hold → collapse
        if t < reveal_time:
            p = ease_out(t / reveal_time)
        elif t < duration - hide_time:
            p = 1.0
        else:
            p = 1 - ease_out((t - (duration - hide_time)) / hide_time)

        w = int(MIN_W + p * (W - MIN_W))

        reveal = np.zeros((H, W), dtype=np.float32)
        x0 = (W - w) // 2
        x1 = x0 + w
        reveal[:, x0:x1] = 1.0

        # 🔑 THIS LINE PRESERVES ROUNDED CORNERS
        return alpha * reveal

    mask = VideoClip(combined_mask, duration=duration)
    mask.ismask = True

    return clip.with_mask(mask)

def create_link_overlay(srt_path):
    all_overlay_clips = []

    overlay_times = _overlay_time_range(srt_path)
    if not overlay_times:
        return all_overlay_clips

    link_times = overlay_times.get("links", [])

    if link_times:
        try:
            link_clip = _generate_link_overlay(
                "Links are in the description",
                duration=link_times["end"] - link_times["start"],
                reveal_time=0.18,   # fast in
                hide_time=0.18,     # fast out
                size=(900, 125),
                font_path=nunito_bold,
            ).with_start(link_times["start"]).with_position(("center", video_size[1]//1.35))

            return link_clip
        except Exception as e:
            print("Error generating link overlay:", e)

    return None

