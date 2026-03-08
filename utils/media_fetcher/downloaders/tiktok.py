import os
import subprocess
from typing import Optional


def download_tiktok(url: str, out_dir: str, filename: str) -> Optional[str]:
    print(f"[tiktok] Downloading: {url}")

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
            print(f"[tiktok] ✅ Saved → {out_path}")
            return out_path

        print("[tiktok] ❌ File missing or empty")
        return None

    except subprocess.CalledProcessError as e:
        print("[tiktok] ❌ yt-dlp failed")
        print(e.stderr[:1000])
        return None

    except FileNotFoundError:
        print("[tiktok] ❌ yt-dlp not installed")
        return None