from serpapi import GoogleSearch
from dotenv import load_dotenv
import os



load_dotenv()

SERPAPI_API_KEY = os.getenv("SHEARS_SERPAPI_API_KEY")


def get_google_videos(query, num=20, hl="en", gl="us"):
    """Search Google Videos and return all video URLs (any domain)."""
    print(f"🔍 Searching Google Videos for: {query}")
    search = GoogleSearch({
        "engine": "google_videos",
        "q": query,
        "api_key": SERPAPI_API_KEY,
        "num": min(num, 20),
        
        "hl": hl,
        "gl": gl,
    })
    data = search.get_dict()
    results = data.get("video_results", []) or []
    urls = []

    for r in results:
        u = r.get("link") or r.get("source")
        if not u:
            continue
        urls.append(u)

    # De-dupe
    unique = list(dict.fromkeys(urls))
    print(f"✅ Found {len(unique)} video links")
    return unique[:num]
