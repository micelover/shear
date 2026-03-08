from utils.core.config import DATA_PATH
import os






def build_proj_paths(base_dir):
    return {
        "base": base_dir,
        "audio_dir": os.path.join(base_dir, "audio"),
        "visual_dir": os.path.join(base_dir, "visual"),
        "media_dir": os.path.join(base_dir, "visual", "media"),

        "audio": os.path.join(base_dir, "audio", "audio.wav"),
        "audio_sfx": os.path.join(base_dir, "audio", "audio_sfx.wav"),

        "words_srt": os.path.join(base_dir, "audio", "words.srt"),
        "sentences_srt": os.path.join(base_dir, "audio", "sentences.srt"),

        "visual": os.path.join(base_dir, "visual", "visual.mp4"),

        # "intro_video": os.path.join(base_dir, "intro.mp4"),
        # "body_video": os.path.join(base_dir, "body.mp4"),

        "video": os.path.join(base_dir, "video.mp4"),
        "final_video": os.path.join(base_dir, "final.mp4")
    }