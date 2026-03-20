from utils.core.settings import BACKGROUND_LIMITS
from utils.core.edit import generate_uuid_name, open_ai_edit_img, open_ai_generation, crop_fit
from utils.core.config import UTILS_PATH

from serpapi import GoogleSearch
import json
import os
from dotenv import load_dotenv
import requests
from PIL import Image
from io import BytesIO




load_dotenv()

SERPAPI_API_KEY = os.getenv("SHEARS_SERPAPI_API_KEY")

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "Mozilla/5.0"})

with open(f"{UTILS_PATH}/prompts/image/remove_bg.txt") as f:
    _remove_bg_prompt = f.read()

with open(f"{UTILS_PATH}/prompts/image/cutout_check.txt") as f:
    _cutout_check_prompt = f.read()

def _get_google_images(query, num, HL = "en", GL = "us"):
    data = GoogleSearch({
        "engine": "google_images",
        "q": query,
        "api_key": SERPAPI_API_KEY,
        "num": min(num, 100),
        "safe": "active",
        "hl": HL, "gl": GL,
    }).get_dict()
    imgs = []
    for r in (data.get("images_results") or []):
        u = r.get("original") or r.get("thumbnail")
        if u and u not in imgs:
            imgs.append(u)
    return imgs[:num]

def _download_and_validate_image(url, out_dir, product_type: str = "", min_width=800):
    try:
        r = SESSION.get(url, timeout=25, stream=True)
        if r.status_code != 200:
            return None

        img = Image.open(BytesIO(r.content))
        img = img.convert("RGB")

        if img.width < min_width:
            return None

        uid = generate_uuid_name("img_")
        work_path = os.path.join(out_dir, uid + "_orig.jpg")
        cutout_path = os.path.join(out_dir, uid + "_cutout.png")
        final_path = os.path.join(out_dir, uid + ".png")

        os.makedirs(out_dir, exist_ok=True)
        img.save(work_path, "JPEG", quality=90)

        open_ai_edit_img(_remove_bg_prompt, [work_path], cutout_path)

        prompt = _cutout_check_prompt.replace("{product_type}", product_type or "product")
        result = open_ai_generation(
            prompt,
            model="gpt-4.1",
            temperature=0,
            images=[work_path, cutout_path],
        )
        verify_json = json.loads(result)
        if (not verify_json["pass"]) or verify_json["confidence"] < 0.7:
            os.remove(work_path)
            os.remove(cutout_path)
            return None

        crop_fit(cutout_path, final_path)
        os.remove(work_path)
        os.remove(cutout_path)

        return final_path

    except Exception as e:
        print(f"[media_fetcher] Image processing failed: {e}")
        return None

def fetch_images(title, short_title, max_images, *, download_path, product_type: str = ""):
    collected = []

    image_urls = _get_google_images(title, max_images*2)

    if len(image_urls) < max_images and short_title:
        image_urls += _get_google_images(short_title, max_images)

    for url in image_urls:
        path = _download_and_validate_image(url, download_path, product_type=product_type)

        if path:
            
            collected.append(path)

        if len(collected) >= max_images:
            break
    
    return collected
