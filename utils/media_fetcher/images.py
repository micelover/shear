from utils.core.settings import BACKGROUND_LIMITS
from utils.core.edit import generate_uuid_name

from serpapi import GoogleSearch
import os
from dotenv import load_dotenv
import requests
from PIL import Image
from io import BytesIO




load_dotenv()

SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY")

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "Mozilla/5.0"})

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

def _download_and_validate_image(url, out_dir, min_width=800):
    try:
        r = SESSION.get(url, timeout=25, stream=True)
        if r.status_code != 200:
            return None

        img = Image.open(BytesIO(r.content))
        img = img.convert("RGB")

        if img.width < min_width:
            return None

        filename = generate_uuid_name("img_") + ".jpg"
        path = os.path.join(out_dir, filename)

        os.makedirs(out_dir, exist_ok=True)
        img.save(path, "JPEG", quality=90)

        return path

    except Exception:
        return None

def fetch_images(title, short_title, max_images, *, download_path):
    collected = []

    image_urls = _get_google_images(title, max_images*2)

    if len(image_urls) < max_images and short_title:
        image_urls += _get_google_images(short_title, max_images)

    for url in image_urls:
        path = _download_and_validate_image(url, download_path)

        if path:
            
            collected.append(path)

        if len(collected) >= max_images:
            break
    
    return collected
