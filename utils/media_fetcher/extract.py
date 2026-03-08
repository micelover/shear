from utils.media_fetcher.extractors.amazon import extract_amazon_videos
from utils.media_fetcher.extractors.bestbuy import extract_bestbuy_videos
from utils.media_fetcher.extractors.generic import extract_generic_site_videos

from typing import List
from urllib.parse import urlparse



def classify_url(url: str) -> str:
    u = url.lower()

    if "amazon." in u:
        return "amazon"

    if "youtube.com" in u or "youtu.be" in u:
        return "youtube"
    
    if u.endswith(".mp4") or u.endswith(".m3u8"):
        return "direct"

    return "generic"


def extract_videos_from_url(url: str) -> List[str]:
    """
    Given a URL (page or video), return a list of video URLs.
    """
    kind = classify_url(url)

    if kind == "amazon":
        print("extracting amazon link")
        return extract_amazon_videos(url)
    
    if kind == "bestbuy":
        print("extracting bestbuy link")
        return extract_bestbuy_videos(url)
    
    if kind == "youtube":
        print("youtube link")
        return None

    if kind == "direct":
        print("direct link")
        return [url]

    print("generic link")
    return extract_generic_site_videos(url)


def extract_generic(url: str) -> List[str]:
    """
    Best-effort generic extractor for non-specialized pages.
    Should be conservative.
    """
    import requests
    import re

    try:
        r = requests.get(
            url,
            timeout=10,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        if not r.ok:
            return []

        html = r.text
        videos = set()

        # Direct MP4
        for m in re.findall(r'https://[^"\']+\.mp4', html):
            videos.add(m)

        # HLS streams
        for m in re.findall(r'https://[^"\']+\.m3u8', html):
            videos.add(m)

        return list(videos)

    except Exception:
        return []