from utils.core.config import DATA_PATH, UTILS_PATH
from utils.thumbnail.images import get_images
from dotenv import load_dotenv
import base64
import os
import requests

load_dotenv()

_flux_prompt_template: str = ""



def _load_flux_prompt() -> str:
    global _flux_prompt_template
    if not _flux_prompt_template:
        with open(f"{UTILS_PATH}/prompts/image/flux_prompt.txt") as f:
            _flux_prompt_template = f.read()
    return _flux_prompt_template


def _generate_flux_prompt(product, product_type: str) -> str:
    return (
        _load_flux_prompt()
        .replace("{product_type}", product_type)
    )


def _flux_img2img(prompt: str, image_path: str, output_path: str) -> None:
    api_key = os.getenv("SHEARS_FLUX_API_KEY")

    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    image_url = f"data:image/png;base64,{b64}"

    response = requests.post(
        "https://fal.run/fal-ai/flux-2/klein/9b/edit/lora",
        headers={
            "Authorization": f"Key {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "prompt": prompt,
            "image_urls": [image_url],
            "image_size": {"width": 1280, "height": 720},
            "num_inference_steps": 8,
        },
        timeout=120,
    )
    response.raise_for_status()
    result = response.json()

    img_url = result["images"][0]["url"]
    img_response = requests.get(img_url, timeout=60)
    img_response.raise_for_status()

    with open(output_path, "wb") as f:
        f.write(img_response.content)



def create_flux_design(product, product_type: str) -> None:
    images = get_images(product.simple_title, product_type=product_type, fetch_count=8, num_images=2, workers=4)
    if not images:
        raise RuntimeError("No product images available for Flux thumbnail")

    reference_image = images[0]
    print(f"[Flux] Reference image: {reference_image}")

    flux_prompt = _generate_flux_prompt(product, product_type)
    print(f"[Flux] Prompt: {flux_prompt}")

    thumbnail_path = f"{DATA_PATH}/thumbnail.png"
    _flux_img2img(flux_prompt, reference_image, thumbnail_path)
    print(f"[Flux] Thumbnail generated: {thumbnail_path}")
