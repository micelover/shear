import os
import inspect
from pathlib import Path



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