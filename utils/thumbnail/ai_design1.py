from utils.core.config import DIR_PATH, DATA_PATH, SOURCE_PATH, UTILS_PATH
from utils.core.models import get_grounding_dino
from utils.thumbnail.render import crop_to_16_9
from utils.core.edit import open_ai_generation, open_ai_edit_img

import cv2
import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFont
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

    # First, try to find boxes with high confidence (> 0.3)
    filtered_boxes = []

    for box, score in zip(boxes, scores):
        if score > 0.3:
            filtered_boxes.append(box)

    # If no high-confidence boxes, use all detections and pick the best one
    if len(filtered_boxes) == 0:
        if len(boxes) == 0:
            # No detections at all - return default closest fit (center of image)
            w, h = image.size
            cx = w // 2
            cy = h // 2
            best_box = (w // 4, h // 4, 3 * w // 4, 3 * h // 4)
            return (cx, cy), best_box
        # Use the box with the highest score
        best_score_idx = scores.argmax()
        filtered_boxes = [boxes[best_score_idx]]

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

def add_thumbnail_text(product_box, thumbnail_path=f"{DATA_PATH}/thumbnail.png"):
    # Load image with PIL
    img = Image.open(thumbnail_path).convert("RGB")
    w, h = img.size
    
    text_top = "I WAS"
    text_bottom = "WRONG"

    # Load Impact font
    font_path = f"{SOURCE_PATH}/font/Impact-Font/impact.ttf"
    # make text smaller relative to image dimensions
    font_size_top = int(max(w, h) / 12)
    font_size_bottom = int(max(w, h) / 11)

    font_top = ImageFont.truetype(font_path, font_size_top)
    font_bottom = ImageFont.truetype(font_path, font_size_bottom)

    x1, y1, x2, y2 = product_box

    margin_x = int(x1)
    margin_y = int(y2 + h * 0.03)

    # Create drawing context
    draw = ImageDraw.Draw(img)
    
    # Add outline effect for both text elements
    outline_width = 5
    
    # --- Top line (yellow with black outline) ---
    for adj_x in range(-outline_width, outline_width + 1):
        for adj_y in range(-outline_width, outline_width + 1):
            if adj_x != 0 or adj_y != 0:
                draw.text(
                    (margin_x + adj_x, margin_y + adj_y),
                    text_top,
                    font=font_top,
                    fill=(0, 0, 0)  # black outline
                )
    
    draw.text(
        (margin_x, margin_y),
        text_top,
        font=font_top,
        fill=(0, 255, 255)  # yellow
    )

    # --- Bottom line (white with black outline) ---
    bottom_y = margin_y + font_size_top + 20
    
    for adj_x in range(-outline_width, outline_width + 1):
        for adj_y in range(-outline_width, outline_width + 1):
            if adj_x != 0 or adj_y != 0:
                draw.text(
                    (margin_x + adj_x, bottom_y + adj_y),
                    text_bottom,
                    font=font_bottom,
                    fill=(0, 0, 0)  # black outline
                )
    
    draw.text(
        (margin_x, bottom_y),
        text_bottom,
        font=font_bottom,
        fill=(255, 255, 255)  # white
    )

    # Convert back to BGR for cv2 compatibility if needed
    img_cv2 = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    cv2.imwrite(thumbnail_path, img_cv2)
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

    # if classify == "SMALL":
    #     detection_result = detect_product(
    #         thumbnail_path,
    #         product_type
    #     )
        
    #     # Only label if detection was successful
    #     if detection_result is not None:
    #         center, box = detection_result
    #         add_thumbnail_text(box, thumbnail_path=thumbnail_path)
