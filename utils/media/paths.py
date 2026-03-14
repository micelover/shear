import os
import inspect
from pathlib import Path
from urllib.request import Request, urlopen



def get_project_paths():
    # 1️⃣ Get the caller file path
    caller_file = Path(inspect.stack()[1].filename).resolve()

    # 2️⃣ Go one directory above that file
    base_dir = caller_file.parents[2]

    # 3️⃣ Cloud Run case (keep your logic)
    if os.environ.get("CLOUD_ENV") == "google":
        base_dir = Path("/app")
        data_path = Path("/tmp/app_data")  # writable
    else:
        data_path = base_dir / "data"

    # 4️⃣ Add subdirectories relative to that one-up directory
    source_path = base_dir / "source"
    utils_path = base_dir / "utils"

    # 5️⃣ Make sure they exist (only locally)
    if os.environ.get("CLOUD_ENV") != "google":
        for p in [data_path, source_path, utils_path]:
            p.mkdir(parents=True, exist_ok=True)

    # 6️⃣ Return absolute full paths
    return (
        str(base_dir.resolve()),
        str(data_path.resolve()),
        str(source_path.resolve()),
        str(utils_path.resolve()),
    )


def _get_gcp_project_id() -> str | None:
    env_project_id = (
        os.getenv("GOOGLE_CLOUD_PROJECT")
        or os.getenv("GCP_PROJECT")
        or os.getenv("GCLOUD_PROJECT")
    )
    if env_project_id:
        return env_project_id

    try:
        req = Request(
            "http://metadata.google.internal/computeMetadata/v1/project/project-id",
            headers={"Metadata-Flavor": "Google"},
        )
        with urlopen(req, timeout=2) as response:
            return response.read().decode("utf-8").strip()
    except Exception:
        return None


def get_youtube_cookies() -> str:
    """
    Return YouTube cookies content as a string.

    Runtime behavior:
      - Local (CLOUD_ENV != "google"): read .secrets/youtube_cookies.txt from disk.
      - Cloud Run (CLOUD_ENV == "google"): load secret `shears_youtube_cookies`
        from Google Cloud Secret Manager.

    Raises:
      RuntimeError: if cookies cannot be found or loaded.
    """
    is_cloud_run = os.getenv("CLOUD_ENV") == "google"

    if not is_cloud_run:
        project_root = Path(__file__).resolve().parents[2]
        cookies_path = project_root / ".secrets" / "youtube_cookies.txt"

        if not cookies_path.exists():
            raise RuntimeError(
                f"YouTube cookies file not found at {cookies_path}. "
                "Expected local cookies at .secrets/youtube_cookies.txt"
            )

        content = cookies_path.read_text(encoding="utf-8").strip()
        if not content:
            raise RuntimeError(
                f"YouTube cookies file is empty at {cookies_path}."
            )

        return content

    project_id = _get_gcp_project_id()
    if not project_id:
        raise RuntimeError(
            "Could not determine GCP project ID for Secret Manager lookup. "
            "Set GOOGLE_CLOUD_PROJECT (or GCP_PROJECT/GCLOUD_PROJECT)."
        )

    secret_name = f"projects/{project_id}/secrets/shears_youtube_cookies/versions/latest"

    try:
        try:
            from google.cloud import secretmanager
        except Exception as import_exc:
            raise RuntimeError(
                "google-cloud-secret-manager is not available in this environment. "
                "Install it before loading cookies on Cloud Run."
            ) from import_exc

        client = secretmanager.SecretManagerServiceClient()
        response = client.access_secret_version(request={"name": secret_name})
        content = response.payload.data.decode("utf-8").strip()
    except Exception as exc:
        raise RuntimeError(
            "Failed to load YouTube cookies from Secret Manager secret "
            f"`shears_youtube_cookies` in project `{project_id}`: {exc}"
        ) from exc

    if not content:
        raise RuntimeError(
            "Secret `shears_youtube_cookies` was retrieved but is empty."
        )

    return content


def get_youtube_token() -> str:
    """
    Return the YouTube OAuth token content as a string.

    Runtime behavior:
      - Local (CLOUD_ENV != "google"): read `token.json` from project root.
      - Cloud Run / GCP (CLOUD_ENV == "google"): load secret `shears_token`
        from Google Cloud Secret Manager.

    Raises:
      RuntimeError: if token cannot be found or loaded.
    """
    is_cloud_run = os.getenv("CLOUD_ENV") == "google"

    if not is_cloud_run:
        project_root = Path(__file__).resolve().parents[2]
        token_path = project_root / "token.json"

        if not token_path.exists():
            raise RuntimeError(
                f"OAuth token file not found at {token_path}. "
                "Expected local token.json in project root."
            )

        content = token_path.read_text(encoding="utf-8").strip()
        if not content:
            raise RuntimeError(
                f"Local token.json at {token_path} is empty."
            )

        return content

    # Cloud path: Secret Manager
    project_id = _get_gcp_project_id()
    if not project_id:
        raise RuntimeError(
            "Could not determine GCP project ID for Secret Manager lookup. "
            "Set GOOGLE_CLOUD_PROJECT (or GCP_PROJECT/GCLOUD_PROJECT)."
        )

    secret_name = f"projects/{project_id}/secrets/shears_token/versions/latest"

    try:
        try:
            from google.cloud import secretmanager
        except Exception as import_exc:
            raise RuntimeError(
                "google-cloud-secret-manager is not available in this environment. "
                "Install it before loading token on Cloud Run."
            ) from import_exc

        client = secretmanager.SecretManagerServiceClient()
        response = client.access_secret_version(request={"name": secret_name})
        content = response.payload.data.decode("utf-8").strip()
    except Exception as exc:
        raise RuntimeError(
            "Failed to load YouTube token from Secret Manager secret `shears_token` "
            f"in project `{project_id}`: {exc}"
        ) from exc

    if not content:
        raise RuntimeError(
            "Secret `shears_token` was retrieved but is empty."
        )

    return content