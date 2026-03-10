from utils.core.config import DIR_PATH, DATA_PATH, SOURCE_PATH, UTILS_PATH
from utils.visual.video_clip import choose_clip_intro, choose_clip_body, make_video_clip
from utils.visual.link_overlay import create_link_overlay
from utils.visual.part.product_overlay import dual_slide_overlay
from utils.visual.specs_overlay import create_specs
from utils.visual.subtitles import create_subtitle_video
from utils.core.edit import get_audio_duration, open_ai_generation, find_videos, find_images
from utils.core.settings import PART_DURATION

from moviepy import (
    CompositeVideoClip, ImageClip, CompositeVideoClip, ColorClip, concatenate_videoclips 
)
import concurrent.futures
import random
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

        background = ColorClip(size=self.video_size, color=(0, 0, 0)).with_duration(audio_duration)

        print(images, valid_videos)
        all_clips = self.select_clips(audio_duration, segment_data, images, valid_videos)
        link_overlay = create_link_overlay(words_srt_path)
        spec_overlays, sound_effects = create_specs(words_srt_path, start=0) 


        # body = CompositeVideoClip([background, *body_clips, *spec_overlays], size=self.video_size)
        visual_clip = CompositeVideoClip([background, *all_clips, link_overlay, *spec_overlays], size=self.video_size)

        visual_clip = create_subtitle_video(visual_clip, words_srt_path, start_time=0, size=self.video_size)

        visual_clip.write_videofile(visual_save_path, fps=32, codec="libx264", threads=2, preset="ultrafast")

        # part_video.close()

        for clip in all_clips:
            clip.close()

        # return sound_effects


