import os
import subprocess
import requests


YTDLP_FORMAT = (
    "bestvideo[ext=mp4][height<=1080]/"
    "bestvideo[height<=1080]+bestaudio/"
    "best[ext=mp4][height<=1080]/"
    "best"
)

FFMPEG_HEADERS = (
    "Referer: https://www.amazon.com/\r\n"
    "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64)\r\n"
)

def download_generic(url: str, out_dir: str, filename: str) -> str | None:
    os.makedirs(out_dir, exist_ok=True)

    filename = filename.strip().replace(" ", "_") + ".mp4"
    out_path = os.path.join(out_dir, filename)

    # 1️⃣ Direct MP4 (fast path)
    if url.lower().endswith(".mp4"):
        path = _download_mp4(url, out_path)
        if path:
            return path

    # 2️⃣ HLS (.m3u8) → ffmpeg (preferred)
    if ".m3u8" in url.lower():
        path = _download_m3u8_ffmpeg(url, out_path)
        if path:
            return path

    # 3️⃣ Fallback → yt-dlp
    return _download_with_ytdlp(url, out_path)

def _download_mp4(url: str, out_path: str) -> str | None:
    try:
        r = requests.get(url, stream=True, timeout=25)
        if r.status_code != 200:
            return None

        with open(out_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        return out_path
    except Exception:
        return None

def _download_m3u8_ffmpeg(url: str, out_path: str) -> str | None:
    try:
        cmd = [
            "ffmpeg",
            "-y",
            "-headers",
            FFMPEG_HEADERS,
            "-protocol_whitelist",
            "file,http,https,tcp,tls,crypto",
            "-i",
            url,
            "-c",
            "copy",
            "-bsf:a",
            "aac_adtstoasc",
            "-movflags",
            "+faststart",
            out_path,
        ]

        subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        return out_path if os.path.exists(out_path) else None

    except Exception:
        return None

def _download_with_ytdlp(url: str, out_path: str) -> str | None:
    try:
        subprocess.run(
            [
                "yt-dlp",
                url,
                "-f",
                YTDLP_FORMAT,
                "--merge-output-format",
                "mp4",
                "--no-playlist",
                "--no-warnings",
                "-o",
                out_path,
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        return out_path if os.path.exists(out_path) else None

    except Exception:
        return None
