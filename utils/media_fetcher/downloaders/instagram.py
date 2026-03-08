from __future__ import annotations

import os
import subprocess
from typing import Optional


def download_instagram(
    url: str,
    out_dir: str,
    filename: Optional[str] = None,
    cookies_file: Optional[str] = None,
) -> Optional[str]:
    print(f"[instagram] ▶ Starting download")
    print(f"[instagram] 🔗 URL: {url}")

    os.makedirs(out_dir, exist_ok=True)

    if not filename:
        return

    if not filename.endswith(".mp4"):
        filename += ".mp4"

    out_path = os.path.join(out_dir, filename)

    cmd = [
        "yt-dlp",
        "-f", "bv*+ba/b",
        "--merge-output-format", "mp4",
        "--no-playlist",
        url,
        "-o", out_path,
    ]

    if cookies_file:
        cmd.extend(["--cookies", cookies_file])
        print("[instagram] 🍪 Using cookies")

    print("[instagram] 🛠 Command:")
    print(" ".join(cmd))

    try:
        subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
            print("[instagram] ✅ Download successful")
            return out_path

        print("[instagram] ❌ File missing or empty")
        return None

    except subprocess.CalledProcessError as e:
        print("[instagram] ❌ yt-dlp failed")

        if e.stderr:
            print("[instagram] stderr:")
            print(e.stderr[:1500])

        return None

    except FileNotFoundError:
        print("[instagram] ❌ yt-dlp not installed")
        return None
