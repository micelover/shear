from utils.core.config import DIR_PATH, DATA_PATH, SOURCE_PATH, UTILS_PATH
from utils.core.pipeline_data import PipelineData

from utils.media.build_paths import build_proj_paths
from utils.media.product_fetcher import ProductFetcher
from utils.media.audio import Audio
from utils.media.media_fetcher import MediaFetcher
from utils.media.visual import Visual
from utils.media.assemble import assemble_intro, add_audio_to_visual, add_part_sfx, concat_part, concat_video
from utils.media.thumbnail import generate_thumbnail
from utils.media.video_data import generate_data
from utils.media.upload_video import get_authenticated_service, upload_video, set_thumbnail
from utils.core.models import release_models

from concurrent.futures import ThreadPoolExecutor, as_completed
import random
import os
import shutil
import time

random.seed(time.time())
os.environ["TOKENIZERS_PARALLELISM"] = "false"


def _classify_product(product_fetcher, simple_title):
    with ThreadPoolExecutor(max_workers=2) as executor:
        f_keywords = executor.submit(product_fetcher.generate_keywords, simple_title)
        f_classify = executor.submit(product_fetcher.classify_product, simple_title)
        f_keywords.result()
        f_classify.result()


def _fetch_audio_and_media(audio, media_fetcher, product, proj_paths):
    with ThreadPoolExecutor(max_workers=2) as executor:
        f_audio = executor.submit(audio.generate_audio, product, proj_paths)
        f_media = executor.submit(media_fetcher.fetch_for_product, product, media_dir=proj_paths["media_dir"])
        f_audio.result()
        f_media.result()


def _generate_thumbnail_and_data(pipeline):
    with ThreadPoolExecutor(max_workers=2) as executor:
        future_thumbnail = executor.submit(generate_thumbnail, pipeline)
        future_data = executor.submit(generate_data, pipeline.product)
        design = future_thumbnail.result()
        data = future_data.result()
    return design, data


def main():
    if os.path.isdir(DATA_PATH): 
        shutil.rmtree(DATA_PATH)

    os.makedirs(DATA_PATH)
    os.makedirs(f"{DATA_PATH}/thumbnail/process")

    proj_paths = build_proj_paths(DATA_PATH)

    os.makedirs(proj_paths['audio_dir'], exist_ok=True)
    os.makedirs(proj_paths['media_dir'], exist_ok=True)

    pipeline = PipelineData()

    product_fetcher = ProductFetcher(pipeline)
    product_fetcher.get_product()
    print("✅ Product fetched:", pipeline.product)

    _classify_product(product_fetcher, pipeline.product.simple_title)

    print("✅ Keywords Created:", pipeline.keywords)
    print("✅ Product Classified:", pipeline.product_type)
    del product_fetcher

    audio = Audio(pipeline)
    media_fetcher = MediaFetcher()
    visual = Visual(pipeline)

    _fetch_audio_and_media(audio, media_fetcher, pipeline.product, proj_paths)
    del audio, media_fetcher

    visual.build_visual(pipeline.product, proj_paths)
    del visual

    add_audio_to_visual(
        audio_path=proj_paths['audio'], 
        visual_path=proj_paths['visual'], 
        output_path=proj_paths['final_video']
    )

    design, data = _generate_thumbnail_and_data(pipeline)
    del design, pipeline
    release_models()

    print(f"[Main] ✅ Data made: {data}")

    # data = {'file': '/Users/gladwynli/Documents/bots/shear/data/final.mp4', 'title': 'SANSUI 24 Inch Gaming Monitor Review – Is It Good?', 'description': "This is a review of SANSUI 24 Inch Gaming Monitor. We evaluate the SANSUI 24 Inch Gaming Monitor's performance and features, outline the key pros and cons, and give a clear verdict on whether it's worth buying. The link to SANSUI 24 Inch Gaming Monitor is in the description.\n\n✅ SANSUI 24 Inch Gaming Monitor\nhttps://www.amazon.com/dp/B0CGD9R7PT?tag=logostudios-20\n\n\n► Disclaimer ◄  \nPrimeChoice Picks is a participant in the Amazon Services LLC Associates Program.  \nAs an Amazon Associate, I earn from qualifying purchases at no additional cost to you.", 'tags': ['24 inch monitor', 'sansui gaming monitor 24 inch', 'sansui 24 inch gaming monitor', 'pc monitor', 'sansui 24 inch monitor review', 'led monitor', 'sansui 24 inch gaming monitor', 'gaming monitor', 'sansui monitor 24 inch', 'budget gaming monitor'], 'privacy_status': 'unlisted'}
    youtube = get_authenticated_service()

    video_id = upload_video(youtube, data)
    del data
    print(f"[Main] ✅ Upload complete! Video ID: {video_id}")

    thumbnail_path = f"{DATA_PATH}/thumbnail.png"
    if os.path.exists(thumbnail_path):
        set_thumbnail(youtube, video_id, thumbnail_path)
        print(f"[Main] ✅ Thumbnail uploaded!")
    else:
        print("[Main] Skipping: file not found.", flush=True)

    # comment_id = add_pinned_comment(
    #     youtube,
    #     video_id,
    #     data.get("pinned_comment", "Links to products are in the description!")
    # )

def main2():
    if os.path.isdir(DATA_PATH): 
        shutil.rmtree(DATA_PATH)

    os.makedirs(DATA_PATH)
    os.makedirs(f"{DATA_PATH}/thumbnail/process")

    proj_paths = build_proj_paths(DATA_PATH)

    os.makedirs(proj_paths['audio_dir'], exist_ok=True)
    os.makedirs(proj_paths['media_dir'], exist_ok=True)

    pipeline = PipelineData()

    product_fetcher = ProductFetcher(pipeline)
    product_fetcher.get_product()
    print("✅ Product fetched:", pipeline.product)

    _classify_product(product_fetcher, pipeline.product.simple_title)
    print("✅ Product Classified:", pipeline.product_type)

    # data = generate_data(pipeline.product)
    generate_thumbnail(pipeline)


if __name__ == "__main__":
    main()