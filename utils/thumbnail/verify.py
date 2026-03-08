from utils.core.models import get_yolo

import cv2
import numpy as np


def normalize_image(img):
    # None → invalid
    if img is None:
        return None

    # Already numpy (OpenCV / MoviePy)
    if isinstance(img, np.ndarray):
        return img

    # PIL Image → numpy
    try:
        return np.array(img)
    except Exception:
        return None

def too_dark(img, threshold=80):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return np.mean(gray) < threshold


def blurry(img, threshold=120):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return cv2.Laplacian(gray, cv2.CV_64F).var() < threshold


def too_zoomed(img, threshold=0.28):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 100, 200)

    h, w = edges.shape
    center = edges[
        int(h * 0.2):int(h * 0.8),
        int(w * 0.2):int(w * 0.8)
    ]

    edge_ratio = np.count_nonzero(center) / center.size
    return edge_ratio > threshold


def busy_background(img, threshold=0.08):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 80, 160)
    return (edges > 0).mean() > threshold


def human_hands(img, conf_threshold=0.4, area_threshold=0.25):
    """
    Reject only if a detected person is LARGE (likely real human).
    """
    yolo = get_yolo()
    if yolo is None:
        return False

    h, w = img.shape[:2]
    img_area = h * w

    results = yolo(img, verbose=False)[0]
    for box in results.boxes:
        if float(box.conf) < conf_threshold:
            continue

        label = results.names[int(box.cls)]
        if label != "person":
            continue

        x1, y1, x2, y2 = box.xyxy[0]
        box_area = (x2 - x1) * (y2 - y1)
        ratio = box_area / img_area

        # 👇 this is the key line
        if ratio > area_threshold:
            return True

    return False

def verify_image(img_path):
    if not isinstance(img_path, str):
        return False, "invalid_input_type"

    img = cv2.imread(img_path)

    if img is None:
        return False, "invalid_image"

    if too_dark(img):
        return False, "too_dark"

    if blurry(img):
        return False, "blurry"

    if too_zoomed(img):
        return False, "too_zoomed"

    if busy_background(img):
        return False, "busy_background"

    if human_hands(img):
        return False, "human_hands"

    return True, None


