from utils.core.config import DIR_PATH, DATA_PATH, SOURCE_PATH, UTILS_PATH
from utils.core.settings import SFX_REGISTRY
from utils.core.edit import get_video_duration

from moviepy import (
    VideoFileClip, AudioFileClip, CompositeAudioClip, afx, concatenate_audioclips, concatenate_videoclips
)
import numpy as np
import os
import subprocess
import tempfile





def _adjust_volume_db(music_clip, target_db=-20, fps=44100):
    """Normalize audio loudness to a target dB level."""

    duration = music_clip.duration
    sample_points = np.linspace(0, duration, num=3)

    rms_values = []

    for t in sample_points:
        try:
            chunk = music_clip.to_soundarray(tt=t, fps=fps, nbytes=2)
            rms = np.sqrt(np.mean(np.square(chunk)))
            if rms > 0:
                db = 20 * np.log10(rms)
                rms_values.append(db)
        except Exception:
            continue

    if not rms_values:
        return music_clip

    avg_db = np.mean(rms_values)

    # Compute gain needed
    gain_db = target_db - avg_db    # how much to adjust
    gain_scale = 10 ** (gain_db / 20)

    # Cap extreme gain
    gain_scale = np.clip(gain_scale, 0.1, 3.0)

    print(f"Original loudness: {avg_db:.2f} dB")
    print(f"Target loudness:   {target_db} dB")
    print(f"Gain applied:      {gain_db:.2f} dB (scale={gain_scale:.2f})")

    return music_clip.with_effects([afx.MultiplyVolume(gain_scale)])

def assemble_intro(audio_path, visual_path, output_path):
    audio = AudioFileClip(audio_path)
    audio = audio.with_effects([afx.MultiplyVolume(2.5)])

    visual = VideoFileClip(visual_path)

    final = visual.with_audio(audio).with_duration(audio.duration)
    final.write_videofile(output_path, codec="libx264", fps=32, threads=2, preset="ultrafast")

def add_audio_to_visual(audio_path, visual_path, output_path):
    audio = AudioFileClip(audio_path)
    audio = audio.with_effects([afx.MultiplyVolume(2.5)])

    visual = VideoFileClip(visual_path)

    final = visual.with_audio(audio).with_duration(audio.duration)
    final.write_videofile(output_path, codec="libx264", fps=32, threads=2, preset="ultrafast")

def add_part_sfx(audio_path, sound_effects, output_path):
    original_audio = AudioFileClip(audio_path)

    all_audio_clips = [original_audio]
    for sfx in sound_effects:
        role = sfx["role"]
        time = sfx["time"]

        if role not in SFX_REGISTRY:
            print(f"[assemble] ⚠️ Unknown SFX role: {role}")
            continue

        print("[assemble] Adding SFX:", role, "at", time)

        sfx_path = SFX_REGISTRY[role]["path"]
        sfx_volume = SFX_REGISTRY[role].get("volume", 1.0)
        sfx_clip = AudioFileClip(sfx_path).with_effects([afx.MultiplyVolume(sfx_volume)])

        all_audio_clips.append(sfx_clip.with_start(time))

    final_audio = CompositeAudioClip(all_audio_clips)

    final_audio.write_audiofile(output_path)
    
    for c in all_audio_clips:
        c.close()

def _create_timestamps(video_paths):
    timestamps = []
    current_time = 0.0

    for title, path in video_paths:
        vid_dur = get_video_duration(path)

        timestamps.append((title, current_time))
        current_time += vid_dur
    
    return timestamps

def concat_part(video_parts, output_path):

    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as tf:
        for p in video_parts:
            tf.write(f"file '{os.path.abspath(p)}'\n")
        list_path = tf.name

    # Run ffmpeg concat
    cmd = [
        "ffmpeg",
        "-f", "concat",
        "-safe", "0",
        "-i", list_path,
        "-c", "copy",
        output_path
    ]

    subprocess.run(cmd, check=True)

    # Remove temp file
    os.remove(list_path)

def concat_video(pipeline, video_paths, output_path):
    timestamps = _create_timestamps(video_paths)
    pipeline.timestamps = timestamps

    part_paths = [part[1] for part in video_paths]

    # Create temporary concat file
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as tf:
        for p in part_paths:
            tf.write(f"file '{os.path.abspath(p)}'\n")
        list_path = tf.name

    # Run ffmpeg concat
    cmd = [
        "ffmpeg",
        "-f", "concat",
        "-safe", "0",
        "-i", list_path,
        "-c", "copy",
        output_path
    ]

    subprocess.run(cmd, check=True)

    # Remove temp file
    os.remove(list_path)

    return output_path, timestamps

def _loop_audio_to_duration(audio_clip, target_duration):
    clips = []
    t = 0
    while t < target_duration:
        clips.append(audio_clip)
        t += audio_clip.duration
    
    final = concatenate_audioclips(clips).subclipped(0, target_duration)
    return final

