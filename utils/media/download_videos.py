from __future__ import annotations
import asyncio
import concurrent.futures
import contextlib
import re
import shutil
import subprocess
import sys
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple, Type
from urllib.parse import unquote


# --- Optional imports guarded (handlers check availability) ---
with contextlib.suppress(Exception):
    import yt_dlp  # type: ignore
    from yt_dlp import YoutubeDL  # 👈 this line fixes the error


with contextlib.suppress(Exception):
    from pytube import YouTube  # type: ignore


# -----------------------------
# Minimal logger
# -----------------------------
class Log:
    def __init__(self, verbose: bool = True):
        self.verbose = verbose
    def info(self, msg: str): 
        if self.verbose: print(f"[INFO] {msg}")
    def warn(self, msg: str): print(f"[WARN] {msg}")
    def err(self, msg: str): print(f"[ERR ] {msg}")
    def success(self, msg: str): print(f"[OK  ] {msg}")


# -----------------------------
# Utilities
# -----------------------------
_SANE_NAME = re.compile(r"[^-\w.]+", re.UNICODE)

def safe_filename(name: str, maxlen: int = 120) -> str:
    name = unquote(name).strip().replace(" ", "_")
    name = _SANE_NAME.sub("", name)
    name = re.sub(r"_+", "_", name)
    return name[:maxlen] or "video"

def which_ffmpeg() -> Optional[str]:
    return shutil.which("ffmpeg") or shutil.which("avconv")

def has_module(mod_name: str) -> bool:
    try:
        __import__(mod_name)
        return True
    except Exception:
        return False

def backoff_delays(retries: int, base: float = 0.5, factor: float = 1.25, jitter: float = 0.25):
    delay = base
    for _ in range(retries):
        yield max(0.05, delay + random.uniform(-jitter, jitter))
        delay *= factor

def _youtube_fallback(url: str) -> str:
    """Builds an Invidious mirror URL for YouTube fallback."""
    video_id = re.search(r"v=([^&]+)", url)
    if not video_id:
        return url
    mirrors = [
        "https://yewtu.be",
        "https://inv.nadeko.net",
        "https://vid.puffyan.us",
        "https://invidious.flokinet.to",
        "https://invidious.nerdvpn.de",
    ]
    host = random.choice(mirrors)
    return f"{host}/latest_version?id={video_id.group(1)}&itag=22"

# def _tiktok_fallback(url: str) -> str:
#     """Tries alternative public TikTok mirrors if API blocks."""
#     mirrors = [
#         "https://vxtiktok.com",
#         "https://tikcdn.io",
#         "https://tnktok.cc",
#         "https://snaptik.app",
#     ]
#     for host in mirrors:
#         # Only rewrite official TikTok links
#         if "tiktok.com" in url:
#             return url.replace("https://www.tiktok.com", host).replace("https://tiktok.com", host)
#     return url


def _instagram_fallback(url: str) -> str:
    """Tries alternate Instagram CDN frontends or simplified URL forms."""
    mirrors = [
        "https://ddinstagram.com",
        "https://instasupersave.com",
        "https://imginn.com",
    ]
    for host in mirrors:
        if "instagram.com" in url:
            return url.replace("https://www.instagram.com", host).replace("https://instagram.com", host)
    return url

# -----------------------------
# Classification
# -----------------------------
@dataclass(frozen=True)
class PlatformSpec:
    key: str
    domains: Tuple[str, ...]
    pat: re.Pattern

PLATFORMS: Tuple[PlatformSpec, ...] = (
    PlatformSpec("youtube", ("youtube.com", "youtu.be"), re.compile(r"(youtube\.com|youtu\.be)", re.I)),
    PlatformSpec("tiktok", ("tiktok.com",), re.compile(r"tiktok\.com", re.I)),
    PlatformSpec("instagram", ("instagram.com",), re.compile(r"instagram\.com", re.I)),
    PlatformSpec("twitter", ("twitter.com", "x.com"), re.compile(r"(twitter\.com|x\.com)", re.I)),
    PlatformSpec("facebook", ("facebook.com", "fb.watch"), re.compile(r"(facebook\.com|fb\.watch)", re.I)),
    PlatformSpec("vimeo", ("vimeo.com",), re.compile(r"vimeo\.com", re.I)),
    PlatformSpec("reddit", ("reddit.com", "v.redd.it"), re.compile(r"(reddit\.com|v\.redd\.it)", re.I)),
    PlatformSpec("dailymotion", ("dailymotion.com", "dai.ly"), re.compile(r"(dailymotion\.com|dai\.ly)", re.I)),
    PlatformSpec("alibaba", ("alibaba.com", "aliexpress.com", "alicdn.com"), re.compile(r"(alibaba\.com|aliexpress\.com|alicdn\.com)", re.I)),
)

def classify_platform(url: str) -> str:
    for p in PLATFORMS:
        if p.pat.search(url):
            return p.key
    return "generic"


# -----------------------------
# Abstract Handler
# -----------------------------
class BaseHandler:
    NAME = "base"
    def __init__(self, logger: Log, output_dir: Path, prefer_mp4: bool = True, max_duration: Optional[int] = None):
        self.log = logger
        self.output_dir = output_dir
        self.prefer_mp4 = prefer_mp4
        self.max_duration = max_duration
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def primary(self, url: str) -> Optional[Path]: raise NotImplementedError
    def backup(self, url: str) -> Optional[Path]: return None

    # Core yt-dlp logic with smart quality + duration limit
    def _yt_dlp_video_only(self, url: str, outtmpl: Optional[str] = None, extra_opts: Optional[dict] = None) -> Optional[Path]:
        if not has_module("yt_dlp"):
            self.log.warn("yt-dlp not available.")
            return None

        quality_levels = [4320, 2160, 1440, 1080, 720, 480, 360]
        base_format = "bestvideo*[vcodec~='(av01|vp9|h265|h264)'][ext=mp4]"
        outtmpl = outtmpl or str(self.output_dir / "%(title).100s-%(id)s.%(ext)s")
        result_file = None
        errors = []

        def hook(d):
            if d.get("status") == "error":
                errors.append(str(d.get("exception") or "unknown error"))

        ydl_opts = {
            "outtmpl": outtmpl,
            "quiet": True,
            "noprogress": True,
            "noplaylist": True,
            "retries": 3,
            "fragment_retries": 3,
            "ignoreerrors": True,
            "no_color": True,
            "progress_hooks": [hook],
            "postprocessors": [],
            "geo_bypass": True,
            "continuedl": True,
            "concurrent_fragment_downloads": 5,
            "cachedir": False,
            "http_headers": {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
        }
        if extra_opts:
            ydl_opts.update(extra_opts)

        for height in quality_levels:
            format_selector = f"{base_format}[height<={height}]/{base_format}/bestvideo*[height<={height}]/best"
            ydl_opts["format"] = format_selector
            self.log.info(f"Trying quality ≤{height}p ...")

            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:  # type: ignore[name-defined]
                    # Get metadata first
                    info = ydl.extract_info(url, download=False)
                    if info is None:
                        continue
                    if "entries" in info and info["entries"]:
                        info = info["entries"][0]

                    duration = info.get("duration")
                    if duration and self.max_duration and duration > self.max_duration:
                        self.log.warn(f"Skipping {duration}s video (> {self.max_duration}s).")
                        return None

                    # Download now
                    info = ydl.extract_info(url, download=True)
                    if info is None:
                        continue
                    if "entries" in info and info["entries"]:
                        info = info["entries"][0]
                    result_file = Path(ydl.prepare_filename(info))
                    if result_file.exists():
                        self.log.success(f"Success at ≤{height}p.")
                        break
            except Exception as e:
                self.log.warn(f"yt-dlp attempt ≤{height}p failed: {e}")
                continue

        if not result_file or not result_file.exists():
            self.log.err("All quality levels failed.")
            return None

        # Strip audio
        if which_ffmpeg():
            try:
                stripped = result_file.with_name(result_file.stem + "_vo.mp4")
                cmd = [which_ffmpeg(), "-y", "-i", str(result_file), "-an", "-c:v", "copy", str(stripped)]
                cp = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                if cp.returncode == 0 and stripped.exists() and stripped.stat().st_size > 0:
                    result_file.unlink(missing_ok=True)
                    result_file = stripped
            except Exception as e:
                self.log.warn(f"FFmpeg strip-audio fallback skipped: {e}")

        return result_file

    def _direct_fetch(self, url: str) -> Optional[Path]:
        return self._yt_dlp_video_only(url)


# -----------------------------
# Concrete Handlers
# -----------------------------
class YouTubeHandler(BaseHandler):
    NAME = "youtube"

    def primary(self, url: str) -> Optional[Path]:
        """Try multiple YouTube clients, then Invidious fallback as last resort."""
        primary_clients = ["web", "tv", "ios"]
        backup_clients = ["web_safari", "tv_embedded", "web_embedded"]
        all_clients = [primary_clients, backup_clients]

        for clients in all_clients:
            self.log.info(f"Trying YouTube clients: {clients}")
            extra = {
                "extractor_args": {
                    "youtube": {
                        "player_client": clients,
                        "skip": [],  # allow DASH + HDR
                    }
                }
            }

            # Attempt yt-dlp with this client set
            path = self._yt_dlp_video_only(url, extra_opts=extra)
            if path and path.exists():
                return path

            self.log.warn(f"Client set {clients} failed, trying next...")

        # # 🔁 Try Invidious mirror fallback
        # self.log.warn("All YouTube clients failed. Trying Invidious fallback mirrors...")
        # mirror_url = _youtube_fallback(url)
        # if mirror_url != url:
        #     self.log.info(f"Using mirror: {mirror_url}")
        #     mirror_path = self._yt_dlp_video_only(mirror_url)
        #     if mirror_path and mirror_path.exists():
        #         self.log.success("YouTube Invidious mirror succeeded.")
        #         return mirror_path

        # 🪣 As absolute last resort, generic direct fetch
        self.log.warn("YouTube: falling back to generic fetch.")
        return self._direct_fetch(url)

    def backup(self, url: str) -> Optional[Path]:
        """Backup method using pytube, then fallback to direct fetch."""
        if not has_module("pytube"):
            self.log.warn("pytube not available; skipping YouTube backup.")
            return None

        try:
            yt = YouTube(url)
            streams = yt.streams.filter(only_video=True, file_extension="mp4").order_by("resolution").desc()
            s = streams.first() or yt.streams.filter(only_video=True).order_by("resolution").desc().first()
            if not s:
                return None

            title = safe_filename(yt.title or "youtube")
            out = self.output_dir / f"{title}-{yt.video_id}.{s.subtype}"
            s.download(output_path=str(self.output_dir), filename=out.name)

            if out.exists():
                self.log.success("pytube backup succeeded.")
                return out

        except Exception as e:
            self.log.warn(f"pytube backup failed: {e}")

        # As very last attempt
        self.log.warn("YouTube: using direct fallback.")
        return self._direct_fetch(url)

class TikTokHandler(BaseHandler):
    NAME = "tiktok"

    def primary(self, url: str) -> Optional[Path]:
        """Primary TikTok downloader using yt-dlp impersonation and fallback API trick."""
        self.log.info("TikTok: trying primary URL with impersonation…")

        ydl_opts = {
            "format": "bv*[ext=mp4]+ba/b",
            "outtmpl": str(self.output_dir / "%(title)s.%(ext)s"),
            "merge_output_format": "mp4",
            "noplaylist": True,
            "quiet": False,
            "ignoreerrors": True,
            "retries": 3,
            "fragment_retries": 3,
            "impersonate": "chrome:windows-10",
            "http_headers": {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
            },
        }

        try:
            # --- Attempt 1: normal impersonation
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if info:
                    path = Path(ydl.prepare_filename(info))
                    if path.exists():
                        self.log.success(f"TikTok download complete: {path.name}")
                        return path
        except Exception as e:
            self.log.warn(f"TikTok primary failed: {e}")

        # --- Attempt 2: direct API extraction fallback
        try:
            import requests, re
            self.log.info("Trying TikTok direct API fallback…")
            video_id = re.search(r"/video/(\d+)", url)
            if not video_id:
                return None
            api_url = f"https://www.tiktok.com/node/share/video/-/{video_id.group(1)}"
            headers = {"User-Agent": "Mozilla/5.0"}
            resp = requests.get(api_url, headers=headers, timeout=10)
            if resp.ok and '"downloadAddr"' in resp.text:
                m = re.search(r'"downloadAddr":"(https:[^"]+)"', resp.text)
                if m:
                    direct_url = m.group(1).replace("\\u0026", "&")
                    self.log.info("Direct TikTok media URL found, re-downloading via yt-dlp…")
                    with YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(direct_url, download=True)
                        if info:
                            path = Path(ydl.prepare_filename(info))
                            if path.exists():
                                return path
        except Exception as e:
            self.log.warn(f"TikTok API fallback failed: {e}")

        return None

class InstagramHandler(BaseHandler):
    NAME = "instagram"

    def primary(self, url: str) -> Optional[Path]:
        """Main Instagram downloader using yt-dlp, then mirror fallback."""
        # Use desktop UA and referer for better access to reels/posts
        extra = {
            "http_headers": {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/118.0.0.0 Safari/537.36"
                ),
                "Referer": "https://www.instagram.com/",
            }
        }

        # 1️⃣ Try official Instagram URL
        path = self._yt_dlp_video_only(url, extra_opts=extra)
        if path and path.exists():
            return path

        self.log.warn("Instagram: primary URL failed, trying mirrors...")

        # 2️⃣ Try Instagram mirrors (ddinstagram, imginn, etc.)
        # mirror = _instagram_fallback(url)
        # if mirror != url:
        #     mirror_path = self._yt_dlp_video_only(mirror, extra_opts=extra)
        #     if mirror_path and mirror_path.exists():
        #         self.log.success("Instagram: mirror succeeded.")
        #         return mirror_path

        return None

    def backup(self, url: str) -> Optional[Path]:
        """Last resort: try generic yt-dlp fetch."""
        self.log.warn("Instagram: using generic fallback.")
        return self._direct_fetch(url)
    
class AlibabaHandler(BaseHandler):
    NAME = "alibaba"

    def primary(self, url: str) -> Optional[Path]:
        """
        Primary downloader for Alibaba / AliExpress product or promo videos.
        Attempts yt-dlp extraction first, then tries direct CDN URLs and mirrors.
        """
        # Common headers to mimic real browser
        extra = {
            "http_headers": {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                "Referer": "https://www.alibaba.com/",
                "Accept-Language": "en-US,en;q=0.9",
            },
        }

        # 1️⃣ Try direct yt-dlp extraction (works for many Alibaba/AliExpress pages)
        self.log.info("Alibaba: trying yt-dlp direct extraction…")
        path = self._yt_dlp_video_only(url, extra_opts=extra)
        if path and path.exists():
            self.log.success("Alibaba: yt-dlp extraction succeeded.")
            return path

        # 2️⃣ Try parsing for direct .mp4 CDN (alicdn.com) URLs
        try:
            import requests
            self.log.info("Alibaba: scanning HTML for direct CDN URLs…")
            resp = requests.get(url, headers=extra["http_headers"], timeout=10)
            if resp.ok and ("alicdn.com" in resp.text or ".mp4" in resp.text):
                m = re.search(r'(https://[^\s"\\]+alicdn\.com[^\s"\\]+\.mp4)', resp.text)
                if m:
                    cdn_url = m.group(1)
                    self.log.info(f"Alibaba: found CDN URL: {cdn_url}")
                    cdn_path = self._yt_dlp_video_only(cdn_url, extra_opts=extra)
                    if cdn_path and cdn_path.exists():
                        self.log.success("Alibaba: CDN download succeeded.")
                        return cdn_path
        except Exception as e:
            self.log.warn(f"Alibaba CDN parsing failed: {e}")

        # 3️⃣ Try AliExpress mirrors (regional or mobile)
        mirrors = [
            "https://www.aliexpress.us",
            "https://m.aliexpress.com",
            "https://vi.aliexpress.com",
        ]
        for host in mirrors:
            if "aliexpress" not in url:
                continue
            mirror_url = re.sub(r"https://www\.aliexpress\.[a-z.]+", host, url)
            self.log.info(f"Alibaba: trying mirror {mirror_url}")
            mirror_path = self._yt_dlp_video_only(mirror_url, extra_opts=extra)
            if mirror_path and mirror_path.exists():
                self.log.success(f"Alibaba: mirror {host} succeeded.")
                return mirror_path

        # 4️⃣ Final fallback
        self.log.warn("Alibaba: using generic fallback.")
        return self._direct_fetch(url)

    def backup(self, url: str) -> Optional[Path]:
        """Backup: Try simplified URL or direct fetch."""
        self.log.info("Alibaba backup: trying simplified URL or direct fetch.")
        simple = url.split("?")[0]
        if simple != url:
            path = self._yt_dlp_video_only(simple)
            if path and path.exists():
                return path
        return self._direct_fetch(url)

class TwitterHandler(BaseHandler): NAME="twitter"
class FacebookHandler(BaseHandler): NAME="facebook"
class VimeoHandler(BaseHandler): NAME="vimeo"
class RedditHandler(BaseHandler): NAME="reddit"
class DailymotionHandler(BaseHandler): NAME="dailymotion"

class GenericHandler(BaseHandler):
    NAME = "generic"
    DIRECT_PAT = re.compile(r"\.(mp4|m4v|mov|m3u8|webm)(?:\?|$)", re.I)
    def primary(self, url: str) -> Optional[Path]:
        if self.DIRECT_PAT.search(url): return self._direct_fetch(url)
        return self._yt_dlp_video_only(url)
    def backup(self, url: str) -> Optional[Path]:
        return self._direct_fetch(url)


# -----------------------------
# Registry
# -----------------------------
HANDLERS: Dict[str, Type[BaseHandler]] = {
    "youtube": YouTubeHandler,
    "tiktok": TikTokHandler,
    "instagram": InstagramHandler,
    "alibaba": AlibabaHandler,
    "twitter": TwitterHandler,
    "facebook": FacebookHandler,
    "vimeo": VimeoHandler,
    "reddit": RedditHandler,
    "dailymotion": DailymotionHandler,
    "generic": GenericHandler,
}


# -----------------------------
# Core Functional Implementation
# -----------------------------
@dataclass
class DownloadConfig:
    output_dir: Path
    prefer_mp4: bool = True
    retries: int = 3
    timeout: int = 120
    verbose: bool = True
    yt_dlp_self_update: bool = False
    max_workers: int = 2
    max_duration: Optional[int] = None  # <-- added here


_executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)


def _maybe_self_update_ytdlp(log: Log):
    if not has_module("yt_dlp"):
        log.warn("yt-dlp not installed; skipping self-update.")
        return
    try:
        log.info("Updating yt-dlp…")
        subprocess.run([sys.executable, "-m", "pip", "install", "-U", "yt-dlp"],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    except Exception as e:
        log.warn(f"yt-dlp self-update failed: {e}")


def _attempt(handler: BaseHandler, url: str, retries: int, log: Log) -> Optional[Path]:
    for attempt, delay in enumerate(backoff_delays(retries), start=1):
        log.info(f"{handler.NAME}: primary attempt {attempt}/{retries}…")
        path = handler.primary(url)
        if path and path.exists():
            log.success(f"{handler.NAME} primary succeeded.")
            return path
        log.warn(f"{handler.NAME} primary failed. Backing off {delay:.2f}s.")
        time.sleep(delay)

    log.info(f"{handler.NAME}: trying backup method…")
    for attempt, delay in enumerate(backoff_delays(retries), start=1):
        log.info(f"{handler.NAME}: backup attempt {attempt}/{retries}…")
        path = handler.backup(url)
        if path and path.exists():
            log.success(f"{handler.NAME} backup succeeded.")
            return path
        log.warn(f"{handler.NAME} backup failed. Backing off {delay:.2f}s.")
        time.sleep(delay)
    return None


async def async_download_video(url: str, cfg: DownloadConfig, log: Log) -> Optional[Path]:
    if not isinstance(url, str) or not url.strip():
        log.err("Invalid URL.")
        return None
    url = url.strip()
    platform = classify_platform(url)
    log.info(f"Classified platform: {platform}")

    handler_cls = HANDLERS.get(platform)
    if handler_cls is None or handler_cls.primary == BaseHandler.primary:
        handler_cls = GenericHandler
    handler = handler_cls(logger=log, output_dir=cfg.output_dir, prefer_mp4=cfg.prefer_mp4, max_duration=cfg.max_duration)
    loop = asyncio.get_running_loop()
    path = await loop.run_in_executor(_executor, _attempt, handler, url, cfg.retries, log)
    if not path:
        log.err("All strategies exhausted.")
        return None

    if cfg.prefer_mp4 and path.suffix.lower() != ".mp4" and which_ffmpeg():
        log.info("Converting container to MP4 (video-only)…")
        target = path.with_suffix(".mp4")
        cmd = [which_ffmpeg(), "-y", "-i", str(path), "-an", "-c:v", "copy", str(target)]
        cp = await asyncio.get_event_loop().run_in_executor(
            _executor, lambda: subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        )
        if cp.returncode == 0 and target.exists() and target.stat().st_size > 0:
            with contextlib.suppress(Exception): path.unlink(missing_ok=True)
            path = target
    return path.resolve()


# -----------------------------
# Public Blocking API
# -----------------------------
def download_video(url: str,
                   output_dir: str | Path = "downloads",
                   prefer_mp4: bool = True,
                   retries: int = 3,
                   verbose: bool = True,
                   yt_dlp_self_update: bool = False,
                   max_duration: Optional[int] = None) -> Optional[str]:
    """Blocking convenience wrapper. Returns absolute file path or None."""
    print("URL:", url)
    cfg = DownloadConfig(
        output_dir=Path(output_dir),
        prefer_mp4=prefer_mp4,
        retries=retries,
        verbose=verbose,
        yt_dlp_self_update=yt_dlp_self_update,
        max_duration=max_duration
    )
    log = Log(verbose)
    cfg.output_dir.mkdir(parents=True, exist_ok=True)
    if cfg.yt_dlp_self_update:
        _maybe_self_update_ytdlp(log)

    if cfg.yt_dlp_self_update:
        _maybe_self_update_ytdlp(log)

    result = asyncio.run(async_download_video(url, cfg, log))
    if not result:
        log.err("Download failed — no result returned.")
        return None
    return result.as_posix()
