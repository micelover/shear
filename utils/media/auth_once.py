"""
Run this script locally whenever the YouTube OAuth token needs to be refreshed.
It will:
  1. Open a browser for Google OAuth consent.
  2. Save the token to token.json locally.
  3. Upload the token to GCP Secret Manager as 'shears_token' so Cloud Run can use it.

Usage:
  python -m utils.media.auth_once
"""

import os
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl"
]

flow = InstalledAppFlow.from_client_secrets_file(
    "client_secrets.json", SCOPES
)

creds = flow.run_local_server(
    port=0,
    access_type="offline",
    prompt="consent"
)

if not creds.refresh_token:
    raise RuntimeError("No refresh token received — revoke app access in Google Account and retry.")

token_json = creds.to_json()

with open("token.json", "w") as f:
    f.write(token_json)

print("✅ token.json saved locally")

# ── Upload to Secret Manager via gcloud CLI ───────────────────────────────────
import subprocess
import shutil

GCP_PROJECT = "bots-automation-474007"
SECRET_ID   = "shears_token"

if not shutil.which("gcloud"):
    print("⚠️  gcloud CLI not found — upload token.json manually:")
    print(f"    gcloud secrets versions add {SECRET_ID} --data-file=token.json --project={GCP_PROJECT}")
else:
    # Create secret if it doesn't exist yet
    check = subprocess.run(
        ["gcloud", "secrets", "describe", SECRET_ID, f"--project={GCP_PROJECT}"],
        capture_output=True,
    )
    if check.returncode != 0:
        subprocess.run(
            ["gcloud", "secrets", "create", SECRET_ID,
             "--replication-policy=automatic", f"--project={GCP_PROJECT}"],
            check=True,
        )
        print(f"  Created secret '{SECRET_ID}'")

    result = subprocess.run(
        ["gcloud", "secrets", "versions", "add", SECRET_ID,
         "--data-file=token.json", f"--project={GCP_PROJECT}"],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        print(f"✅ Token uploaded to Secret Manager ({GCP_PROJECT}/{SECRET_ID})")
    else:
        print(f"⚠️  Secret Manager upload failed:\n{result.stderr}")
