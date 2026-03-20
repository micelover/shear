from utils.core.config import DIR_PATH, DATA_PATH, SOURCE_PATH, UTILS_PATH
from utils.core.edit import generate_uuid_name, open_ai_generation, google_shopping_images, download_image, open_ai_edit_img, crop_fit
from utils.thumbnail.verify import verify_image

from PIL import Image, UnidentifiedImageError
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
import json





with open(f'{UTILS_PATH}/prompts/image/remove_bg.txt', 'r') as file:
    remove_bg_prompt = file.read()

with open(f'{UTILS_PATH}/prompts/image/cutout_check.txt', 'r') as file:
    cutout_check_prompt = file.read()

def process_single_image(url, product_type: str = ""):
    try:
        uid = generate_uuid_name("img_")

        work_path = f"{DATA_PATH}/thumbnail/process/{uid}.png"
        cutout_path = f"{DATA_PATH}/thumbnail/process/{uid}.png"
        final_path = f"{DATA_PATH}/thumbnail/{uid}.png"

        download_image(url, work_path)

        is_valid, reason = verify_image(work_path)
        if not is_valid:
            print(f"⚠️ Skipping invalid image: {reason}")
            os.remove(work_path)
            return None

        open_ai_edit_img(remove_bg_prompt, [work_path], cutout_path)

        prompt = cutout_check_prompt.replace("{product_type}", product_type or "product")
        result = open_ai_generation(prompt,
            model="gpt-4.1",
            temperature=0,
            images=[work_path, cutout_path],
        )
        verify_json = json.loads(result)

        if (not verify_json["pass"]) or verify_json["confidence"] < 0.7:
            return None

        crop_fit(cutout_path, final_path)
        os.remove(work_path)

        return final_path

    except Exception as e:
        print("ERROR processing", url, e)
        return None

def get_images(
    product_title: str,
    product_type: str = "",
    product_names: list | None = None,
    fetch_count: int = 16,
    num_images: int = 8,
    workers: int = 4,
):
    image_urls = []

    if product_names:
        for name in product_names:
            specific_urls = google_shopping_images(name, 1)
            if specific_urls:
                image_urls.append(specific_urls[0])
            if len(image_urls) >= num_images:
                break

    remaining = fetch_count - len(image_urls)
    if remaining > 0:
        generic_urls = google_shopping_images(product_title, remaining)
        image_urls.extend(generic_urls[:remaining])

    image_urls = image_urls[:fetch_count]

    images = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [
            executor.submit(process_single_image, url, product_type)
            for url in image_urls
        ]
        for future in as_completed(futures):
            result = future.result()
            if result:
                images.append(result)
            if len(images) >= num_images:
                break

    return images

def safe_load_images(paths, max_dim=1500):
    imgs = []
    for p in paths:
        try:
            # Try opening the image safely
            img = Image.open(p)
            img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)

            # Ensure RGBA
            if img.mode != "RGBA":
                img = img.convert("RGBA")

            imgs.append(img)

        except (UnidentifiedImageError, OSError, ValueError) as e:
            print(f"⚠️ Skipping bad image ({p}): {e}")
            continue

        except Exception as e:
            print(f"⚠️ Unexpected error loading img {p}: {e}")
            continue

    return imgs
