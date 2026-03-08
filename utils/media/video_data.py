from utils.core.config import DIR_PATH, DATA_PATH, SOURCE_PATH, UTILS_PATH
from utils.core.edit import open_ai_generation

import os
import json
import random
from datetime import datetime
import os





with open(f'{UTILS_PATH}/prompts/title.txt', 'r') as file:
    orignial_title_prompt = file.read()

with open(f'{UTILS_PATH}/prompts/description.txt', 'r') as file:
    orignial_description_prompt = file.read()

with open(f'{UTILS_PATH}/prompts/tags.txt', 'r') as file:
    orignial_tags_prompt = file.read()

def _format_timestamp(seconds: float) -> str:
    total_seconds = int(seconds)

    hours = total_seconds // 3600
    total_seconds %= 3600

    minutes = total_seconds // 60
    seconds = total_seconds % 60

    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    else:
        return f"{minutes}:{seconds:02d}"
    
def _sanitize_text(text, max_len=95):
    return text.strip().replace("\n", " ")[:max_len]

def _generate_title(product_title):
    title = f"{product_title} Review – Is It Good?"

    title_prompt = (
        orignial_title_prompt
        .replace("{product_name}", product_title)
    )
    title_response = open_ai_generation(title_prompt, model="gpt-5-mini", temperature=0.25)
    if title_response:
        title = title_response.strip().replace("\n", " ")[:65]

    return title

def _generate_description(product):
    description_parts = []

    # Prepare prompt
    description_prompt = (
        orignial_description_prompt
        .replace("{product_name}", product.simple_title)
    )

    # AI-generated text
    description_response = open_ai_generation(
        description_prompt,
        model="gpt-5-mini",
        temperature=0.4
    )

    if description_response and isinstance(description_response, str):
        description_parts.append(description_response.strip()[:1250])

    description_parts.append("")  # blank line

    short_title = product.simple_title
    affiliate_link = product.affiliate_link
    description_parts.append(f"✅ {short_title}\n{affiliate_link}\n")

    description_parts.append("")  # blank line

    disclaimer = '''
► Disclaimer ◄  
PrimeChoice Picks is a participant in the Amazon Services LLC Associates Program.  
As an Amazon Associate, I earn from qualifying purchases at no additional cost to you.
    '''
    
    description_parts.append(disclaimer.strip())  

    return "\n".join(description_parts)

def _generate_tags(product_name):
    tags = [product_name]

    tags_prompt = orignial_tags_prompt.replace("{product}", product_name)
    try:
        tags_response = open_ai_generation(
            tags_prompt,
            model="gpt-5-mini",
            temperature=0.7,
        )
        tags_json = json.loads(tags_response)
        if isinstance(tags_json, dict) and "tags" in tags_json:
            tags = tags_json["tags"]
        elif isinstance(tags_json, list):
            tags = tags_json
        random.shuffle(tags)
    except Exception as e:
        print(f"[WARN] Failed to generate tags: {e}")

    return [t.strip().lower() for t in tags if 1 < len(t) < 50][:10]

def _create_pinned_comment():
    return "🔗 Product links: All items featured in this video are listed in the description."

def generate_data(product):
    current_date = datetime.now()
    year = current_date.year
    month = current_date.month
    day = current_date.day

    print("product.simple_title:", product.simple_title)

    title = _generate_title(product.simple_title)

    description = _generate_description(product)

    tags = _generate_tags(product.simple_title)

    print(f"Generated title: {title}")
    print(f"Generated description: {description}")
    print(f"Generated tags: {tags}")

    # pinned_comment = _create_pinned_comment()

    video_data = {
        "file": f"{DATA_PATH}/final.mp4",
        "title": title,
        "description": description,
        # "pinned_comment": pinned_comment,
        "tags": tags,
        "privacy_status": "unlisted"
    }

    return video_data
    # return 






