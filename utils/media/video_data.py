from utils.core.config import DATA_PATH, UTILS_PATH
from utils.core.edit import open_ai_generation

import json
import random


_prompts: dict[str, str] = {}

def _load_prompts() -> dict[str, str]:
    if _prompts:
        return _prompts
    for name in ["title_strategist", "title_copywriter", "description", "tags"]:
        with open(f"{UTILS_PATH}/prompts/{name}.txt") as f:
            _prompts[name] = f.read()
    return _prompts


def _generate_title(product_title, price=""):
    prompts = _load_prompts()
    title = f"{product_title} Review – Is It Good?"

    # Step 1: Strategist — pick angle
    strategist_response = open_ai_generation(
        prompts["title_strategist"]
        .replace("{product_name}", product_title)
        .replace("{price}", price or "N/A"),
        model="gpt-5-mini",
        temperature=0.7,
    )
    if not strategist_response:
        return title
    
    print("Strategist Response", strategist_response)

    # Step 2: Copywriter — write final title using angle
    copywriter_response = open_ai_generation(
        prompts["title_copywriter"].replace("{analyst_output}", strategist_response.strip()),
        model="gpt-5-mini",
        temperature=0.7,
    )
    if copywriter_response:
        title = copywriter_response.strip()[:65]

    return title


def _generate_description(product):
    prompts = _load_prompts()
    description_parts = []

    description_prompt = prompts["description"].replace("{product_name}", product.simple_title)

    description_response = open_ai_generation(
        description_prompt,
        model="gpt-5-mini",
        temperature=0.4
    )

    if description_response and isinstance(description_response, str):
        description_parts.append(description_response.strip()[:1250])

    description_parts.append("")  # blank line
    description_parts.append(f"✅ {product.simple_title}\n{product.affiliate_link}\n")
    description_parts.append("")  # blank line

    disclaimer = (
        "► Disclaimer ◄  \n"
        "PrimeChoice Picks is a participant in the Amazon Services LLC Associates Program.  \n"
        "As an Amazon Associate, I earn from qualifying purchases at no additional cost to you."
    )
    description_parts.append(disclaimer)

    return "\n".join(description_parts)


def _generate_tags(product_name):
    prompts = _load_prompts()
    tags = [product_name]

    tags_prompt = prompts["tags"].replace("{product}", product_name)
    try:
        tags_response = open_ai_generation(tags_prompt, model="gpt-5-mini", temperature=0.7)
        tags_json = json.loads(tags_response)
        if isinstance(tags_json, dict) and "tags" in tags_json:
            tags = tags_json["tags"]
        elif isinstance(tags_json, list):
            tags = tags_json
        random.shuffle(tags)
    except Exception as e:
        print(f"[WARN] Failed to generate tags: {e}")

    return [t.strip().lower() for t in tags if 1 < len(t) < 50][:10]


def generate_data(product):
    title = _generate_title(product.simple_title, product.price)
    description = _generate_description(product)
    tags = _generate_tags(product.simple_title)

    print(f"Generated title: {title}")
    print(f"Generated description: {description}")
    print(f"Generated tags: {tags}")

    return {
        "file": f"{DATA_PATH}/final.mp4",
        "title": title,
        "description": description,
        "tags": tags,
        "privacy_status": "public",
    }
