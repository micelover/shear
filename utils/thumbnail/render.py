from PIL import Image, ImageDraw, ImageFilter
import math


def draw_vertical_gradient(img, top_color, bottom_color):
    """
    Draws a vertical gradient from top_color → bottom_color onto img.
    img must be RGB or RGBA.
    """
    w, h = img.size
    draw = ImageDraw.Draw(img)

    for y in range(h):
        t = y / h
        r = int(top_color[0] * (1 - t) + bottom_color[0] * t)
        g = int(top_color[1] * (1 - t) + bottom_color[1] * t)
        b = int(top_color[2] * (1 - t) + bottom_color[2] * t)
        draw.line((0, y, w, y), fill=(r, g, b))

def apply_vignette(img, strength=0.6, power=2.6, inner=0.12):
    """
    strength: how dark the edges get (0.55–0.75)
    power:    how sharp the falloff is (2.4–3.2)
    inner:    radius of protected bright center (0.12–0.22)
    """
    W, H = img.size
    cx, cy = W / 2, H / 2
    max_dist = math.sqrt(cx**2 + cy**2)

    px = img.load()

    for y in range(H):
        for x in range(W):
            dx = x - cx
            dy = y - cy
            dist = math.sqrt(dx*dx + dy*dy)

            t = dist / max_dist

            # 🔒 protect center so it doesn't brighten too fast
            if t < inner:
                v = 0.0
            else:
                # remap [inner → 1] → [0 → 1]
                t2 = (t - inner) / (1 - inner)
                v = t2 ** power

            factor = 1 - strength * v

            r, g, b, a = px[x, y]
            px[x, y] = (
                int(r * factor),
                int(g * factor),
                int(b * factor),
                a
            )

    return img

def crop_to_visible_alpha(img, pad=2):
    """
    Crops away all fully-transparent pixels from all sides.
    pad: small safety margin so we never cut into the product.
    """
    if img.mode != "RGBA":
        img = img.convert("RGBA")

    alpha = img.getchannel("A")
    bbox = alpha.getbbox()  # bounding box of alpha > 0

    if bbox is None:
        return img  # fully transparent image (should not happen)

    x1, y1, x2, y2 = bbox

    # apply safety padding
    x1 = max(0, x1 - pad)
    y1 = max(0, y1 - pad)
    x2 = min(img.width,  x2 + pad)
    y2 = min(img.height, y2 + pad)

    return img.crop((x1, y1, x2, y2))

def draw_glow_text(base_img, position, text, font, text_color="white", glow_color="black", blur_radius=6):
    x, y = position

    # Ensure base image is RGBA
    if base_img.mode != "RGBA":
        base_img = base_img.convert("RGBA")

    # Transparent layer for glow
    temp_img = Image.new("RGBA", base_img.size, (0, 0, 0, 0))
    temp_draw = ImageDraw.Draw(temp_img)

    # Draw glow text
    temp_draw.text((x, y), text, font=font, fill=glow_color)

    # Blur glow
    glow = temp_img.filter(ImageFilter.GaussianBlur(blur_radius))

    # Make sure glow is also RGBA
    if glow.mode != "RGBA":
        glow = glow.convert("RGBA")

    # Composite glow onto base
    base_img = Image.alpha_composite(base_img, glow)

    # Draw final text on top
    draw = ImageDraw.Draw(base_img)
    draw.text((x, y), text, font=font, fill=text_color)

    return base_img  # return updated image

def draw_text_box(
    image,
    text_bbox,
    color="white",
    thickness=6,          # now means BORDER width
    pad_x=20,
    pad_y=20,
    radius=0,
    has_border=False,
    border_color=(0, 0, 0),
):
    x, y, w, h = text_bbox

    x1 = x - pad_x
    y1 = y - pad_y
    x2 = x + w + pad_x
    y2 = y + h + pad_y

    draw = ImageDraw.Draw(image)

    outline = border_color if has_border else None
    width = thickness if has_border else 0

    if radius > 0:
        draw.rounded_rectangle(
            [(x1, y1), (x2, y2)],
            radius=radius,
            fill=color,
            outline=outline,
            width=width
        )
    else:
        draw.rectangle(
            [(x1, y1), (x2, y2)],
            fill=color,
            outline=outline,
            width=width
        )

    return image

def subtle_tilt(img, angle_deg=3):
    """
    Applies a very subtle perspective-like tilt using rotation.
    Keeps transparency and avoids aggressive distortion.
    """
    if img.mode != "RGBA":
        img = img.convert("RGBA")

    return img.rotate(
        angle_deg,
        resample=Image.Resampling.BICUBIC,
        expand=True,
        fillcolor=(0, 0, 0, 0)
    )

def paste_realistic_shadow(
    shadow_layer,
    img,
    position,
    floor_top,
    opacity=90,
    blur=12
):
    x, y = position
    iw, ih = img.size

    # Shadow size = just smaller than base
    sw = int(iw * 0.85)
    sh = max(6, int(sw * 0.12))

    shadow = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
    draw = ImageDraw.Draw(shadow)

    draw.ellipse(
        [(0, 0), (sw, sh)],
        fill=(0, 0, 0, opacity)
    )

    shadow = shadow.filter(ImageFilter.GaussianBlur(blur))

    sx = int(x + (iw - sw) / 2)
    sy = max(
        int(y + ih - sh // 2),
        floor_top
    )

    shadow_layer.paste(shadow, (sx, sy), shadow)
    shadow.close()

def add_box_shadow(
    canvas,
    box_coords,
    radius=0,
    offset=(8, 12),      # (right, down)
    shadow_color=(0, 0, 0),
    shadow_alpha=120,
    blur=20
):
    """
    box_coords: (x1, y1, x2, y2)
    radius: same radius as the rectangle
    offset: shadow shift (x, y)
    shadow_alpha: darkness of shadow
    blur: softness
    """

    x1, y1, x2, y2 = box_coords
    ox, oy = offset

    shadow_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(shadow_layer)

    shadow_box = (
        x1 + ox,
        y1 + oy,
        x2 + ox,
        y2 + oy
    )

    if radius > 0:
        d.rounded_rectangle(
            shadow_box,
            radius=radius,
            fill=(*shadow_color, shadow_alpha)
        )
    else:
        d.rectangle(
            shadow_box,
            fill=(*shadow_color, shadow_alpha)
        )

    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(blur))

    canvas.alpha_composite(shadow_layer)

def _smart_crop_top(img, height, target_height):
    try:
        import cv2
        import numpy as np

        cv_img = cv2.cvtColor(np.array(img.convert("RGB")), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
        cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
        faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(50, 50))

        if len(faces) > 0:
            topmost_face_y = min(y for (_, y, _, _) in faces)
            ideal_top = topmost_face_y - 60  # padding above face
            return max(0, min(ideal_top, height - target_height))
    except Exception as e:
        print(f"[Crop] Face detection failed, using center crop: {e}")

    return (height - target_height) // 2


def crop_to_16_9(input_path, output_path):
    img = Image.open(input_path)
    width, height = img.size
    target_height = int(width * 9 / 16)

    if target_height > height:
        raise ValueError("Image is too short to crop to 16:9.")

    top = _smart_crop_top(img, height, target_height)
    img.crop((0, top, width, top + target_height)).save(output_path)
    print(f"✅ Cropped to 16:9 (top={top}).")
