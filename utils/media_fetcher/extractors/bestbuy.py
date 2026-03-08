import re
import json
import requests
from bs4 import BeautifulSoup

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
})




def extract_bestbuy_videos(bestbuy_url, timeout=8):
    """
    Attempts to extract direct MP4 demo videos from a Best Buy product page.
    Returns a list of MP4 URLs or Brightcove video IDs.
    """

    print(f"\n🔍 [BestBuy] Fetching page: {bestbuy_url}")

    try:
        r = SESSION.get(bestbuy_url, timeout=timeout)
        r.raise_for_status()
    except Exception as e:
        print(f"❌ [BestBuy] Request failed: {e}")
        return []

    print(f"✅ [BestBuy] Page fetched (status {r.status_code})")

    html = r.text
    soup = BeautifulSoup(html, "html.parser")

    found = set()

    # --------------------------------------------------
    # 1️⃣ <video> / <source> tags
    # --------------------------------------------------
    print("🔎 [BestBuy] Scanning <video> / <source> tags...")

    video_hits = 0
    for video in soup.find_all("video"):
        src = video.get("src")
        if src and src.endswith(".mp4"):
            found.add(src)
            video_hits += 1

        for source in video.find_all("source"):
            src = source.get("src")
            if src and src.endswith(".mp4"):
                found.add(src)
                video_hits += 1

    print(f"📦 [BestBuy] <video> tag hits: {video_hits}")

    # --------------------------------------------------
    # 2️⃣ Brightcove embeds
    # --------------------------------------------------
    print("🔎 [BestBuy] Scanning for Brightcove embeds...")

    brightcove_matches = re.findall(
        r'players\.brightcove\.net/([^/]+)/([^_]+)_default/index\.html\?videoId=([0-9]+)',
        html
    )

    print(f"📦 [BestBuy] Brightcove embeds found: {len(brightcove_matches)}")

    for account_id, player_id, video_id in brightcove_matches:
        found.add(str({
            "platform": "brightcove",
            "account_id": account_id,
            "player_id": player_id,
            "video_id": video_id
        }))

    # --------------------------------------------------
    # 3️⃣ JSON blobs in <script> tags
    # --------------------------------------------------
    print("🔎 [BestBuy] Scanning <script> tags for video data...")

    script_hits = 0
    mp4_hits = 0

    for script in soup.find_all("script"):
        text = script.string
        if not text:
            continue

        if "video" not in text.lower():
            continue

        script_hits += 1

        mp4s = re.findall(r'https?://[^"\']+\.mp4', text)
        for url in mp4s:
            found.add(url)
            mp4_hits += 1

        try:
            data = json.loads(text)
            _extract_mp4_from_dict(data, found)
        except Exception:
            pass

    print(f"📦 [BestBuy] Script blocks scanned: {script_hits}")
    print(f"📦 [BestBuy] MP4s found in scripts: {mp4_hits}")

    # --------------------------------------------------
    # Final cleanup
    # --------------------------------------------------
    print(f"✅ [BestBuy] Total unique video assets found: {len(found)}")

    return list(found)


def _extract_mp4_from_dict(obj, results):
    if isinstance(obj, dict):
        for v in obj.values():
            _extract_mp4_from_dict(v, results)
    elif isinstance(obj, list):
        for v in obj:
            _extract_mp4_from_dict(v, results)
    elif isinstance(obj, str):
        if obj.startswith("http") and obj.endswith(".mp4"):
            results.add(obj)
