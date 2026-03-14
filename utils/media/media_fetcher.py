from utils.core.settings import BACKGROUND_LIMITS
from utils.core.edit import is_valid_media_file
from utils.media_fetcher.images import fetch_images
from utils.media_fetcher.webpages import get_google_web_pages
from utils.media_fetcher.extract import extract_videos_from_url
from utils.media_fetcher.videos import get_google_videos
from utils.media_fetcher.download import download_video

from dotenv import load_dotenv
from urllib.parse import urlparse
import requests
import os



load_dotenv()

class MediaFetcher():

    def __init__(self):
        self.SERPAPI_API_KEY = os.getenv("SHEARS_SERPAPI_API_KEY")

        self.SESSION = requests.Session()
        self.SESSION.headers.update({"User-Agent": "Mozilla/5.0"})

        self.LIMIT_IMG = BACKGROUND_LIMITS["LIMIT_IMG"]

        self.LIMIT_WEBPAGES = BACKGROUND_LIMITS["LIMIT_WEBPAGES"]

        self.LIMIT_FETCH_VIDEOS = BACKGROUND_LIMITS["LIMIT_FETCH_VIDEOS"]
        self.LIMIT_VIDEOS = BACKGROUND_LIMITS["LIMIT_VIDEOS"]


    def _classify_video_url(self, url: str) -> dict:
        url_l = url.lower()
        host = urlparse(url_l).netloc

        # ---- PLATFORM ----
        if "youtube.com" in host or "youtu.be" in host:
            platform = "youtube"

        elif "instagram.com" in host:
            platform = "instagram"

        elif "tiktok.com" in host:
            platform = "tiktok"

        elif "media-amazon.com" in host or "amazonaws.com" in host:
            platform = "amazon"

        # High-quality retail / brand CDNs
        elif any(x in host for x in (
            "apple.com",
            "walmartimages.com",
            "bestbuy.com",
            "cloudinary.com",
            "cdn",
        )):
            platform = "cdn"

        # Direct file links (cleanest b-roll)
        elif url_l.endswith((".mp4", ".mov", ".webm")) or ".m3u8" in url_l:
            platform = "direct"

        else:
            platform = "generic"

        # ---- MEDIA TYPE ----
        if url_l.endswith((".mp4", ".mov", ".webm")):
            media_type = "mp4"
        elif ".m3u8" in url_l:
            media_type = "hls"
        else:
            media_type = "unknown"

        return {
            "url": url,
            "platform": platform,
            "media_type": media_type,
            "host": host,  # optional but VERY useful later
        }

    def fetch_and_classify_video_urls(self, product_title, short_product, amazon_url=None):
        seen_urls = set()

        webpages = []
        site_video_urls = []

        if amazon_url:
            webpages.append(amazon_url) 

        sites = get_google_web_pages(product_title, num=self.LIMIT_WEBPAGES)
        if sites:
            webpages += sites

        for site in webpages:
            vids = extract_videos_from_url(site)
            if not vids:
                continue

            site_video_urls += vids

        google_videos = get_google_videos(product_title, num=self.LIMIT_FETCH_VIDEOS)
        if not google_videos or len(google_videos)<self.LIMIT_FETCH_VIDEOS:
            print(f"Fetched {len(google_videos)}/{self.LIMIT_FETCH_VIDEOS}, Trying: {short_product}")
            google_videos += get_google_videos(short_product, num=self.LIMIT_FETCH_VIDEOS)
        classified = {}

        for url in [*site_video_urls, *google_videos]:
            if url in seen_urls:
                continue
            vid_info = self._classify_video_url(url)
            platform = vid_info["platform"]
            url = vid_info["url"]

            classified.setdefault(platform, []).append(url)
            seen_urls.add(url)
                  
        return classified

    def _download_classified_videos(self, classified, out_dir):
        downloaded = []
        used = set()

        def try_download(url):
            # if url.endswith(".m3u8"):
            #     print(f"[download] ⏭️ Skipping HLS playlist: {url}")
            #     used.add(url)
            #     return False

            if url in used:
                return False
            if len(downloaded) >= self.LIMIT_VIDEOS:
                return False

            try:
                path = download_video(url, out_dir)

                if not is_valid_media_file(path, delete_if_invalid=True):
                    print(f"[download] ⚠️ Invalid file for URL: {url}")
                    used.add(url)
                    return False

                used.add(url)
                downloaded.append(path)
                return True

            except Exception as e:
                print(f"[download] ❌ Failed: {url} | {e}")
                used.add(url)
                return False
            
        if len(downloaded) >= self.LIMIT_VIDEOS:
            return downloaded

        for url in classified.get("amazon", []):
            if len(downloaded) >= self.LIMIT_VIDEOS:
                return downloaded
            try_download(url)

        for url in classified.get("cdn", []):
            if len(downloaded) >= self.LIMIT_VIDEOS:
                return downloaded
            try_download(url)

        for platform, urls in classified.items():
            if platform in {"youtube", "amazon", "cdn"}:
                continue
            for url in urls:
                if len(downloaded) >= self.LIMIT_VIDEOS:
                    return downloaded
                try_download(url)

        for url in classified.get("youtube", []):
            if len(downloaded) >= self.LIMIT_VIDEOS:
                return downloaded
            try_download(url)


        return downloaded

    def fetch_for_product(self, product, *, media_dir):
        product_title = product.title
        simple_title = product.simple_title
        amazon_url = product.url

        image_paths = fetch_images(product_title, simple_title, self.LIMIT_IMG, download_path=media_dir)

        classified_urls = self.fetch_and_classify_video_urls(product_title, simple_title, amazon_url)
        print("all urls:", classified_urls)

        video_paths = self._download_classified_videos(classified_urls, media_dir)

        return image_paths, video_paths

