from utils.core.config import SOURCE_PATH
from utils.thumbnail.render import apply_vignette, crop_to_visible_alpha

from PIL import Image, ImageDraw, ImageFilter, ImageChops, ImageFont
import math
import aggdraw
import numpy as np
from datetime import datetime


W, H = (1280, 720)

impact_font = f"{SOURCE_PATH}/font/Impact-Font/impact.ttf"
anton_font = f"{SOURCE_PATH}/font/Anton/Anton-Regular.ttf"

TOP_GRAY    = (205, 205, 205)
BOTTOM_GRAY = (155, 155, 155)

current_date = datetime.now()
year = current_date.year

def white_ratio(img, threshold=240):
    """
    Returns percentage of pixels that are near-white.
    threshold: 240–255 range considered white.
    """
    img_small = img.resize((200, 200))  # speed boost
    arr = np.array(img_small)

    # If RGBA, ignore alpha
    if arr.shape[2] == 4:
        arr = arr[:, :, :3]

    # White if all channels are high
    white_pixels = np.sum(
        (arr[:, :, 0] > threshold) &
        (arr[:, :, 1] > threshold) &
        (arr[:, :, 2] > threshold)
    )

    total_pixels = arr.shape[0] * arr.shape[1]
    return white_pixels / total_pixels

def choose_best_image(image_paths, target_ratio=1.5):
    best_path = None
    best_score = float("inf")

    for path in image_paths:
        try:
            with Image.open(path) as img:
                ratio = img.width / img.height
                ratio_diff = abs(ratio - target_ratio)

                white_score = white_ratio(img)

                # Weight whiteness heavily
                score = (white_score * 5) + ratio_diff

                if score < best_score:
                    best_score = score
                    best_path = path

        except Exception as e:
            print(f"⚠️ Skipping {path}: {e}")

    return best_path

def draw_gray_gradient_bg(W, H):
    bg = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(bg)

    for y in range(H):
        t = y / (H - 1)
        r = int(TOP_GRAY[0] * (1 - t) + BOTTOM_GRAY[0] * t)
        g = int(TOP_GRAY[1] * (1 - t) + BOTTOM_GRAY[1] * t)
        b = int(TOP_GRAY[2] * (1 - t) + BOTTOM_GRAY[2] * t)
        draw.line((0, y, W, y), fill=(r, g, b))

    return bg.convert("RGBA")

import math

def create_design2(product_images, output_path="thumbnail.png"):
    canvas = Image.new("RGB", (W, H), (235, 235, 235)).convert("RGBA")

    print("Creating design3 with images:", product_images)
    chosen_img_path = choose_best_image(product_images, target_ratio=1.5)
    print("Chosen image for design3:", chosen_img_path)

    product = Image.open(chosen_img_path).convert("RGBA")

    max_height = int(H * 0.90)
    max_width  = int(W * 0.55)  # adjust depending on your layout

    scale_h = max_height / product.height
    scale_w = max_width / product.width

    # Use the smaller one so neither dimension exceeds limits
    scale = min(scale_h, scale_w)

    new_w = int(product.width * scale)
    new_h = int(product.height * scale)

    product = product.resize((new_w, new_h), Image.Resampling.LANCZOS)

    right_zone_start = int(W * 0.46)
    right_zone_end   = int(W * 0.96)

    product_x = right_zone_start + (
        (right_zone_end - right_zone_start - new_w) // 2
    )

    product_y = (H - new_h) // 2

    min_top_padding = int(H * 0.05)
    if product_y < min_top_padding:
        product_y = min_top_padding

    canvas.alpha_composite(product, (product_x, product_y))

    draw = ImageDraw.Draw(canvas)


    headline_font = ImageFont.truetype(impact_font, 140)  # or Anton
    buy_font = ImageFont.truetype(impact_font, 140)

    left_margin = int(W * 0.05)
    top_margin = int(H * 0.18)

    # TEXT CONTENT
    line1 = "STILL"
    line2 = "WORTH"
    line3 = "IT?"

    line_spacing = 20  # smaller gap between lines

    # --- Measure text heights dynamically ---
    bbox1 = draw.textbbox((0, 0), line1, font=headline_font)
    h1 = bbox1[3] - bbox1[1]
    w1 = bbox1[2] - bbox1[0]

    bbox2 = draw.textbbox((0, 0), line2, font=headline_font)
    h2 = bbox2[3] - bbox2[1]

    bbox3 = draw.textbbox((0, 0), line3, font=buy_font)

    line_spacing = 20  # smaller gap between main lines

    # --- Draw Line 1 ---
    y1 = top_margin
    draw.text((left_margin, y1), line1, fill=(0, 0, 0), font=headline_font)

    # --- Draw Line 2 ---
    y2 = y1 + h1 + line_spacing
    draw.text((left_margin, y2), line2, fill=(0, 0, 0), font=headline_font)

    # --- BUY IT BLOCK (clean structure) ---

    # Position BUY IT 20px below SEE THIS
    bbox2 = draw.textbbox((0, 0), line2, font=headline_font)
    bottom_of_line2 = y2 + bbox2[3]
    y3 = bottom_of_line2 + line_spacing

    # Measure BUY IT text first
    bbox3 = draw.textbbox((0, 0), line3, font=buy_font)
    text_w = bbox3[2] - bbox3[0]
    text_h = bbox3[3] - bbox3[1]

    # Add real padding (important)
    padding_x = 5
    padding_y = 5

    box_w = text_w + padding_x * 2
    box_h = text_h + padding_y * 2

    # Create combined block
    buy_block = Image.new("RGBA", (box_w, box_h), (0, 0, 0, 0))
    buy_draw = ImageDraw.Draw(buy_block)

    # Draw box first
    buy_draw.rectangle((0, 0, box_w, box_h), fill=(0, 0, 0))

    # Measure actual bounding box inside mini-canvas
    bbox = buy_draw.textbbox((0, 0), line3, font=buy_font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    # True center correction (important!)
    text_x = (box_w - text_w) // 2 - bbox[0]
    text_y = (box_h - text_h) // 2 - bbox[1]

    buy_draw.text((text_x, text_y), line3, fill=(255, 215, 0), font=buy_font)

    # Paste final combined block
    canvas.alpha_composite(buy_block, (left_margin - padding_x, y3))

    # ----------------------------
    # CURVED ARROW
    # ----------------------------
    bottom_of_line1 = y1 + bbox1[3]
    right_of_line1 = left_margin + w1
    arrow_padding = 40

    base_x = right_of_line1 + arrow_padding
    base_y = bottom_of_line1 - 5
    
    target_x = product_x - 10
    target_y = product_y + int(product.height * (1/4))

    # ---- Build circle center (keep your sagitta math) ----

    dx = target_x - base_x
    dy = target_y - base_y
    d = math.hypot(dx, dy)

    curvature = 0.97
    h = d * curvature
    R = (d*d) / (8*h) + (h/2)

    mx = (base_x + target_x) / 2
    my = (base_y + target_y) / 2

    # Perpendicular unit vector
    ux = -dy / d
    uy = dx / d

    # Force upward bulge
    if uy > 0:
        ux = -ux
        uy = -uy

    t = R - h

    center_x = mx + ux * t
    center_y = my + uy * t

    # ---- Sample arc manually ----

    start_angle = math.atan2(base_y - center_y, base_x - center_x)
    end_angle   = math.atan2(target_y - center_y, target_x - center_x)

    # Ensure we go the shorter upward path
    if end_angle < start_angle:
        end_angle += 2 * math.pi

    num_points = 120
    points = []

    for i in range(num_points + 1):
        theta = start_angle + (end_angle - start_angle) * (i / num_points)
        x = center_x + R * math.cos(theta)
        y = center_y + R * math.sin(theta)
        points.append((x, y))

    # ---- Draw smooth path ----

    agg_draw = aggdraw.Draw(canvas)
    pen = aggdraw.Pen((0, 0, 0), width=12)

    path = aggdraw.Path()
    path.moveto(*points[0])

    for pt in points[1:]:
        path.lineto(*pt)

    agg_draw.path(path, pen)

    width = 12
    radius = width // 2
    brush = aggdraw.Brush((0, 0, 0))

    # Round start cap
    agg_draw.ellipse((
        points[0][0] - radius,
        points[0][1] - radius,
        points[0][0] + radius,
        points[0][1] + radius
    ), brush)

    # Round end cap
    agg_draw.ellipse((
        points[-1][0] - radius,
        points[-1][1] - radius,
        points[-1][0] + radius,
        points[-1][1] + radius
    ), brush)

    # ---- Draw simple open arrowhead at the end ----

    angle = math.atan2(
        points[-1][1] - points[-5][1],
        points[-1][0] - points[-5][0]
    )

    arrow_size = 40
    arrow_angle = math.pi / 4

    left_point = (
        points[-1][0] - arrow_size * math.cos(angle - arrow_angle),
        points[-1][1] - arrow_size * math.sin(angle - arrow_angle)
    )

    right_point = (
        points[-1][0] - arrow_size * math.cos(angle + arrow_angle),
        points[-1][1] - arrow_size * math.sin(angle + arrow_angle)
    )

    width = 11
    radius = width // 2

    pen_arrow = aggdraw.Pen((0, 0, 0), width=width)
    brush = aggdraw.Brush((0, 0, 0))

    # ---- Draw left line ----
    left_line = aggdraw.Path()
    left_line.moveto(*left_point)
    left_line.lineto(*points[-1])
    agg_draw.path(left_line, pen_arrow)

    # ---- Draw right line ----
    right_line = aggdraw.Path()
    right_line.moveto(*points[-1])
    right_line.lineto(*right_point)
    agg_draw.path(right_line, pen_arrow)

    # ---- Add rounded caps ONLY at outer ends ----

    agg_draw.ellipse((
        left_point[0] - radius,
        left_point[1] - radius,
        left_point[0] + radius,
        left_point[1] + radius
    ), brush)

    agg_draw.ellipse((
        right_point[0] - radius,
        right_point[1] - radius,
        right_point[0] + radius,
        right_point[1] + radius
    ), brush)

    agg_draw.flush()

    canvas.save(output_path)
    return True

