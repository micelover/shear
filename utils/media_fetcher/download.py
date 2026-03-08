from utils.core.edit import generate_uuid_name
from utils.media_fetcher.downloaders.youtube import DownloadResult, download_youtube
from utils.media_fetcher.downloaders.instagram import download_instagram
from utils.media_fetcher.downloaders.tiktok import download_tiktok
from utils.media_fetcher.downloaders.dailymotion import download_dailymotion
from utils.media_fetcher.downloaders.generic import download_generic

from urllib.parse import urlparse
import os 
import shutil



def _promote_to_media(result: DownloadResult, media_dir: str, final_name: str = None) -> str:
    """
    Move the downloaded file from its job sandbox into data/visual/media.
    Returns the new absolute path.
    """

    if result.status not in {"ok", "degraded"}:
        raise RuntimeError("Cannot promote failed download")

    src = result.filepath
    if not src or not os.path.exists(src):
        raise RuntimeError("Source file does not exist")
    
    if final_name is None:
        final_name = generate_uuid_name("vid_")

    os.makedirs(media_dir, exist_ok=True)

    ext = os.path.splitext(src)[1]
    dst = os.path.join(media_dir, final_name + ext)

    shutil.move(src, dst)

    # Remove the job directory (sandbox)
    try:
        shutil.rmtree(os.path.dirname(src))
    except Exception:
        pass

    return dst


def download_video(url: str, out_dir: str) -> str | None:
    host = urlparse(url).netloc.lower()
    filename = generate_uuid_name("vid_")

    if "youtube.com" in host or "youtu.be" in host:
        print("downlading youtube video")
        download_result = download_youtube(url)
        return _promote_to_media(download_result, out_dir, filename)
    
    elif "instagram.com" in host:
        return download_instagram(url, out_dir, filename)
    
    elif "tiktok.com" in host:
        return download_tiktok(url, out_dir, filename)
    
    elif "dailymotion.com" in url or "dai.ly" in url:
        return download_dailymotion(url, out_dir, filename)

    return download_generic(url, out_dir, filename)
