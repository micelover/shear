from __future__ import annotations
from utils.core.edit import generate_uuid_name

import dataclasses
import json
import os
import random
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse, parse_qs
from dotenv import load_dotenv

try:
    from yt_dlp import YoutubeDL
    from yt_dlp.utils import DownloadError
except Exception as e:  # pragma: no cover
    raise RuntimeError(
        "yt-dlp is required. Install a pinned version in your environment."
    ) from e

load_dotenv()

# ---------------------------
# Public data structures
# ---------------------------

DownloadStatus = str  # "ok" | "degraded" | "retryable_failed" | "terminal_failed"
ErrorCategory = str   # see classify_error()


@dataclass(frozen=True)
class DownloadRequest:
    url: str
    job_id: str = "job"
    # Optional: limit output resolution (height). If None, use env/default.
    max_height: Optional[int] = None
    # If True, allow using cookies (if cookie file is configured).
    allow_cookies: bool = True
    # If True, attempt additional client fallback tiers.
    allow_fallbacks: bool = True
    # Optional: override output directory (ephemeral ok; usually /tmp/work/<job_id>)
    output_dir: Optional[str] = None


@dataclass(frozen=True)
class DownloadResult:
    status: DownloadStatus
    url: str
    video_id: Optional[str]
    title: Optional[str]
    filepath: Optional[str]
    ext: Optional[str]
    duration: Optional[float]
    extractor: Optional[str]
    requested_max_height: Optional[int]
    used_client: Optional[str]
    used_cookies: bool
    attempt_count: int
    error_category: Optional[ErrorCategory]
    error_message: Optional[str]
    debug: Dict[str, Any]


# ---------------------------
# Configuration helpers
# ---------------------------

def _env_bool(name: str, default: bool) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in {"1", "true", "t", "yes", "y", "on"}


def _env_int(name: str, default: int) -> int:
    v = os.getenv(name)
    if v is None:
        return default
    try:
        return int(v.strip())
    except ValueError:
        return default


def _now_ms() -> int:
    return int(time.time() * 1000)


def _redact_url(u: str) -> str:
    """
    Redact query parameters and fragments. Never log signed media URLs.
    """
    try:
        p = urlparse(u)
        safe = p._replace(query="", fragment="")
        return safe.geturl()
    except Exception:
        return "<redacted-url>"

def _extract_video_id(u: str) -> Optional[str]:
    """
    Best-effort video id extraction for logging/metadata only.
    """
    try:
        p = urlparse(u)
        if p.hostname and "youtu.be" in p.hostname:
            vid = p.path.strip("/").split("/")[0]
            return vid or None
        if p.hostname and "youtube.com" in p.hostname:
            qs = parse_qs(p.query)
            vid = qs.get("v", [None])[0]
            return vid
    except Exception:
        return None
    return None


def _has_binary(name: str) -> bool:
    return shutil.which(name) is not None


def _safe_log(level: str, msg: str, **fields: Any) -> None:
    """
    Structured JSON logging for Cloud Run.
    Fields should already be safe (no cookies, no signed URLs, no PO tokens).
    """
    record = {
        "level": level.upper(),
        "ts_ms": _now_ms(),
        "msg": msg,
        **fields,
    }
    print(json.dumps(record, ensure_ascii=False))


# ---------------------------
# Error classification
# ---------------------------

_RETRYABLE_PATTERNS = [
    r"\b429\b",
    r"Too Many Requests",
    r"\b5\d\d\b",
    r"HTTP Error 5\d\d",
    r"timed out",
    r"TLS",
    r"Temporary failure",
    r"Connection reset",
    r"EOF occurred",
]

_TERMINAL_PATTERNS = [
    r"\bDRM\b",
    r"encrypted",
    r"requires payment",
    r"members only",
    r"Private video",
    r"This video is unavailable",
    r"Video unavailable",
    r"Sign in to confirm your age",
    r"age-restricted",
    r"not available in your country",
]

_DEGRADE_PATTERNS = [
    r"signature",
    r"n challenge",
    r"Some .* formats have been skipped",
    r"missing a url",
    r"forcing SABR",
    r"\b403\b",
    r"HTTP Error 403",
    r"Forbidden",
    r"PO Token",
    r"pot",
]


def classify_error(message: str) -> ErrorCategory:
    """
    Classify errors into broad buckets:
    - retryable: transient network/rate-limits/5xx
    - degrade: extraction/format issues (try other clients, lower quality)
    - terminal: DRM, hard availability, private, strict age-gate, etc.
    - unknown: anything else
    """
    m = (message or "").strip()
    if not m:
        return "unknown"

    if any(re.search(p, m, re.IGNORECASE) for p in _TERMINAL_PATTERNS):
        return "terminal"
    if any(re.search(p, m, re.IGNORECASE) for p in _RETRYABLE_PATTERNS):
        return "retryable"
    if any(re.search(p, m, re.IGNORECASE) for p in _DEGRADE_PATTERNS):
        return "degrade"

    return "unknown"

# ---------------------------
# Core downloader
# ---------------------------

class YouTubeDownloader:
    def __init__(self) -> None:
        # Primary working roots (Cloud Run best practice: /tmp)
        self.work_root = os.getenv("YTDLP_WORK_ROOT", "/tmp/ytdlp_work")
        self.temp_root = os.getenv("YTDLP_TEMP_ROOT", "/tmp/ytdlp_tmp")

        # Cookies (mount from Secret Manager as a file; never bake into image)
        self.cookies_path = os.getenv("YTDLP_COOKIES_FILE", "").strip() or None

        # Retry policy
        self.max_attempts = _env_int("YTDLP_MAX_ATTEMPTS", 4)
        self.base_backoff_s = float(os.getenv("YTDLP_BASE_BACKOFF_S", "1.2"))
        self.max_backoff_s = float(os.getenv("YTDLP_MAX_BACKOFF_S", "12.0"))

        # Quality policy
        self.default_max_height = _env_int("YTDLP_MAX_HEIGHT", 1080)
        self.degraded_max_height = _env_int("YTDLP_DEGRADED_MAX_HEIGHT", 720)

        # Downloader behavior
        self.quiet = _env_bool("YTDLP_QUIET", True)
        self.no_warnings = _env_bool("YTDLP_NO_WARNINGS", False)
        self.socket_timeout = _env_int("YTDLP_SOCKET_TIMEOUT", 20)
        self.read_timeout = _env_int("YTDLP_READ_TIMEOUT", 20)

        # Fragments
        self.retries = _env_int("YTDLP_RETRIES", 2)
        self.fragment_retries = _env_int("YTDLP_FRAGMENT_RETRIES", 5)
        self.concurrent_fragments = _env_int("YTDLP_CONCURRENT_FRAGMENTS", 2)

        # Environment checks (log once)
        self._log_environment_health()

        # Ensure roots exist
        os.makedirs(self.work_root, exist_ok=True)
        os.makedirs(self.temp_root, exist_ok=True)

    def _parse_clients(self, s: str) -> List[str]:
        clients = [c.strip() for c in (s or "").split(",") if c.strip()]
        return clients or ["android", "ios", "web"]

    def _log_environment_health(self) -> None:
        has_ffmpeg = _has_binary("ffmpeg")
        has_deno = _has_binary("deno")
        # Node is optional; we don't assume it's supported/configured.
        _safe_log(
            "INFO",
            "downloader_environment",
            has_ffmpeg=has_ffmpeg,
            has_deno=has_deno,
            cookies_configured=bool(os.getenv("YTDLP_COOKIES_FILE", "").strip()),
        )

    def download(self, req: DownloadRequest) -> DownloadResult:
        url_safe = _redact_url(req.url)
        vid = _extract_video_id(req.url)

        job_dir = req.output_dir or os.path.join(self.work_root, req.job_id)
        temp_dir = os.path.join(self.temp_root, req.job_id)

        os.makedirs(job_dir, exist_ok=True)
        os.makedirs(temp_dir, exist_ok=True)

        requested_max_h = req.max_height if req.max_height is not None else self.default_max_height

        # Quality ladder (highest → lowest), never below 720
        quality_ladder = [
            h for h in [2160, 1440, 1080, 720]
            if h <= requested_max_h
        ]

        clients = ["android"]

        attempts = 0
        last_error = None

        for height in quality_ladder:
            for client in clients:
                attempts += 1

                _safe_log(
                    "INFO",
                    "download_attempt",
                    job_id=req.job_id,
                    url=url_safe,
                    video_id=vid,
                    client=client,
                    target_height=height,
                )

                try:
                    info, final_path = self._run_ytdlp(
                        url=req.url,
                        job_dir=job_dir,
                        temp_dir=temp_dir,
                        client=client,
                        max_height=height,
                        use_cookies=False,
                        job_id=req.job_id,
                    )

                    _safe_log(
                        "INFO",
                        "download_success",
                        job_id=req.job_id,
                        client=client,
                        height=height,
                        filepath=os.path.basename(final_path),
                    )

                    return DownloadResult(
                        status="ok",
                        url=url_safe,
                        video_id=info.get("id") if info else vid,
                        title=info.get("title") if info else None,
                        filepath=final_path,
                        ext=info.get("ext") if info else None,
                        duration=info.get("duration") if info else None,
                        extractor=info.get("extractor") if info else None,
                        requested_max_height=requested_max_h,
                        used_client=client,
                        used_cookies=False,
                        attempt_count=attempts,
                        error_category=None,
                        error_message=None,
                        debug={
                            "selected_height": height,
                        },
                    )

                except Exception as e:
                    last_error = str(e)[:2000]
                    _safe_log(
                        "WARN",
                        "download_failed",
                        job_id=req.job_id,
                        client=client,
                        height=height,
                        error=last_error,
                    )
                    continue

        # ❌ Nothing >=720p worked
        self._cleanup_job_dirs(temp_dir=temp_dir, job_dir=job_dir)

        return DownloadResult(
            status="terminal_failed",
            url=url_safe,
            video_id=vid,
            title=None,
            filepath=None,
            ext=None,
            duration=None,
            extractor=None,
            requested_max_height=requested_max_h,
            used_client=None,
            used_cookies=False,
            attempt_count=attempts,
            error_category="no_720p_available",
            error_message=last_error or "No format >=720p available",
            debug={},
        )
    
    def _get_video_dimensions(self, path: str) -> Optional[Tuple[int, int]]:
        try:
            cmd = [
                "ffprobe",
                "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height",
                "-of", "json",
                path,
            ]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
            )
            data = json.loads(result.stdout)
            stream = data["streams"][0]
            return stream["width"], stream["height"]
        except Exception:
            return None

    # ---------------------------
    # Internal helpers
    # ---------------------------

    def _sleep_backoff(self, try_index: int) -> None:
        # Exponential backoff with jitter
        base = self.base_backoff_s * (2 ** max(0, try_index - 1))
        sleep_s = min(self.max_backoff_s, base) * random.uniform(0.75, 1.25)
        time.sleep(sleep_s)

    def _cleanup_job_dirs(self, temp_dir: str, job_dir: str) -> None:
        """
        Aggressive cleanup for ephemeral Cloud Run storage.
        You may choose to keep job_dir if your caller needs it; here we remove it on failure.
        """
        keep_on_fail = _env_bool("YTDLP_KEEP_DIRS_ON_FAIL", False)
        if keep_on_fail:
            return
        for d in (temp_dir, job_dir):
            try:
                shutil.rmtree(d, ignore_errors=True)
            except Exception:
                pass

    # def _build_format_selector(self, height: int) -> str:
    #     return (
    #         f"bestvideo[height<={height}]+bestaudio/"
    #         f"best[height<={height}]/"
    # )

    def _build_format_selector(self, height: int) -> str:
        """
        FAST + ROBUST selector:
        - Prefer progressive MP4 (no DASH, no tokens)
        - Fall back aggressively
        - Never fail just because of resolution
        """
        return (
            # 1️⃣ Progressive MP4 (FASTEST, most reliable)
            f"best[ext=mp4][height<={height}]/"
            # 2️⃣ Any progressive format
            f"best[height<={height}]/"
            # 3️⃣ Absolute last resort
            "best"
        )
    
    def _probe_best_height(self, url: str, client: str) -> int:
        """
        Return the best available height for this URL using a specific YouTube client.
        Does NOT download.
        """
        ydl_opts: Dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "noprogress": True,
            "extractor_args": {"youtube": {"player_client": [client]}},
        }

        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        # Handle playlists / multi-video edge cases by grabbing first entry
        if isinstance(info, dict) and info.get("_type") == "playlist" and info.get("entries"):
            info = info["entries"][0]

        best = 0
        for f in (info.get("formats") or []):
            h = f.get("height")
            if isinstance(h, int) and h > best:
                best = h
        return best


    def _run_ytdlp(
        self,
        url: str,
        job_dir: str,
        temp_dir: str,
        client: str,
        max_height: int,
        use_cookies: bool,
        job_id: str,
    ) -> Tuple[Dict[str, Any], str]:
        """
        Runs yt-dlp and returns (info_dict, final_file_path).

        Important: never log raw "url" outputs; they can include signed media URLs.
        """
        # Output template: stable and safe (avoid special chars)
        outtmpl = os.path.join(job_dir, "%(id)s__%(title).150B.%(ext)s")

        # yt-dlp options
        ydl_opts: Dict[str, Any] = {
            "outtmpl": outtmpl,
            "paths": {"home": job_dir, "temp": temp_dir},
            "quiet": self.quiet,
            "no_warnings": self.no_warnings,
            "noprogress": True,
            "retries": self.retries,
            "fragment_retries": self.fragment_retries,
            "concurrent_fragment_downloads": self.concurrent_fragments,
            "socket_timeout": self.socket_timeout,
            "continuedl": True,
            "nopart": False,
            "overwrites": True,
            # Prefer mp4 container when merging if possible
            "merge_output_format": os.getenv("YTDLP_MERGE_FORMAT", "mp4"),
            # Ensure postprocessing doesn't keep intermediates
            "keepvideo": False,
            # Metadata extraction
            "skip_download": False,
            "format": self._build_format_selector(max_height),
        }

        # Cookies if configured and allowed
        if use_cookies and self.cookies_path:
            ydl_opts["cookiefile"] = self.cookies_path

        # YouTube client persona selection (Innertube)
        # Keep this flexible: user can set YTDLP_CLIENTS to adjust ladder.
        # yt-dlp's youtube extractor supports extractor_args; "player_client" is the standard knob.
        ydl_opts["extractor_args"] = {
            "youtube": {
                "player_client": [client],
            }
        }

        # Some deployments want a custom UA; keep configurable.
        ua = os.getenv("YTDLP_USER_AGENT", "").strip()
        if ua:
            ydl_opts["user_agent"] = ua

        # Optional: prefer IPv4 in some envs
        if _env_bool("YTDLP_FORCE_IPV4", False):
            ydl_opts["force_ipv4"] = True

        # Optional: enforce filename restrictions for portability
        if _env_bool("YTDLP_RESTRICT_FILENAMES", True):
            ydl_opts["restrictfilenames"] = True

        # Make sure temp/job dirs exist
        os.makedirs(job_dir, exist_ok=True)
        os.makedirs(temp_dir, exist_ok=True)

        # Run extraction + download
        try:
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
        except DownloadError as e:
            # Bubble up with a bounded message (avoid dumping internals)
            raise RuntimeError(f"yt-dlp DownloadError: {str(e)[:2000]}") from e
        except Exception as e:
            raise

        if not isinstance(info, dict):
            raise RuntimeError("yt-dlp returned unexpected info type.")

        # Determine final file path
        # yt-dlp usually stores it in _filename / requested_downloads
        final_path = info.get("_filename")
        if not final_path and "requested_downloads" in info and info["requested_downloads"]:
            final_path = info["requested_downloads"][0].get("filepath")

        if not final_path:
            # Try to find a produced media file in job_dir
            final_path = self._find_media_file(job_dir)

        if not final_path or not os.path.exists(final_path):
            raise RuntimeError("Download completed but output file not found.")

        return info, final_path

    def _find_media_file(self, job_dir: str) -> Optional[str]:
        """
        Best-effort scan for the newest media file in job_dir.
        Avoid returning .part files.
        """
        try:
            candidates = []
            for name in os.listdir(job_dir):
                if name.endswith(".part") or name.endswith(".ytdl"):
                    continue
                path = os.path.join(job_dir, name)
                if os.path.isfile(path):
                    candidates.append(path)
            if not candidates:
                return None
            candidates.sort(key=lambda p: os.path.getmtime(p), reverse=True)
            return candidates[0]
        except Exception:
            return None


# ---------------------------
# Convenience entrypoint
# ---------------------------

def download_youtube(url: str, job_id: str = "job", max_height: Optional[int] = None) -> DownloadResult:
    """
    Convenience function for simple use cases.
    """
    dl = YouTubeDownloader()
    req = DownloadRequest(url=url, job_id=job_id, max_height=max_height)
    return dl.download(req)
