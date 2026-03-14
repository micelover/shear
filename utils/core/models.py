import gc
import torch
from ultralytics import YOLO
from transformers import (
    CLIPModel,
    CLIPProcessor,
    AutoProcessor,
    AutoModelForZeroShotObjectDetection
)

from utils.core.config import DEVICE




_yolo = None
_clip_model = None
_clip_processor = None
_dino_model = None
_dino_processor = None

def get_yolo():
    global _yolo
    if _yolo is None:
        _yolo = YOLO("yolov8n.pt")
    return _yolo

def get_clip():
    global _clip_model, _clip_processor
    if _clip_model is None:
        _clip_model = (
            CLIPModel
            .from_pretrained("openai/clip-vit-base-patch32")
            .to(DEVICE)
            .eval()
        )
        for p in _clip_model.parameters():
            p.requires_grad = False

        _clip_processor = CLIPProcessor.from_pretrained(
            "openai/clip-vit-base-patch32",
            use_fast=True
        )

    return _clip_model, _clip_processor

def get_grounding_dino():
    global _dino_model, _dino_processor

    if _dino_model is None:
        _dino_processor = AutoProcessor.from_pretrained(
            "IDEA-Research/grounding-dino-base",
            use_fast=True
        )

        _dino_model = (
            AutoModelForZeroShotObjectDetection
            .from_pretrained("IDEA-Research/grounding-dino-base")
            .to(DEVICE)
            .eval()
        )

        for p in _dino_model.parameters():
            p.requires_grad = False

    return _dino_model, _dino_processor


def release_dino():
    """Free only the Grounding DINO model from memory."""
    global _dino_model, _dino_processor
    _dino_model = None
    _dino_processor = None
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def release_models():
    """Free all cached ML models from memory."""
    global _yolo, _clip_model, _clip_processor, _dino_model, _dino_processor
    _yolo = None
    _clip_model = None
    _clip_processor = None
    _dino_model = None
    _dino_processor = None
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()