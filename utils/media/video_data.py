from utils.core.config import DATA_PATH, UTILS_PATH
from utils.core.edit import open_ai_generation

import json
import random


_prompts: dict[str, str] = {}

def _load_prompts() -> dict[str, str]:
    if _prompts:
        return _prompts
    for name in ["title", "title_pick", "description", "tags"]:
        with open(f"{UTILS_PATH}/prompts/{name}.txt") as f:
            _prompts[name] = f.read()
    return _prompts


def _parse_titles(response: str) -> list[str]:
    titles = []
    for line in response.strip().splitlines():
        line = line.strip()
        if line and line[0].isdigit() and '.' in line:
            title = line.split('.', 1)[1].strip()
            if title:
                titles.append(title[:65])
    return titles


def _pick_best_title(titles: list[str]) -> str:
    prompts = _load_prompts()
    numbered = "\n".join(f"{i+1}. {t}" for i, t in enumerate(titles))
    pick_prompt = prompts["title_pick"].replace("{titles}", numbered)
    response = open_ai_generation(pick_prompt, model="gpt-5-mini", temperature=0)
    if response:
        try:
            idx = int(response.strip()) - 1
            if 0 <= idx < len(titles):
                return titles[idx]
        except ValueError:
            pass
    return titles[0]


def _generate_title(product_title, price=""):
    prompts = _load_prompts()
    title = f"{product_title} Review – Is It Good?"

    title_prompt = (
        prompts["title"]
        .replace("{product_name}", product_title)
        .replace("{price}", price or "N/A")
    )
    title_response = open_ai_generation(title_prompt, model="gpt-5-mini", temperature=0.7)
    if title_response:
        titles = _parse_titles(title_response)
        if titles:
            print(f"[Title] Candidates: {titles}")
            title = _pick_best_title(titles) if len(titles) > 1 else titles[0]

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
    print("product.simple_title:", product.simple_title)

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
