from utils.core.config import DIR_PATH, DATA_PATH, SOURCE_PATH, UTILS_PATH
from utils.core.edit import open_ai_generation

from moviepy import (
    ImageClip, ColorClip, TextClip, CompositeVideoClip, vfx
)
from moviepy.video.fx.FadeIn import FadeIn
from moviepy.video.fx.FadeOut import FadeOut
import json
import re





canvas_size = (1280, 720)

with open(f"{UTILS_PATH}/prompts/get_specs.txt", "r") as f:
    orignial_get_specs_prompt = f.read()

open_sans = f"{SOURCE_PATH}/font/Open_Sans/OpenSans-Bold.ttf"
poppins_bold = f"{SOURCE_PATH}/font/poppins_bold.ttf"
sf_pro_med = f"{SOURCE_PATH}/font/sf_pro/SFPRODISPLAYMEDIUM.OTF"

def srt_time_to_seconds(s: str) -> float:
    h, m, s_ms = s.split(":")
    s, ms = s_ms.split(",")
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0

def _generate_key_spec(spec_text, duration=4, position_x=50):
    spec_clip = TextClip(
        text=spec_text,
        font_size=125,
        color="white",
        font=poppins_bold,
        stroke_color="black",
        stroke_width=5,
        size=(None, int(0.25 * canvas_size[1]))
    ).with_duration(duration)

    # ✅ Animate opacity by animating the MASK
    spec_clip = spec_clip.with_mask(
        spec_clip.mask.with_effects([
            FadeIn(0.25).copy(),
            FadeOut(0.45).copy()
        ])
    )

    # ✅ Bottom aligned (50px from bottom)
    spec_clip = spec_clip.with_position((
        position_x, 
        canvas_size[1] - spec_clip.h - 40
    ))
    return spec_clip

def _generate_basic_spec(
    spec_text,
    start_t,
    duration=3.5,
    video_size=(1280, 720),
    all_specs=None
):
    w, h = video_size
    STACK_SPACING = 100
    TOP_MARGIN = 10
    margin = 10

    all_specs = all_specs or []

    title_box_height = int(h * 0.20)

    # --- Text ---
    txt_title = TextClip(
        text=spec_text,
        font_size=90,
        color="#FFFFFF",
        font=sf_pro_med,
        stroke_color="black",
        stroke_width=2,     # 🔑 thin stroke
        size=(None, title_box_height),
        method="label"
    ).with_duration(duration)

    txt_title_w, txt_title_h = txt_title.size

    # --- Vertical stacking ---
    def compute_stack_y(t):
        global_t = t + start_t

        active = [s for s in all_specs if s["start"] <= global_t < s["end"]]
        if not active:
            return h + 100

        active.sort(key=lambda s: s["start"], reverse=True)

        for i, s in enumerate(active):
            if s["start"] == start_t:
                return TOP_MARGIN + i * STACK_SPACING

        return h + 100

    # --- Fixed position (top-right) ---
    target_x = max(margin, w - txt_title_w - margin)
    baseline_fix = int(txt_title_h * 0.12)

    txt_title = txt_title.with_position(
        lambda t: (
            target_x,
            compute_stack_y(t) - baseline_fix
        )
    )

    # --- Fade in / out (SAFE) ---
    txt_title = txt_title.with_mask(
        txt_title.mask.with_effects([
            FadeIn(0.25).copy(),
            FadeOut(0.45).copy()
        ])
    )


    overlay = CompositeVideoClip([txt_title], size=video_size)
    return overlay.with_duration(duration)

def create_specs(srt_path, start=0, size=(1280,720)):
    with open(srt_path, "r", encoding="utf-8") as f:
        srt_text = f.read().strip()

    get_specs_prompt = orignial_get_specs_prompt.replace("{SRT}", srt_text)

    spec_overlays = []
    sound_effects = []

    spec_response = open_ai_generation(get_specs_prompt, model="gpt-5-mini", temperature=0.3)
    if isinstance(spec_response, str):
        cleaned = re.sub(r"^```(?:json)?|```$", "", spec_response.strip(), flags=re.MULTILINE).strip()
        try:
            spec_dict = json.loads(cleaned)
        except json.JSONDecodeError:
            spec_dict = spec_response
    elif isinstance(spec_response, dict):
        print("[specs] ❌ JSON parse failed:", e)
        return
    else:
        print("[specs] ❌ Unexpected response type:", type(spec_response))
        return
    
    if not isinstance(spec_dict, dict):
        print("[specs] ❌ Parsed result is not a dict")
        return
    
    basic_specs = spec_dict["basic_spec"]
    price_specs = spec_dict["price_spec"]

    PRICE_DUR = 4
    BASIC_DUR = 3.5
    
    price_spec_x = 50
    for spec_obj in price_specs:
        try:
            print(f"[specs] {spec_obj['text']}: {spec_obj['start']}")
            start_time = srt_time_to_seconds(spec_obj['start'])
            price = spec_obj['text'].strip()
            if "$" not in price:
                price = "$" + price
            spec_clip_obj = _generate_key_spec(price, duration=PRICE_DUR, position_x=price_spec_x)
            spec_clip_obj = (spec_clip_obj
                .with_duration(PRICE_DUR)
                .with_start(start + start_time)
            )

            spec_overlays.append(spec_clip_obj)
            sound_effects.append({
                "role": "price_appear",
                "time": start + start_time
            })
        except Exception as e:
            print(f"[specs] ⚠️ Error creating spec clip: {e}")
            continue

    basic_spec_timeline = []

    for spec_obj in basic_specs:
        start_time = srt_time_to_seconds(spec_obj["start"])
        start_t = start + start_time
        end_t = start_t + BASIC_DUR

        basic_spec_timeline.append({
            "text": spec_obj["text"].title(),
            "start": start_t,
            "end": end_t
        })
    
    for spec in basic_spec_timeline:
        try:
            spec_clip_obj = _generate_basic_spec(
                spec["text"],
                start_t=spec["start"],
                duration=BASIC_DUR,
                video_size=size,
                all_specs=basic_spec_timeline
            ).with_start(spec["start"])

            spec_overlays.append(spec_clip_obj)

        except Exception as e:
            print(f"[specs] ⚠️ Error creating spec clip: {e}")
            continue
    
    print(f"[specs] Generated {len(spec_overlays)} spec overlays.")

    return spec_overlays, sound_effects




