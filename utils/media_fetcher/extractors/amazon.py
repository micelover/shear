import re
import json
import requests
from bs4 import BeautifulSoup

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
    "Accept-Language": "en-US,en;q=0.9",
})


def extract_amazon_videos(
    amazon_url: str,
    timeout: int = 12,
    max_results: int = 5,
    verbose: bool = True,
) -> list[str]:
    """
    Best-effort Amazon product video extractor (static).
    Returns HLS (.m3u8) URLs only.
    """

    def log(msg):
        if verbose:
            print(f"[amazon-extract] {msg}")

    log(f"Fetching page: {amazon_url}")

    try:
        r = SESSION.get(amazon_url, timeout=timeout)
        r.raise_for_status()
    except Exception as e:
        log(f"❌ Request failed: {e}")
        return []

    html = r.text
    soup = BeautifulSoup(html, "html.parser")

    found = []

    # 1️⃣ Global .m3u8 scan
    m3u8_global = _find_m3u8_urls(html)
    if m3u8_global:
        log(f"✅ Found {len(m3u8_global)} .m3u8 URLs in raw HTML")
        found.extend(m3u8_global)
    else:
        log("⚠️ No .m3u8 URLs found in raw HTML")

    # 2️⃣ Scan <script> blocks
    script_hits = 0
    for i, script in enumerate(soup.find_all("script")):
        text = script.string or ""
        if not text:
            continue

        lowered = text.lower()
        if "video" not in lowered and "hls" not in lowered:
            continue

        script_hits += 1
        m3u8_script = _find_m3u8_urls(text)
        if m3u8_script:
            log(f"🎯 Script[{i}] yielded {len(m3u8_script)} .m3u8 URLs")
            found.extend(m3u8_script)

        if "videoassets" in lowered or '"videos"' in lowered:
            before = len(found)
            _try_parse_json(text, found)
            after = len(found)
            if after > before:
                log(f"🧩 Script[{i}] JSON parse added {after - before} URLs")

        if len(found) >= max_results:
            log("⏹️ Reached max_results during script scan")
            break

    if script_hits == 0:
        log("⚠️ No <script> blocks with video/hls keywords found")

    # 3️⃣ Filter + dedupe
    clean = _postprocess(found, max_results)

    if clean:
        log(f"✅ Final result: {len(clean)} usable Amazon video URLs")
        for idx, url in enumerate(clean, 1):
            log(f"   [{idx}] {url}")
    else:
        log("❌ No usable Amazon video URLs after filtering")

    return clean


# -----------------------------
# Helpers
# -----------------------------

_M3U8_RE = re.compile(
    r'(https?://m\.media-amazon\.com/images/S/[^"\')\s]+?\.m3u8[^"\')\s]*)',
    re.IGNORECASE
)

def _find_m3u8_urls(text: str) -> list[str]:
    return [m.group(1).strip(',[]{}') for m in _M3U8_RE.finditer(text)]


def _try_parse_json(script_text: str, results: list[str]) -> None:
    try:
        start = script_text.find("{")
        end = script_text.rfind("}") + 1
        if start == -1 or end <= start:
            return

        data = json.loads(script_text[start:end])
        _extract_from_obj(data, results)
    except Exception:
        return


def _extract_from_obj(obj, results: list[str]) -> None:
    if isinstance(obj, dict):
        for v in obj.values():
            _extract_from_obj(v, results)
    elif isinstance(obj, list):
        for v in obj:
            _extract_from_obj(v, results)
    elif isinstance(obj, str):
        if obj.startswith("http") and ".m3u8" in obj:
            results.append(obj)


def _postprocess(urls: list[str], limit: int) -> list[str]:
    seen = set()
    cleaned = []

    for url in urls:
        if url.startswith("blob:"):
            continue
        if "m.media-amazon.com" not in url:
            continue
        if "vse-vms-transcoding-artifact" not in url:
            continue
        if url in seen:
            continue

        seen.add(url)
        cleaned.append(url)

        if len(cleaned) >= limit:
            break

    return cleaned
