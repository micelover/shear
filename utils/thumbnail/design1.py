from utils.core.config import DIR_PATH, DATA_PATH, SOURCE_PATH, UTILS_PATH
from utils.core.edit import open_ai_generation, random_font
from utils.thumbnail.images import safe_load_images
from utils.thumbnail.render import draw_vertical_gradient, crop_to_visible_alpha, draw_text_box

from PIL import Image, ImageDraw, ImageFont, ImageFilter
import random
import json
from datetime import datetime
import math
import numpy as np
import cv2






impact = f"{SOURCE_PATH}/font/Impact-Font/impact.ttf"
anton = f"{SOURCE_PATH}/font/Anton/Anton-Regular.ttf"  
all_font_path = [impact, anton]

now = datetime.now()
year = now.year

def solve_width_scale(imgs, available_w, gap_px):
    """
    Computes the exact scale so that:
    sum(scaled image widths) + gaps == available_w
    """
    if not imgs:
        return 1.0

    total_raw_width = sum(img.width for img in imgs)
    total_gap = gap_px * (len(imgs) - 1)

    if total_raw_width <= 0:
        return 1.0

    return (available_w - total_gap) / total_raw_width

def create_design1(product_images, output_path="thumbnail.png"):
    if len(product_images) < 1:
        return False

    W, H = 1280, 720
    white_height = int(H * 0.23)

    title_font = random_font(all_font_path, size=130)
    ascent, descent = title_font.getmetrics()

    # ----------------------------
    # 1) BASE CANVAS (TRANSPARENT)
    # ----------------------------
    background = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    TOP_BLUE = (40, 180, 235)
    BOTTOM_BLUE = (0, 150, 215)

    # ----------------------------
    # 2) FLOOR (WOOD) — DRAW FIRST
    # ----------------------------
    wood = Image.open(f"{SOURCE_PATH}/visual/table.png").convert("RGBA")
    wood = crop_to_visible_alpha(wood)

    # scale wood by WIDTH (not height)
    wood = wood.resize((W, white_height), Image.Resampling.LANCZOS)

    # subtle polish
    wood = wood.filter(ImageFilter.GaussianBlur(radius=0.5))
    overlay = Image.new("RGBA", (W, white_height), (0, 0, 0, 30))
    wood = Image.alpha_composite(wood, overlay)

    # paste floor
    background.paste(wood, (0, H - white_height), wood)
    floor_top = H - white_height

    # ----------------------------
    # 3) SKY / BLUE BACKGROUND ABOVE FLOOR
    # ----------------------------
    sky_h = (H - white_height) + 5
    sky = Image.new("RGBA", (W, sky_h))
    draw_vertical_gradient(sky, TOP_BLUE, BOTTOM_BLUE)

    background.paste(sky, (0, 0))

    # ----------------------------
    # BASE LAYER
    # ----------------------------
    base_layer = background.copy()

    # ----------------------------
    # TITLE (UNCHANGED LOGIC)
    # ----------------------------
    title_text = random.choice([
        "STILL WORTH IT?",
        "HONEST REVIEW"
    ]).format(year=year)

    background_pad_y = 20
    temp = base_layer.copy()
    temp_draw = ImageDraw.Draw(temp)

    bbox = temp_draw.textbbox((0, 0), title_text, font=title_font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx = (W - tw) // 2
    ty = -((ascent - th) - background_pad_y) + 5

    temp_draw.text((tx, ty), title_text, font=title_font, fill="white")
    bbox = temp_draw.textbbox((tx, ty), title_text, font=title_font)

    x1, y1, x2, y2 = bbox
    w = x2 - x1
    h = y2 - y1

    # ----------------------------
    # LOAD IMAGES
    # ----------------------------
    imgs = safe_load_images(product_images)
    if not imgs:
        return False

    # ----------------------------
    # PRODUCT AREA
    # ----------------------------
    LEFT_PAD   = int(W * 0.05)
    RIGHT_PAD  = int(W * 0.05)
    TOP_LIMIT  = int(H * 0.3)
    BOTTOM_LIMIT = floor_top + int(white_height * 0.825)

    baseline_y = floor_top + int(white_height * 0.65)

    # ----------------------------
    # GRID SEARCH LAYOUT (OLD ALGORITHM)
    # ----------------------------
    top = TOP_LIMIT                     # just below title
    bottom = BOTTOM_LIMIT
    avail_w = W - LEFT_PAD - RIGHT_PAD
    avail_h = bottom - top

    max_imgs = min(7, len(imgs))
    best_layout = None
    best_fill_ratio = 0
    best_imgs_used = 0

    for use_n in range(2, max_imgs + 1):
        subset = imgs[:use_n]   # simple + deterministic
        n = len(subset)

        spacing = 10
        max_rows = min(4, n)

        for rows in range(1, max_rows + 1):
            cols = math.ceil(n / rows)

            cell_w = (avail_w - (cols - 1) * spacing) / cols
            cell_h = (avail_h - (rows - 1) * spacing) / rows

            layout = []
            idx = 0
            total_fill = 0

            for r in range(rows):
                row = []
                for c in range(cols):
                    if idx >= n:
                        break

                    img = subset[idx]
                    iw, ih = img.size
                    ratio = iw / ih

                    if ratio > cell_w / cell_h:
                        nw = cell_w
                        nh = cell_w / ratio
                    else:
                        nh = cell_h
                        nw = cell_h * ratio

                    nw, nh = int(nw), int(nh)
                    resized = img.resize((nw, nh), Image.Resampling.LANCZOS)

                    row.append(resized)
                    total_fill += nw * nh
                    idx += 1

                layout.append(row)

            fill_ratio = total_fill / (avail_w * avail_h)

            if fill_ratio > best_fill_ratio:
                # clean up old layout
                if best_layout:
                    for r in best_layout:
                        for im in r:
                            im.close()

                best_fill_ratio = fill_ratio
                best_layout = layout
                best_imgs_used = use_n
            else:
                # discard this layout
                for r in layout:
                    for im in r:
                        im.close()
    
    # ----------------------------
    # PASTE BEST LAYOUT (CENTERED)
    # ----------------------------
    used_h = sum(max(img.height for img in row) for row in best_layout) + spacing * (len(best_layout) - 1)
    y = top + (avail_h - used_h) / 2

    for row in best_layout:
        row_w = sum(img.width for img in row) + spacing * (len(row) - 1)
        if len(row) > 1:
            # total space available for gaps
            extra_space = avail_w - sum(img.width for img in row)
            gap = extra_space / (len(row) - 1)
        else:
            gap = 0

        x = LEFT_PAD
        row_h = max(img.height for img in row)

        for img in row:
            base_layer.paste(
                img,
                (int(x), int(y + (row_h - img.height) / 2)),
                img
            )
            x += img.width + gap
            img.close()

        y += row_h + spacing

    # ----------------------------
    # FINAL IMAGE (DEFINE IT!)
    # ----------------------------
    final = base_layer

    # ----------------------------
    # TITLE BOX + TEXT
    # ----------------------------
    final = draw_text_box(
        final,
        text_bbox=(x1, y1, w, h),
        color="red",
        thickness=8,
        pad_x=50,
        pad_y=20,
        radius=20
    )

    draw = ImageDraw.Draw(final)
    draw.text((tx, ty), title_text, font=title_font, fill="white")

    final.save(output_path)
    final.close()

    return True
