from utils.core.config import SOURCE_PATH, UTILS_PATH
import random







CATEGORY_POOL = [
    {"name": "3D Printers", "weight": 8},
    {"name": "Smart Home Devices", "weight": 10},
    {"name": "Budget Laptops", "weight": 6},
    {"name": "Portable Projectors", "weight": 9},
    {"name": "Mini PCs", "weight": 9},
    {"name": "Wireless Earbuds", "weight": 10},
    {"name": "Smartwatches", "weight": 8},
    {"name": "Gaming Mouse", "weight": 8},
    {"name": "Webcams", "weight": 7},
    {"name": "USB Microphones", "weight": 7},
    {"name": "Dash Cams", "weight": 9},
    {"name": "Smart Doorbells", "weight": 9},
    {"name": "Security Cameras", "weight": 9},
]

KEYWORD_AMOUNT = {"low": "3", "high": "5"}

SCRIPT_LENGTH = {"low": "400", "high": "500"}
# SCRIPT_LENGTH = {"low": "25", "high": "50"}

BACKGROUND_LIMITS = {
    "LIMIT_IMG": 10,
    "LIMIT_WEBPAGES": 10,

    "LIMIT_FETCH_VIDEOS": 10,
    "LIMIT_VIDEOS": 3,
    "YOUTUBE_LIMIT": 2,

    # "LIMIT_IMG": 5,
    # "LIMIT_WEBPAGES": 0,

    # "LIMIT_FETCH_VIDEOS": 0,
    # "LIMIT_VIDEOS": 0,
    # "YOUTUBE_LIMIT": 0,
}

PART_DURATION = {"low": "2", "high": "4"}


SFX_REGISTRY = {
    "price_appear": {
        "path": f"{SOURCE_PATH}/sfx/money.wav",
        "volume": 0.35
    }
}

THUMBNAIL_IMG_COUNT = {
    "design1": (8, 4),
    "design2": (8, 4),
    "ai_design": (4, 2),
}

