from utils.media.paths import get_project_paths

import torch


# Call once at startup
DIR_PATH, DATA_PATH, SOURCE_PATH, UTILS_PATH = get_project_paths()

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
