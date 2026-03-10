from utils.core.config import DIR_PATH, DATA_PATH, SOURCE_PATH, UTILS_PATH
from utils.core.models import get_grounding_dino
from utils.thumbnail.render import crop_to_16_9
from utils.core.edit import open_ai_generation, open_ai_edit_img

import cv2
import numpy as np
import torch
from PIL import Image
import math





with open(f'{UTILS_PATH}/prompts/size_classify.txt', 'r') as file:
    orignial_size_classify_prompt = file.read()

with open(f'{UTILS_PATH}/prompts/image/ai_design_small.txt', 'r') as file:
    orignial_ai_design_small_prompt = file.read()

with open(f'{UTILS_PATH}/prompts/image/ai_design_big.txt', 'r') as file:
    orignial_ai_design_big_prompt = file.read()

def detect_product(image_path, prompt):
    model, processor = get_grounding_dino()

    image = Image.open(image_path).convert("RGB")

    inputs = processor(
        images=image,
        text=prompt,
        return_tensors="pt"
    ).to(model.device)

    with torch.no_grad():
        outputs = model(**inputs)

    results = processor.post_process_grounded_object_detection(
        outputs,
        inputs.input_ids,
        target_sizes=[image.size[::-1]]
    )[0]

    boxes = results["boxes"]
    scores = results["scores"]

    filtered_boxes = []

    for box, score in zip(boxes, scores):
        if score > 0.3:
            filtered_boxes.append(box)

    if len(filtered_boxes) == 0:
        return None

    best_box = None
    best_area = 0

    for box in filtered_boxes:
        x1, y1, x2, y2 = box.tolist()
        area = (x2 - x1) * (y2 - y1)

        if area > best_area:
            best_area = area
            best_box = (x1, y1, x2, y2)

    cx = int((best_box[0] + best_box[2]) / 2)
    cy = int((best_box[1] + best_box[3]) / 2)

    return (cx, cy), best_box

def label_img(box, thumbnail_path=f"{DATA_PATH}thumbnail.png"):
    img = cv2.imread(thumbnail_path)
    h, w = img.shape[:2]

    x1, y1, x2, y2 = map(int, box)

    def clamp(v, lo, hi):
        return max(lo, min(v, hi))

    # --- Arrow tip: top-left corner of product ---
    tip = np.array([x1 + 20, y1 + 20], dtype=np.float32)

    # --- Arrow tail: upper-left area of frame ---
    tail_anchor = np.array([
        clamp(int(w * 0.08), 40, x1 - 120),
        clamp(int(h * 0.12), 40, y1 - 80)
    ], dtype=np.float32)

    # --- Direction from tail to tip ---
    direction = tip - tail_anchor
    norm = np.linalg.norm(direction)
    if norm > 1e-6:
        direction /= norm
    perp = np.array([-direction[1], direction[0]], dtype=np.float32)

    # --- Arrowhead dimensions ---
    head_length = 40
    head_width = 44
    shaft_thickness = 18
    shaft_length = 80

    # head_base is where wings meet the shaft
    head_base = tip - direction * head_length

    # Shorter shaft: tail starts shaft_length back from head_base
    tail = head_base - direction * shaft_length

    # Arrowhead wing points
    left_pt  = head_base + perp * (head_width / 2)
    right_pt = head_base - perp * (head_width / 2)

    color = (255, 255, 255)

    SS = 4
    big = cv2.resize(img, (w * SS, h * SS), interpolation=cv2.INTER_CUBIC)

    def scale(pt):
        return (int(pt[0] * SS), int(pt[1] * SS))

    # --- Draw shaft (tail → head_base) with rounded cap ---
    cv2.line(big, scale(tail), scale(head_base), color, shaft_thickness * SS // 2, cv2.LINE_AA)
    cv2.circle(big, scale(tail), shaft_thickness * SS // 4, color, -1, cv2.LINE_AA)

    # --- Draw arrowhead as two angled lines meeting at tip ---
    wing_thickness = shaft_thickness * SS // 2
    cv2.line(big, scale(tip), scale(left_pt),  color, wing_thickness, cv2.LINE_AA)
    cv2.line(big, scale(tip), scale(right_pt), color, wing_thickness, cv2.LINE_AA)

    img = cv2.resize(big, (w, h), interpolation=cv2.INTER_AREA)

    # --- Text above the tail (no shadow) ---
    text = "I WAS WRONG"
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = max(w, h) / 580
    text_thickness = max(2, int(font_scale * 3.2))

    (text_w, text_h), _ = cv2.getTextSize(text, font, font_scale, text_thickness)

    text_x = clamp(int(tail[0]) - text_w // 2, 20, w - text_w - 20)
    text_y = clamp(int(tail[1]) - 40, text_h + 20, h - 20)

    cv2.putText(img, text, (text_x, text_y), font, font_scale,
                (255, 255, 255), text_thickness, cv2.LINE_AA)

    cv2.imwrite(thumbnail_path, img)
    return img

def create_ai_design1(product, images, product_type):
    product_title = product.title

    # Classify size
    size_prompt = orignial_size_classify_prompt.replace("{title}", product_title)
    classify = open_ai_generation(
        size_prompt,
        model="gpt-5-mini",
        temperature=0
    ).strip().upper()

    if classify not in ["SMALL", "LARGE"]:
        classify = "LARGE"

    # Choose correct design prompt
    thumbnail_path = f"{DATA_PATH}/thumbnail.png"

    headline = "I WAS WRONG"
    if classify == "SMALL":
        ai_prompt = orignial_ai_design_small_prompt.replace("{headline_text}", headline)
    else:
        ai_prompt = orignial_ai_design_big_prompt.replace("{headline_text}", headline)


    open_ai_edit_img(ai_prompt, images, thumbnail_path)
    crop_to_16_9(thumbnail_path, thumbnail_path)

    if classify == "SMALL":
        center, box = detect_product(
            thumbnail_path,
            product_type
        )
        
        label_img(box, thumbnail_path=thumbnail_path)
