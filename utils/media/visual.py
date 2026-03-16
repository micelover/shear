from utils.core.config import DIR_PATH, DATA_PATH, SOURCE_PATH, UTILS_PATH
from utils.visual.video_clip import choose_clip_intro, choose_clip_body, make_video_clip
from utils.visual.link_overlay import create_link_overlay
from utils.visual.part.product_overlay import dual_slide_overlay
from utils.visual.specs_overlay import create_specs
from utils.visual.subtitles import create_subtitle_clips
from utils.core.edit import get_audio_duration, open_ai_generation, find_videos, find_images
from utils.core.settings import PART_DURATION

from moviepy import (
    CompositeVideoClip, ImageClip, CompositeVideoClip, ColorClip, concatenate_videoclips 
)
import concurrent.futures
import subprocess
import tempfile
import random
import gc
import os
import json
import re




class Visual():
    def __init__(self, pipeline):
        self.dosis = f"{SOURCE_PATH}/font/Dosis/Dosis-VariableFont_wght.ttf"
        self.futura_bold = f"{SOURCE_PATH}/font/Futura Bold/Futura Bold.otf"
        self.open_sans = f"{SOURCE_PATH}/font/Open_Sans/OpenSans-Bold.ttf"
        self.nunito_bold = f"{SOURCE_PATH}/font/Nunito/Nunito-Bold.ttf"

        self.pipeline = pipeline

        with open(f'{UTILS_PATH}/prompts/part_segment_length.txt', 'r') as file:
            self.orignial_part_segment_length_prompt = file.read()

        self.video_size = (1280, 720)

    def preload_assets(self, folder):
        with concurrent.futures.ThreadPoolExecutor() as ex:
            imgs_future = ex.submit(find_images, folder)
            vids_future = ex.submit(find_videos, folder)
            images = imgs_future.result()
            videos = vids_future.result()
        valid_videos = [v for v in videos if os.path.getsize(v) > 1000]
        return images, valid_videos

    @staticmethod
    def _clip_to_segment(clip, seg_start, seg_end):
        """
        Slice a clip (with absolute .start time) into a segment window.
        Returns the re-timed clip, or None if the clip is not active in [seg_start, seg_end).
        """
        clip_start = clip.start
        clip_end   = clip_start + clip.duration

        if clip_end <= seg_start or clip_start >= seg_end:
            return None

        offset   = max(0.0, seg_start - clip_start)
        new_dur  = min(clip_end, seg_end) - max(clip_start, seg_start)
        new_start = max(0.0, clip_start - seg_start)

        # Guard against zero/negative duration due to floating point
        if new_dur <= 0.001:
            return None

        return (
            clip.subclipped(offset, offset + new_dur)
                .with_start(new_start)
        )

    def _render_in_segments(
        self,
        all_clips,
        link_overlay,
        spec_overlays,
        subtitle_clips,
        audio_duration,
        visual_save_path,
        segment_duration=45,
    ):
        """
        Render the composite in fixed-length chunks to cap peak RAM,
        then concat the chunks with ffmpeg stream-copy (no re-encode).
        """
        overlays = [link_overlay, *spec_overlays, *subtitle_clips]
        segment_paths = []
        t = 0.0
        seg_idx = 0

        while t < audio_duration:
            seg_end = min(t + segment_duration, audio_duration)
            seg_len = seg_end - t

            print(f"[visual] Rendering segment {seg_idx}: {t:.1f}s – {seg_end:.1f}s")

            seg_clips = [
                ColorClip(size=self.video_size, color=(0, 0, 0)).with_duration(seg_len)
            ]

            for clip in all_clips:
                sliced = self._clip_to_segment(clip, t, seg_end)
                if sliced is not None:
                    seg_clips.append(sliced)

            for ov in overlays:
                sliced = self._clip_to_segment(ov, t, seg_end)
                if sliced is not None:
                    seg_clips.append(sliced)

            seg_path = f"{visual_save_path}.seg{seg_idx:03d}.mp4"
            segment_paths.append(seg_path)

            comp = CompositeVideoClip(seg_clips, size=self.video_size)
            comp.write_videofile(
                seg_path,
                fps=24,
                codec="libx264",
                preset="ultrafast",
                bitrate="6000k",
                audio=False,
                threads=os.cpu_count(),
                logger=None,
            )
            comp.close()
            # Close sliced copies (not the originals — those are closed by the caller)
            for c in seg_clips[1:]:
                try:
                    c.close()
                except Exception:
                    pass
            del comp, seg_clips
            gc.collect()

            t = seg_end
            seg_idx += 1

        # Concatenate all segments with ffmpeg stream-copy (very fast, no RAM spike)
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as tf:
            for p in segment_paths:
                tf.write(f"file '{os.path.abspath(p)}'\n")
            list_path = tf.name

        try:
            subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-f", "concat", "-safe", "0",
                    "-i", list_path,
                    "-c", "copy",
                    visual_save_path,
                ],
                check=True,
            )
        finally:
            os.remove(list_path)
            for p in segment_paths:
                try:
                    os.remove(p)
                except Exception:
                    pass

        print(f"[visual] ✅ Segments concatenated → {visual_save_path}")
    
    
    def select_clips(self, duration, part_plan, images, valid_videos):
        all_body_clips = []
        last_img = None

        USED_WINDOWS = {}  
        for i, segment in enumerate(part_plan):
            is_last = (i == len(part_plan) - 1)
                            
            sentence = segment["sentence"]
            clip_targets = [sentence]

            start_time = segment["start"]
            end_time = segment["end"]
            if is_last:
                end_time = duration

            est_time = end_time - start_time

            if not valid_videos and not images:
                break

            if random.random() < 0.95 and valid_videos:  
                clip_info = choose_clip_body(valid_videos, est_time, self.pipeline.keywords, USED_WINDOWS)
                if clip_info:
                    path, start, end = clip_info
                    clip = make_video_clip(path, start, end, est_time, start_time, self.video_size)
                else:
                    continue

            else:  
                if not images:
                    continue
                random_img = random.choice(images)

                # 🔑 prevent same image twice in a row
                if random_img == last_img and len(images) > 1:
                    random_img = random.choice(
                        [img for img in images if img != last_img]
                    )

                last_img = random_img

                clip = ImageClip(random_img).resized(height=self.video_size[1])
                pos = ((self.video_size[0]-clip.w)//2, 0)
                clip = clip.with_position(pos).with_duration(est_time).with_start(start_time)

            all_body_clips.append(clip)

        return all_body_clips


    def build_visual(self, product, paths):
        title, simple_title = product.title, product.simple_title

        base_path = paths["base"]
        visual_path = paths["media_dir"]

        audio_path = paths["audio"]

        words_srt_path = paths["words_srt"]
        sentences_srt_path = paths["sentences_srt"]

        visual_save_path = paths["visual"]

        audio_duration = get_audio_duration(audio_path)

        images, valid_videos = self.preload_assets(visual_path)

        with open(sentences_srt_path, "r", encoding="utf-8") as f:
            sentences_srt_text = f.read().strip()

        segment_length_prompt = (self.orignial_part_segment_length_prompt
            .replace("{srt}", str(sentences_srt_text))
            .replace("{length_high}", PART_DURATION["high"])
        )
        response_data = open_ai_generation(segment_length_prompt, model="gpt-5-mini", temperature=0.25)
        if response_data:
            response_data = re.sub(r"^```(?:json)?|```$", "", response_data.strip(), flags=re.MULTILINE).strip()
            try:
                segment_data = json.loads(response_data)
            except Exception as e:
                print("[visual] ❌ JSON parse failed for visual planner:", response_data)

        print("SEGMENT DATA MADE:", segment_data)

        print(images, valid_videos)
        all_clips = self.select_clips(audio_duration, segment_data, images, valid_videos)
        link_overlay = create_link_overlay(words_srt_path)
        spec_overlays, sound_effects = create_specs(words_srt_path, start=0)
        subtitle_clips = create_subtitle_clips(self.video_size[1], words_srt_path, start_time=0, size=self.video_size)

        # Render in 45-second segments to cap peak RAM, then ffmpeg-concat
        self._render_in_segments(
            all_clips,
            link_overlay,
            spec_overlays,
            subtitle_clips,
            audio_duration,
            visual_save_path,
        )

        for clip in all_clips:
            try:
                clip.close()
            except Exception:
                pass

        # return sound_effects


