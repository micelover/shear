import re
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
    "Accept-Language": "en-US,en;q=0.9",
})

VIDEO_EXTS = (".mp4", ".m3u8", ".mpd")

JS_URL_PATTERNS = [
    r'file\s*:\s*"([^"]+\.(?:mp4|m3u8|mpd))"',
    r'url\s*:\s*"([^"]+\.(?:mp4|m3u8|mpd))"',
    r'src\s*:\s*"([^"]+\.(?:mp4|m3u8|mpd))"',
    r'sources?\s*:\s*\[\s*{\s*file\s*:\s*"([^"]+)"',
    r'sources?\s*:\s*\[\s*{\s*src\s*:\s*"([^"]+)"',
    r'playlist\s*:\s*\[\s*{\s*file\s*:\s*"([^"]+)"',
    r'hls\s*:\s*"([^"]+\.m3u8)"',
    r'dash\s*:\s*"([^"]+\.mpd)"',
    r'video\s+src\s*=\s*"([^"]+)"',
]

BAD_HINTS = (
    "poster", "thumbnail", "sprite", "preview",
    "storyboard", ".jpg", ".png", ".webp"
)


# --------------------------------------------------
# Public entry
# --------------------------------------------------

def extract_generic_site_videos(url: str, timeout: int = 10, max_results: int = 5, verbose: bool = True) -> list[str]:
    def log(msg):
        if verbose:
            print(f"[generic] {msg}")

    log(f"Fetching page: {url}")

    try:
        r = SESSION.get(url, timeout=timeout)
        r.raise_for_status()
    except Exception as e:
        log(f"❌ Request failed: {e}")
        return []

    html = r.text
    soup = BeautifulSoup(html, "html.parser")

    found = []

    # --------------------------------------------------
    # 1️⃣ <video> / <source> tags
    # --------------------------------------------------
    for video in soup.find_all("video"):
        for attr in ("src", "data-src"):
            src = video.get(attr)
            if src and src.lower().endswith(VIDEO_EXTS):
                found.append(urljoin(url, src))

        for source in video.find_all("source"):
            src = source.get("src")
            if src and src.lower().endswith(VIDEO_EXTS):
                found.append(urljoin(url, src))

    # --------------------------------------------------
    # 2️⃣ Attributes (lazy-loaded frameworks)
    # --------------------------------------------------
    COMMON_ATTRS = (
        "src", "data-src", "data-video", "data-video-src",
        "data-url", "data-href", "href"
    )

    for tag in soup.find_all(True):
        for attr in COMMON_ATTRS:
            val = tag.get(attr)
            if isinstance(val, str) and val.lower().endswith(VIDEO_EXTS):
                found.append(urljoin(url, val))

    # --------------------------------------------------
    # 3️⃣ JSON-LD (schema.org VideoObject)
    # --------------------------------------------------
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string)
            _extract_from_obj(data, found)
        except Exception:
            pass

    # --------------------------------------------------
    # 4️⃣ Script regex scan (JS configs)
    # --------------------------------------------------
    for script in soup.find_all("script"):
        text = script.string or ""
        if not text:
            continue

        lowered = text.lower()
        if "video" not in lowered and "player" not in lowered and "stream" not in lowered:
            continue

        for pattern in JS_URL_PATTERNS:
            for m in re.finditer(pattern, text, re.IGNORECASE):
                found.append(urljoin(url, m.group(1)))

    # --------------------------------------------------
    # 5️⃣ Raw fallback scan (last resort)
    # --------------------------------------------------
    for m in re.finditer(r'https?://[^"\']+\.(?:mp4|m3u8|mpd)', html, re.IGNORECASE):
        found.append(m.group(0))

    # --------------------------------------------------
    # Cleanup
    # --------------------------------------------------
    clean = _postprocess(found, max_results)

    if clean:
        log(f"✅ Found {len(clean)} video URL(s)")
        for i, u in enumerate(clean, 1):
            log(f"   [{i}] {u}")
    else:
        log("ℹ️ No static video URLs found")

    return clean


# --------------------------------------------------
# Helpers
# --------------------------------------------------

def _extract_from_obj(obj, results):
    if isinstance(obj, dict):
        for v in obj.values():
            _extract_from_obj(v, results)
    elif isinstance(obj, list):
        for v in obj:
            _extract_from_obj(v, results)
    elif isinstance(obj, str):
        if obj.lower().endswith(VIDEO_EXTS):
            results.append(obj)


def _postprocess(urls: list[str], limit: int) -> list[str]:
    seen = set()
    cleaned = []

    for url in urls:
        if not isinstance(url, str):
            continue

        u = url.strip()
        lu = u.lower()

        if any(bad in lu for bad in BAD_HINTS):
            continue

        if not lu.startswith("http"):
            continue

        if u in seen:
            continue

        seen.add(u)
        cleaned.append(u)

        if len(cleaned) >= limit:
            break

    return cleaned
