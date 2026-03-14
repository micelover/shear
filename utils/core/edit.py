from utils.core.config import DEVICE

from pysrt import SubRipFile, SubRipItem, SubRipTime
import whisper
import uuid
import requests
from PIL import Image, ImageFont
import random
import numpy as np
import time
from openai import OpenAI
from groq import Groq
from dotenv import load_dotenv
from serpapi import GoogleSearch
import os
import base64
from pathlib import Path
import subprocess
import json
from pydub import AudioSegment
import io
import base64
import re





load_dotenv()
groq_api_key = os.getenv("SHEARS_GROQ_API_KEY")
openAI_api_key = os.getenv("SHEARS_OPENAI_API_KEY")

inworld_api_key = os.getenv("SHEARS_INWORLD_API_KEY")

serpapi_api_key = os.getenv("SHEARS_SERPAPI_API_KEY")

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "Mozilla/5.0"})

groq_client = Groq(
    api_key=groq_api_key
)
openAI_client = OpenAI(api_key=openAI_api_key)

def groq_generation(prompt, model, temperature):
    response = groq_client.chat.completions.create(
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
        model=model,
        temperature=temperature,
    )
    return response.choices[0].message.content
        
def open_ai_generation(
    prompt,
    model="gpt-4.1",
    temperature=0,
    images=None,
    max_retries=4,
    base_delay=2,
):
    """
    Unified GPT caller using Responses API.
    Automatically removes temperature if model doesn't support it.
    """

    for attempt in range(max_retries):
        try:
            content = []

            # Add text
            content.append({
                "type": "input_text",
                "text": prompt
            })

            # Add images (if any)
            if images:
                for img_path in images:
                    with open(img_path, "rb") as f:
                        img_bytes = f.read()

                    img_b64 = base64.b64encode(img_bytes).decode("utf-8")

                    mime_type = (
                        "image/jpeg"
                        if img_path.lower().endswith((".jpg", ".jpeg"))
                        else "image/png"
                    )

                    content.append({
                        "type": "input_image",
                        "image_url": f"data:{mime_type};base64,{img_b64}"
                    })

            # Build request payload
            request_payload = {
                "model": model,
                "input": [{
                    "role": "user",
                    "content": content
                }]
            }

            # Try adding temperature
            if temperature is not None:
                request_payload["temperature"] = temperature

            try:
                response = openAI_client.responses.create(**request_payload)
            except Exception as inner_error:
                # If temperature unsupported, retry without it
                if "temperature" in str(inner_error).lower():
                    request_payload.pop("temperature", None)
                    response = openAI_client.responses.create(**request_payload)
                else:
                    raise inner_error

            return response.output_text.strip()

        except Exception as e:
            print(f"⚠️ Error: {e}. Retrying {attempt + 1}/{max_retries}...")
            time.sleep(base_delay * (2 ** attempt))

    print("❌ All retries failed.")
    return None

def open_ai_tts(
    script: str,
    model: str = "gpt-4o-mini-tts",
    speaker: str = "cedar",
    save_path: str | None = None,
    instructions: str = ""
):
    response = openAI_client.audio.speech.create(
        model=model,
        voice=speaker,
        input=script,
        instructions=instructions,  
        response_format="mp3",
    )

    audio_bytes = response.read()

    if save_path:
        path = Path(save_path)
        path.write_bytes(audio_bytes)
        return str(path)

    return AudioSegment.from_file(io.BytesIO(audio_bytes), format="mp3")

def inworld_tts(text, output_path, id="Alex", model="inworld-tts-1.5-max", temperature=0.9):

    url = "https://api.inworld.ai/tts/v1/voice"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Basic {inworld_api_key}"
    }

    payload = {
    "text": text,
    "voiceId": id,
    "modelId": model,
    "timestampType": "WORD",
    # "temperature": temperature
    }

    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()
    result = response.json()
    audio_content = base64.b64decode(result['audioContent'])

    with open(output_path, "wb") as f:
        f.write(audio_content)

def google_images(query, num):
    data = GoogleSearch({
        "engine": "google_images",
        "q": query,
        "api_key": serpapi_api_key,
        "num": min(num, 100),
        "hl": "en", "gl": "us",
    }).get_dict()
    imgs = []
    for r in (data.get("images_results") or []):
        u = r.get("original") or r.get("thumbnail")
        if u and u not in imgs:
            imgs.append(u)
    return imgs[:num]

def google_shopping_images(query, num_images=10):
    params = {
        "engine": "google_shopping",
        "q": query,
        "google_domain": "google.com",
        "hl": "en",
        "gl": "us",
        "num": num_images,
        "api_key": serpapi_api_key,
    }

    search = GoogleSearch(params)
    results = search.get_dict()

    image_urls = []

    for item in results.get("shopping_results", [])[:num_images]:
        if "thumbnail" in item:
            image_urls.append(item["thumbnail"])

    return image_urls

def download_image(url, path):
    try:
        r = SESSION.get(url, timeout=25, allow_redirects=True, stream=True)
        if r.status_code != 200:
            return None
        
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        with open(path, "wb") as f:
            for chunk in r.iter_content(8192):
                if chunk:
                    f.write(chunk)
        return path
    except Exception as e:
        print(f"Error downloading {url}: {e}")
        return None     


def find_videos(folder: str, recursive: bool = False):
    valid_exts = (".mp4", ".mov", ".avi", ".mkv", ".flv", ".wmv", ".webm")
    video_paths = []

    if recursive:
        # Walk through subfolders
        for root, _, files in os.walk(folder):
            for f in files:
                if f.lower().endswith(valid_exts):
                    video_paths.append(os.path.join(root, f))
    else:
        # Just the top-level folder
        for f in os.listdir(folder):
            if f.lower().endswith(valid_exts):
                video_paths.append(os.path.join(folder, f))

    return video_paths

def find_images(folder: str, recursive: bool = False):
    valid_exts = (".jpg", ".jpeg", ".png")
    image_paths = []

    if recursive:
        # Walk through subfolders
        for root, _, files in os.walk(folder):
            for f in files:
                if f.lower().endswith(valid_exts):
                    image_paths.append(os.path.join(root, f))
    else:
        # Just the top-level folder
        for f in os.listdir(folder):
            if f.lower().endswith(valid_exts):
                image_paths.append(os.path.join(folder, f))

    return image_paths

# def open_ai_edit_img(prompt, input_paths, output_path, model="gpt-image-1"):
#     """
#     input_paths: list of image file paths
#     """

#     size_str = "1536x1024"

#     # Read all images into a list of bytes
#     image_bytes_list = []

#     for path in input_paths:
#         with open(path, "rb") as f:
#             image_bytes_list.append(f.read())

#     result = openAI_client.images.edit(
#         model=model,
#         prompt=prompt,
#         image=image_bytes_list,   # <-- LIST of images
#         size=size_str
#     )

#     image_base64 = result.data[0].b64_json
#     img_data = base64.b64decode(image_base64)

#     with open(output_path, "wb") as f:
#         f.write(img_data)

#     print("✅ Image generated with multiple references.")

def open_ai_edit_img(prompt, image_paths, output_path):
    image_files = []

    for path in image_paths:
        image_files.append(open(path, "rb"))

    result = openAI_client.images.edit(
        model="gpt-image-1",
        prompt=prompt,
        image=image_files,  # <-- list of FILE OBJECTS
        size="1536x1024"
    )

    # Save result
    image_base64 = result.data[0].b64_json
    with open(output_path, "wb") as f:
        f.write(base64.b64decode(image_base64))

    # Close files
    for f in image_files:
        f.close()

def robust_json_loads(response: str):
    if not response:
        raise ValueError("Empty response from model.")

    text = response.strip()

    # If already valid JSON, return immediately
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass  # Only attempt repairs if initial parse fails

    # Remove markdown fences
    text = re.sub(r"```json|```", "", text).strip()

    # If it does NOT start with [ or {, attempt extraction
    if not text.startswith("[") and not text.startswith("{"):
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            text = match.group()

    # Fix trailing commas
    text = re.sub(r",\s*([}\]])", r"\1", text)

    # If multiple objects without array wrapper, wrap them
    if text.startswith("{") and re.search(r"\},\s*\{", text):
        text = f"[{text}]"

    return json.loads(text)

def crop_fit(input_path, output_path, alpha_threshold=12, pad=0):
    """
    Crops so the first/last pixels with alpha >= alpha_threshold
    sit exactly on the borders. Optional 'pad' adds pixels back.
    """
    img = Image.open(input_path).convert("RGBA")
    a = np.array(img)[:, :, 3]  # alpha channel

    # Treat faint halo as transparent
    mask = a >= alpha_threshold

    # If nothing is left, just save original
    if not mask.any():
        img.save(output_path)
        return output_path

    # Find tight bounds where any non-transparent pixels exist
    ys = np.where(mask.any(axis=1))[0]
    xs = np.where(mask.any(axis=0))[0]

    top    = max(0, ys[0] - pad)
    bottom = min(img.height, ys[-1] + 1 + pad)  # +1 because crop is exclusive
    left   = max(0, xs[0] - pad)
    right  = min(img.width,  xs[-1] + 1 + pad)

    img.crop((left, top, right, bottom)).save(output_path)
    return output_path

def has_video_stream(path: str) -> bool:
    try:
        r = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-select_streams", "v",
                "-show_entries", "stream=index",
                "-of", "csv=p=0",
                path
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return bool(r.stdout.strip())
    except Exception:
        return False


def is_valid_media_file(path: str, delete_if_invalid: bool = True) -> bool:
    try:
        if not path or not isinstance(path, str):
            return False
        if not os.path.isfile(path):
            return False
        if os.path.getsize(path) < 50_000:
            if delete_if_invalid:
                os.remove(path)
            return False
        if not has_video_stream(path):
            if delete_if_invalid:
                os.remove(path)
            return False
        return True
    except Exception:
        try:
            if delete_if_invalid and path and os.path.exists(path):
                os.remove(path)
        except Exception:
            pass
        return False

def get_audio_duration(path):
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "json",
        path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(result.stdout)
    return float(data["format"]["duration"])

def get_video_duration(path):
    result = subprocess.run(
        [
            "ffprobe",
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "format=duration",
            "-of", "json",
            path,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return float(json.loads(result.stdout)["format"]["duration"])

def merge_segments(segments, max_gap=0.65, max_chars=150):
    merged = []
    current = None

    for seg in segments:
        text = seg["text"].strip()
        start = seg["start"]
        end = seg["end"]

        if current is None:
            current = {
                "start": start,
                "end": end,
                "text": text,
            }
            continue

        gap = start - current["end"]

        should_merge = (
            gap <= max_gap and
            not current["text"].endswith((".", "!", "?")) and
            len(current["text"]) + 1 + len(text) <= max_chars
        )

        if should_merge:
            # Merge text and extend end normally
            current["text"] += " " + text
            current["end"] = end
        else:
            # 🔧 FORCE GAPLESS: push current end to next start
            current["end"] = start
            merged.append(current)

            current = {
                "start": start,
                "end": end,
                "text": text,
            }

    if current:
        merged.append(current)

    return merged

def create_srt_from_transcription(result, return_words=True, return_sentences=False):
    if not return_words and not return_sentences:
        return None
    
    output = {}
    if return_words:
        words = SubRipFile()
        count = 1
        for i, segment in enumerate(result['segments']):
            for word in segment['words']:
                start_time = word['start']
                end_time = word['end']

                try:
                    if (len(words) >= 1):
                        previous_sub = words[-1]
                        previous_sub.end = SubRipTime(seconds=start_time)  
                except Exception as e:     
                    print("Error updating previous subtitle end time:", e)
                
                sub = SubRipItem(index=count,
                                start={"seconds": start_time},
                                end={"seconds": end_time},
                                text=word['word'])
                words.append(sub)
                count += 1
        output['words'] = words

    if return_sentences:
        sentences = SubRipFile()
        count = 1

        merged_segments = merge_segments(result["segments"])

        for seg in merged_segments:
            start_time = seg["start"]
            end_time = seg["end"]
            text = seg["text"]

            sub = SubRipItem(
                index=count,
                start=SubRipTime(seconds=start_time),
                end=SubRipTime(seconds=end_time),
                text=text
            )

            sentences.append(sub)
            count += 1

        output["sentences"] = sentences
    return output

def transcribe_audio(audio_file):
    model = whisper.load_model("base")
    result = model.transcribe(audio_file, word_timestamps=True)
    return result
    
def delete_folder_files(folder):
    for f in os.listdir(folder):
        file_path = os.path.join(folder, f)
        if os.path.isfile(file_path):
            os.remove(file_path)
    
def generate_uuid_name(prefix="item"):
    return f"{prefix}{uuid.uuid4().hex[:8]}"

def random_font(font_paths, size=95):
    random_font_path = random.choice(font_paths)
    font = ImageFont.truetype(random_font_path, size=size)
    return font


