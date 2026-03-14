from utils.core.config import DIR_PATH, DATA_PATH, SOURCE_PATH, UTILS_PATH, DEVICE
from utils.core.models import get_clip

from moviepy import (
    VideoFileClip, CompositeVideoClip
)
import random
import os
from PIL import Image            
import torch                       
from transformers import CLIPProcessor, CLIPModel
import gc
import numpy as np

from utils.media_fetcher import videos




VIDEO_DURATIONS = {}  # cache outside

COARSE_CACHE = {}  # (path, keyword_id) -> [(score, t), ...]

TEXT_CACHE = {}

def get_text_features(keywords):
    clip_model, clip_processor = get_clip()

    key = tuple(keywords)
    if key in TEXT_CACHE:
        return TEXT_CACHE[key]

    inputs = clip_processor(
        text=keywords,
        return_tensors="pt",
        padding=True
    )
    inputs = {k: v.to(DEVICE) for k, v in inputs.items()}

    with torch.no_grad():
        text_features = clip_model.get_text_features(**inputs)
        text_features = text_features / text_features.norm(dim=-1, keepdim=True)

    TEXT_CACHE[key] = text_features
    return text_features

def get_duration(path):
    if path not in VIDEO_DURATIONS:
        try:
            vid = VideoFileClip(path)
            VIDEO_DURATIONS[path] = vid.duration
            vid.close()
        except Exception:
            VIDEO_DURATIONS[path] = None
    return VIDEO_DURATIONS[path]

def overlaps(a, b, margin=0.5):
    """
    Returns True if time windows a and b overlap (with margin in seconds).
    """
    return not (a[1] + margin < b[0] or b[1] + margin < a[0])

def clear_memory():
    torch.cuda.empty_cache()
    gc.collect()

def free_intervals(video_duration, used, clip_len):
    if not used:
        return [(0.0, video_duration)]

    used = sorted(used)
    free = []
    prev_end = 0.0

    for s, e in used:
        if s - prev_end >= clip_len:
            free.append((prev_end, s))
        prev_end = max(prev_end, e)

    if video_duration - prev_end >= clip_len:
        free.append((prev_end, video_duration))

    return free

def sample_start_from_free(free, duration):
    valid = []
    for s, e in free:
        if e - s >= duration:
            valid.append((s, e - duration))

    if not valid:
        return None

    s, e = random.choice(valid)
    return random.uniform(s, e)

def sample_frames(vid, start, duration, n=3):

    frames = []
    segment = duration / n

    for i in range(n):
        lo = start + i * segment
        hi = start + (i + 1) * segment
        t = random.uniform(lo, hi)
        frames.append(vid.get_frame(t))

    return frames
    
def clip_score_frame(frame, keywords):
    clip_model, clip_processor = get_clip()

    text_features = get_text_features(keywords)

    image = Image.fromarray(frame)
    inputs = clip_processor(images=image, return_tensors="pt")
    inputs = {k: v.to(DEVICE) for k, v in inputs.items()}

    with torch.no_grad():
        image_features = clip_model.get_image_features(**inputs)
        image_features = image_features / image_features.norm(dim=-1, keepdim=True)
        logits = image_features @ text_features.T
        return logits.max().item()

def score_window(vid, start, duration, keywords, n_frames=3):
    clip_model, clip_processor = get_clip()
    frames = sample_frames(vid, start, duration, n_frames)

    text_features = get_text_features(keywords)

    images = [Image.fromarray(f) for f in frames]
    inputs = clip_processor(images=images, return_tensors="pt")
    inputs = {k: v.to(DEVICE) for k, v in inputs.items()}
    with torch.no_grad():
        image_features = clip_model.get_image_features(**inputs)
        image_features = image_features / image_features.norm(dim=-1, keepdim=True)
        logits = image_features @ text_features.T
        return logits.max(dim=1).values.mean().item()

def keyword_id(keywords):
    return tuple(keywords)

def coarse_step_for_duration(dur):
    if dur is None:
        return 8  # safe default

    if dur > 1200:   # > 20 min
        return 20
    if dur > 600:    # > 10 min
        return 16
    if dur > 300:    # > 5 min
        return 10
    return 6

def coarse_scan(video_path, vid, keywords, top_k=3):
    key = (video_path, keyword_id(keywords))
    if key in COARSE_CACHE:
        return COARSE_CACHE[key]

    dur = get_duration(video_path)
    if dur is None:
        return []

    step = coarse_step_for_duration(dur)

    hits = []

    t = 0.0
    while t < dur:
        try:
            frame = vid.get_frame(t)
            score = clip_score_frame(frame, keywords)
            hits.append((score, t))
            hits = sorted(hits, reverse=True)[:top_k]

            # early exit once we have confident hits
            if len(hits) >= top_k and hits[-1][0] > 20:
                break
        except Exception:
            pass

        t += step


    hits = sorted(hits, reverse=True)[:top_k]
    COARSE_CACHE[key] = hits
    return hits

def refine_regions(video_path, coarse_hits, duration, radius=4):
    vid_duration = get_duration(video_path)
    regions = []

    for _, t in coarse_hits:
        lo = max(0.0, t - radius)
        hi = min(vid_duration - duration, t + radius)
        if hi > lo:
            regions.append((lo, hi))

    # merge overlaps
    regions.sort()
    merged = []
    for r in regions:
        if not merged or merged[-1][1] < r[0]:
            merged.append(list(r))
        else:
            merged[-1][1] = max(merged[-1][1], r[1])

    return [tuple(r) for r in merged]

def overlaps_existing(path, start, end, USED_WINDOWS):
    if path not in USED_WINDOWS:
        return False

    for used_start, used_end in USED_WINDOWS[path]:
        # Overlap condition
        if not (end <= used_start or start >= used_end):
            return True

    return False

def choose_clip_intro(
    videos,
    duration,
    keywords,
    max_tries=5,
    threshold=0.22,
):
    best = None
    best_score = -1

    for i in range(max_tries):
        path = random.choice(videos)

        vid_duration = get_duration(path)
        if vid_duration is None or vid_duration < duration:
            continue

        vid = VideoFileClip(path)
        try:
            start = random.uniform(0, vid_duration - duration)
            end = start + duration

            score = score_window(vid, start, duration, keywords)
        finally:
            vid.close()

        if score > best_score:
            best_score = score
            best = (path, start, end)

        if score >= threshold:
            break

    if best:
        path, start, end = best
        return best
    return None

def choose_clip_body(
    videos,
    duration,
    keywords,
    USED_WINDOWS,
    max_tries=5,
    threshold=0.27,
):
    best = None
    best_score = -1

    videos_shuffled = videos[:]
    random.shuffle(videos_shuffled)

    for path in videos_shuffled[:max_tries]:
        vid_duration = get_duration(path)
        if vid_duration is None or vid_duration < duration:
            continue

        vid = VideoFileClip(path)
        accepted = None
        try:
            # Try multiple attempts per video to avoid overlap
            for _ in range(3):  # try 3 random windows per video
                start = random.uniform(0, vid_duration - duration)
                end = start + duration

                # 🔥 Skip if overlapping
                if overlaps_existing(path, start, end, USED_WINDOWS):
                    continue

                score = score_window(vid, start, duration, keywords)

                # Track best
                if score > best_score:
                    best_score = score
                    best = (path, start, end)

                # Immediate accept if above threshold
                if score >= threshold:
                    accepted = (path, start, end)
                    break
        finally:
            vid.close()

        if accepted:
            USED_WINDOWS.setdefault(accepted[0], []).append((accepted[1], accepted[2]))
            return accepted

    # Fallback = best non-overlapping clip
    if best:
        path, start, end = best
        USED_WINDOWS.setdefault(path, []).append((start, end))
        return best

    return None

# def choose_clip_body(
#     videos,
#     duration,
#     keywords,
#     USED_WINDOWS,
#     max_tries=5,
#     threshold=0.27,
# ):
#     best = None
#     best_score = -1

    # videos_shuffled = videos[:]
    # random.shuffle(videos_shuffled)

    # for path in videos_shuffled[:max_tries]:
    #     vid = VideoFileClip(path)
    #     try:
    #         vid_duration = get_duration(path)
    #         if vid_duration is None or vid_duration < duration:
    #             continue

    #         coarse_hits = coarse_scan(path, vid, keywords)
    #         if not coarse_hits:
    #             continue
    #         COARSE_MIN = threshold - 0.05
    #         if coarse_hits[0][0] < COARSE_MIN:
    #             continue


    #         regions = refine_regions(path, coarse_hits, duration)
    #         if not regions:
    #             continue
    #         regions = regions[:2]

    #         used = USED_WINDOWS.get(path, [])
    #         valid_regions = []

    #         for lo, hi in regions:

    #             attempts = 2 if coarse_hits[0][0] > threshold else 3
    #             for _ in range(attempts):  # a few attempts per region
    #                 start = random.uniform(lo, hi)
    #                 end = start + duration
    #                 if not any(overlaps((start, end), u) for u in used):
    #                     valid_regions.append((start, end))
    #                     break

    #         if not valid_regions:
    #             fallback = fallback or path
    #             continue

    #         best_local = None
    #         best_local_score = -1

    #         for start, end in valid_regions:
    #             score = score_window(vid, start, duration, keywords)

    #             if score > best_local_score:
    #                 best_local_score = score
    #                 best_local = (start, end)

    #             if score >= threshold:
    #                 break

    #         if best_local_score > best_score:
    #             best_score = best_local_score
    #             best = (path, best_local[0], best_local[1])

    #         if best_local_score >= threshold:
    #             break
    #     except Exception as e:
    #         print(f"Error processing {path}: {e}")
    #     finally:
    #         vid.close()

    # if best:
    #     path, start, end = best
    #     USED_WINDOWS.setdefault(path, []).append((start, end))
    #     return best

    # if fallback:
    #     fb_duration = get_duration(fallback)
    #     if fb_duration and fb_duration >= duration:
    #         start = random.uniform(0, fb_duration - duration)
    #         end = start + duration
    #         USED_WINDOWS.setdefault(fallback, []).append((start, end))
    #         return (fallback, start, end)

    # return None
    
def make_video_clip(path, start, end, duration, current_time, size):
    return (
        VideoFileClip(path)
        .subclipped(start, end)
        .resized(height=size[1])
        .with_position(("center", "center"))
        .with_duration(duration)
        .with_start(current_time)
    )


