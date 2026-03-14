from serpapi import GoogleSearch
from dotenv import load_dotenv
import os



load_dotenv()

SERPAPI_API_KEY = os.getenv("SHEARS_SERPAPI_API_KEY")

def get_google_web_pages(query, num=20, hl="en", gl="us"):
    urls = []
    seen = set()
    page_size = 10  # Google max

    for start in range(0, num, page_size):
        print(f"🔍 Google search page (start={start}) for: {query}")

        search = GoogleSearch({
            "engine": "google",
            "q": query,
            "num": page_size,
            "start": start,
            "safe": "active",
            "hl": hl,
            "gl": gl,
            "api_key": SERPAPI_API_KEY,
        })

        data = search.get_dict()
        results = data.get("organic_results", []) or []

        if not results:
            print("⚠️ No more results")
            break

        for r in results:
            url = r.get("link")
            if url and url not in seen:
                seen.add(url)
                urls.append(url)

        if len(results) < page_size:
            break

        if len(urls) >= num:
            break

    print(f"✅ Collected {len(urls)} unique URLs")
    return urls[:num]
