from utils.core.config import DIR_PATH, DATA_PATH, SOURCE_PATH, UTILS_PATH
from moviepy import (
    TextClip, CompositeVideoClip
)
import os
import pysrt
import os




dosis = f"{SOURCE_PATH}/font/Dosis/Dosis-VariableFont_wght.ttf"
futura_bold = f"{SOURCE_PATH}/font/Futura Bold/Futura Bold.otf"
open_sans = f"{SOURCE_PATH}/font/Open_Sans/OpenSans-Bold.ttf"


def create_subtitle_clips(video_height, srt_path, start_time=0, size=(1280,720)):
    """Return a list of TextClip objects. Caller adds them to its own CompositeVideoClip."""
    srt = pysrt.open(srt_path)

    # Config
    prop = 70
    color1 = "#FFFFFF"
    fontType = futura_bold
    stroke = 2.75
    max_char = 16
    max_words = 1

    # Group lines
    all_lines, line, current_char, current_words = [], [], 0, 0
    for sub in srt:
        characters = len(sub.text) + 1
        if not line or ((current_char + characters <= max_char) and (current_words + 1 <= max_words)):
            line.append(sub)
            current_char += characters
            current_words += 1
        else:
            all_lines.append(line)
            line, current_char, current_words = [sub], characters, 1
    if line: all_lines.append(line)

    subtitle_clips = []

    # Build clips
    for line in all_lines:
        full_text = "".join(te.text for te in line)

        start = (line[0].start.hours * 3600 + line[0].start.minutes * 60 +
                line[0].start.seconds + line[0].start.milliseconds / 1000) + start_time
        end = (line[-1].end.hours * 3600 + line[-1].end.minutes * 60 +
            line[-1].end.seconds + line[-1].end.milliseconds / 1000) + start_time

        text_clip = TextClip(
            text=full_text, font_size=prop, color=color1, font=fontType,
            method='caption', size=(size[0], 350),
            stroke_color='#000000', stroke_width=stroke
        )

        clip_h = text_clip.h
        coords = lambda t, h=video_height, ch=clip_h: (
            "center",
            (h - 125) - (ch * (1 + 0.2 * (1 - (min(t, 0.15) / 0.15) ** 2)) / 2)
        )

        text_clip = (
            text_clip
            .with_start(start).with_end(end)
            .with_duration(end - start)
            .with_position(coords)
            .resized(lambda t: 1 + 0.2 * (1 - (min(t, 0.1) / 0.1) ** 2))
        )
        subtitle_clips.append(text_clip)

    return subtitle_clips


# Legacy wrapper kept for backwards compatibility
def create_subtitle_video(preSubAudio, srt_path, start_time=0, size=(1280,720)):
    subtitle_clips = create_subtitle_clips(preSubAudio.h, srt_path, start_time=start_time, size=size)
    return CompositeVideoClip([preSubAudio, *subtitle_clips])
