import os
import ssl
import time
import json

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from google.auth.transport.requests import Request

from utils.media.paths import get_youtube_token


CLIENT_SECRETS_FILE = "client_secrets.json"
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl"
]

_IS_CLOUD = os.getenv("CLOUD_ENV") == "google"
# On Cloud Run token.json is written to /tmp so the refresh survives the request
_TOKEN_WRITE_PATH = "/tmp/token.json" if _IS_CLOUD else "token.json"


def get_authenticated_service():
    creds = None

    try:
        token_str = get_youtube_token()
        data = json.loads(token_str)

        if isinstance(data, str):  # double-encoded fix
            data = json.loads(data)

        creds = Credentials.from_authorized_user_info(data, SCOPES)
        print(f"[auth] Token loaded — valid={creds.valid}, expired={creds.expired}, has_refresh={bool(creds.refresh_token)}")
    except Exception as e:
        print("❌ TOKEN LOAD ERROR:", e)
        creds = None

    # ✅ If valid, use it
    if creds and creds.valid:
        print("[auth] ✅ Token valid, building service")
        return build("youtube", "v3", credentials=creds)

    # ✅ Try refresh ONLY
    if creds and creds.refresh_token:
        try:
            print("[auth] Token expired, attempting refresh...")
            creds.refresh(Request())
            print("[auth] ✅ Token refreshed successfully")
            with open(_TOKEN_WRITE_PATH, "w") as f:
                f.write(creds.to_json())
            return build("youtube", "v3", credentials=creds)
        except Exception as e:
            # 🔴 DO NOT RE-AUTH AUTOMATICALLY
            raise RuntimeError(
                "OAuth refresh failed. Manual re-authorization required."
            ) from e

    # 🔴 OAuth flow is ALLOWED ONLY manually
    print(f"[auth] ❌ creds={creds}, valid={getattr(creds,'valid',None)}, expired={getattr(creds,'expired',None)}, refresh_token={bool(getattr(creds,'refresh_token',None))}")
    raise RuntimeError(
        "No valid OAuth token found. Run manual auth script."
    )

def upload_video(youtube, info: dict):
    body = dict(
        snippet=dict(
            title=info["title"],
            description=info["description"],
            tags=info.get("tags", []),
            # categoryId="22"  # People & Blogs
        ),
        status=dict(
            privacyStatus=info.get("privacy_status", "unlisted")
        )
    )

    media = MediaFileUpload(
        info["file"],
        chunksize=8 * 1024 * 1024,  # 8 MB chunks
        resumable=True
    )


    insert_request = youtube.videos().insert(
        part=",".join(body.keys()),
        body=body,
        media_body=media
    )
    
    response = None
    retries = 0
    MAX_RETRIES = 8

    while response is None:
        try:
            status, response = insert_request.next_chunk()

            if status:
                print(f"Uploading: {int(status.progress() * 100)}%")
                retries = 0  # reset retries on progress

        except (ssl.SSLError, ssl.SSLEOFError, HttpError) as e:
            retries += 1

            if retries > MAX_RETRIES:
                raise RuntimeError(
                    f"Upload failed after {MAX_RETRIES} retries"
                ) from e

            wait = min(2 ** retries, 30)
            print(
                f"⚠️ Upload error ({retries}/{MAX_RETRIES}): {e}. "
                f"Retrying in {wait}s..."
            )
            time.sleep(wait)
            continue

    if response and "id" in response:
        print(f"✅ Upload successful! Video ID: {response['id']}")
        return response["id"]

def set_thumbnail(youtube, video_id, thumbnail_path):
    youtube.thumbnails().set(
        videoId=video_id,
        media_body=MediaFileUpload(thumbnail_path)
    ).execute()
    print("✅ Thumbnail uploaded successfully!")

def ensure_commentable_privacy(youtube, video_id):
    video = youtube.videos().list(
        part="status",
        id=video_id
    ).execute()

    privacy = video["items"][0]["status"]["privacyStatus"]

    if privacy == "private":
        return False
    
    return True

# def add_pinned_comment(youtube, video_id: str, text: str):
#     """
#     Adds and pins a top-level comment on a YouTube video.
#     Must be authenticated as the channel owner.
#     """

#     comment_status = ensure_commentable_privacy(youtube, video_id)
#     if comment_status is False:
#         return False

#     # Step 1: Create comment
#     comment_response = youtube.commentThreads().insert(
#         part="snippet",
#         body={
#             "snippet": {
#                 "videoId": video_id,
#                 "topLevelComment": {
#                     "snippet": {
#                         "textOriginal": text
#                     }
#                 }
#             }
#         }
#     ).execute()

#     comment_id = comment_response["id"]

#     # Step 2: Pin comment (publish moderation status)
#     youtube.comments().setModerationStatus(
#         id=comment_id,
#         moderationStatus="published"
#     ).execute()

#     print("📌 Pinned comment added successfully!")
#     return comment_id