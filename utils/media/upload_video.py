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


def get_authenticated_service():
    creds = None

    try:
        token_content = get_youtube_token()
        if token_content:
            creds = Credentials.from_authorized_user_info(
                json.loads(token_content), SCOPES
            )
    except Exception:
        creds = None

    # ✅ If valid, use it
    if creds and creds.valid:
        return build("youtube", "v3", credentials=creds)

    # ✅ Try refresh ONLY
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())

            # Persist only when running locally (Cloud Run should use Secret Manager)
            if os.getenv("CLOUD_ENV") != "google":
                with open("token.json", "w") as f:
                    f.write(creds.to_json())

            return build("youtube", "v3", credentials=creds)
        except Exception as e:
            # 🔴 DO NOT RE-AUTH AUTOMATICALLY
            raise RuntimeError(
                "OAuth refresh failed. Manual re-authorization required. "
                "Run utils/media/auth_once.py to regenerate token.json with the same SCOPES as upload_video.py."
            ) from e

    # 🔴 OAuth flow is ALLOWED ONLY manually
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