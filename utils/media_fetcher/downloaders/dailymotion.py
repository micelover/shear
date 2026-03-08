import os
import subprocess
from typing import Optional


def download_dailymotion(url: str, out_dir: str, filename: str) -> Optional[str]:
    print(f"[dailymotion] Downloading: {url}")

    os.makedirs(out_dir, exist_ok=True)

    if not filename.endswith(".mp4"):
        filename += ".mp4"

    out_path = os.path.join(out_dir, filename)

    cmd = [
        "yt-dlp",
        "--no-playlist",
        "--merge-output-format", "mp4",
        "-f", "bv*+ba/b",
        url,
        "-o", out_path,
    ]

    try:
        subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
            print(f"[dailymotion] ✅ Saved → {out_path}")
            return out_path

        print("[dailymotion] ❌ Empty file")
        return None

    except subprocess.CalledProcessError as e:
        print("[dailymotion] ❌ yt-dlp failed")
        print(e.stderr[:1000])
        return None

    except FileNotFoundError:
        print("[dailymotion] ❌ yt-dlp not installed")
        return None