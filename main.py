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

from concurrent.futures import ThreadPoolExecutor, as_completed
import random
import os
import shutil
import time

random.seed(time.time())
os.environ["TOKENIZERS_PARALLELISM"] = "false"

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
    product_fetcher.GetProduct()
    print("✅ Product fetched:", pipeline.product)

    product_fetcher.generate_keywords(pipeline.product.simple_title)
    print("✅ Keywords Created:", pipeline.keywords)

    audio = Audio(pipeline)
    media_fetcher = MediaFetcher()
    visual = Visual(pipeline)

    audio.generate_audio(pipeline.product, proj_paths)

    media_fetcher.fetch_for_product(pipeline.product, media_dir=proj_paths["media_dir"])

    visual.build_visual(pipeline.product, proj_paths)

    add_audio_to_visual(
        audio_path=proj_paths['audio'], 
        visual_path=proj_paths['visual'], 
        output_path=proj_paths['final_video']
    )

    design = generate_thumbnail(pipeline.product)

    data = generate_data(pipeline.product)
    print(f"[Main] ✅ Data made: {data}")

    # data = {'file': '/Users/gladwynli/Documents/bots/shear/data/final.mp4', 'title': 'SANSUI 24 Inch Gaming Monitor Review – Is It Good?', 'description': "This is a review of SANSUI 24 Inch Gaming Monitor. We evaluate the SANSUI 24 Inch Gaming Monitor's performance and features, outline the key pros and cons, and give a clear verdict on whether it's worth buying. The link to SANSUI 24 Inch Gaming Monitor is in the description.\n\n✅ SANSUI 24 Inch Gaming Monitor\nhttps://www.amazon.com/dp/B0CGD9R7PT?tag=logostudios-20\n\n\n► Disclaimer ◄  \nPrimeChoice Picks is a participant in the Amazon Services LLC Associates Program.  \nAs an Amazon Associate, I earn from qualifying purchases at no additional cost to you.", 'tags': ['24 inch monitor', 'sansui gaming monitor 24 inch', 'sansui 24 inch gaming monitor', 'pc monitor', 'sansui 24 inch monitor review', 'led monitor', 'sansui 24 inch gaming monitor', 'gaming monitor', 'sansui monitor 24 inch', 'budget gaming monitor'], 'privacy_status': 'unlisted'}
    youtube = get_authenticated_service()

    video_id = upload_video(youtube, data)
    print(f"[Main] ✅ Upload complete! Video ID: {video_id}")

    thumbnail_path = f"{DATA_PATH}/thumbnail.png"
    if os.path.exists(thumbnail_path):
        set_thumbnail(youtube, video_id, thumbnail_path)
        print(f"[Main] ✅ Thumbnail uploaded!")
    else:
        print("[Main] Skipping: file not found.", flush=True)



    # for idx, product in enumerate(pipeline.products):
    #     print("literation:", idx)
    #     rank = len(pipeline.products) - idx
    #     part_paths = build_part_paths(base_dir=DATA_PATH, rank=rank)

    #     os.makedirs(part_paths['audio_dir'], exist_ok=True)
    #     os.makedirs(part_paths['media_dir'], exist_ok=True)

    #     audio.generate_audio_part(product, rank, part_paths)

    #     media_fetcher.fetch_for_product(product, media_dir=part_paths['media_dir'])
    #     sound_effects = visual.build_visual_part(rank, product, part_paths)

    #     add_part_sfx(part_paths['body_audio'], sound_effects, part_paths['body_audio_sfx'])

    #     add_audio_to_visual(
    #         audio_path=part_paths['intro_audio'], 
    #         visual_path=part_paths['intro_visual'], 
    #         output_path=part_paths['intro_video']
    #     )
    #     add_audio_to_visual(
    #         audio_path=part_paths['body_audio_sfx'], 
    #         visual_path=part_paths['body_visual'], 
    #         output_path=part_paths['body_video']
    #     )

    #     concat_part([part_paths['intro_video'], part_paths['body_video']], part_paths['final_video'])

    #     all_part_paths.append((product.title, part_paths['final_video']))

    #     if rank == 1:
    #         visual.build_intro(proj_paths, part_paths)
    #         assemble_intro(proj_paths['intro_audio'], proj_paths['intro_visual'], proj_paths['intro_video'])

    #         all_part_paths.insert(0, ("Intro", proj_paths['intro_video']))

    #         os.remove(proj_paths['intro_audio'])
    #         os.remove(proj_paths['intro_srt'])
    #         os.remove(proj_paths['intro_visual'])

    #     shutil.rmtree(part_paths['base'])

    # concat_video(pipeline, all_part_paths, proj_paths["final_video"])
    # for part in all_part_paths:
    #     os.remove(part[1])

    # design = generate_thumbnail(TOPIC, pipeline.products)
    # # design = generate_thumbnail(TOPIC)
    # print(f"[Main] ✅ Thumbnail made!")

    # data = generate_data(TOPIC, pipeline.products, pipeline.timestamps, design=design)
    # print(f"[Main] ✅ Data made: {data}")

    # time.sleep(60)
    # data = {'file': '/Users/gladwynli/Documents/bots/fufuv2/data/final.mp4', 'title': 'Top 5 Best 3D Printers 2026 - These Surprised Me', 'description': 'We put the leading 3d-printers of 2026 head-to-head to find the best overall value. Our hands-on testing focuses on print quality, speed, and reliability using the same benchmark models and tough materials. If you’re looking to buy a 3d-printer, you’re in the right place.\n\n✅ FlashForge Adventurer 5M\nhttps://www.amazon.com/dp/B0CH4NYL6J?tag=logostudios-20\n\n✅ FlashForge Adventurer 5M Pro\nhttps://www.amazon.com/dp/B0CH4RG161?tag=logostudios-20\n\n✅ MINGDA W600DMDA\nhttps://www.amazon.com/dp/B0DMPYVTP7?tag=logostudios-20\n\n✅ Flashforge AD5X\nhttps://www.amazon.com/dp/B0DN68QV3B?tag=logostudios-20\n\n✅ FlashForge AD5X Multicolor\nhttps://www.amazon.com/dp/B0DNW25S87?tag=logostudios-20\n\n\n0:00 → Intro\n0:14 → 5️⃣ FLASHFORGE Adventurer 5M 3D Printer with Fully Auto Leveling, Max 600mm/s High Speed Printing, 280°C Direct Extruder with 3S Detachable Nozzle, CoreXY All Metal Structure, Print Size 220x220x220mm\n1:23 → 4️⃣ FLASHFORGE Adventurer 5M Pro 3D Printer with 1 Click Auto Printing System, 600mm/s High-Speed, Quick Detachable 280°C Nozzle, Core XY All-Metal Structure, Multi-Functional 220x220x220mm 3D Printer\n2:37 → 3️⃣ 3D Fast Printing Industrial Parts 3D Printer W600DMDA, High Precision 3D Printer - MINGDA Technology Co\n3:45 → 2️⃣ FLASHFORGE AD5X Multi-Color 3D Printer, CoreXY 600mm/s High-Speed, 1-Click Auto Leveling, 300°C Direct Drive Extruder, 220x220x220mm Build Volume, Ideal for Precision and Efficiency\n4:59 → 1️⃣ FLASHFORGE AD5X Multi-Color 3D Printer with IFS, 600mm/s High Speed, 300°C High Temp Direct Extruder, Fully Auto Leveling, All Metal CoreXY,4-Color Printing for PLA-CF,PETG-CF, 220x220x220mm\n► Disclaimer ◄  \nPrimeChoice Picks is a participant in the Amazon Services LLC Associates Program.  \nAs an Amazon Associate, I earn from qualifying purchases at no additional cost to you.', 'tags': ['prusa mk4 worth it', 'creality k1 max review', 'diy 3d printing', 'maker tools', 'top gadgets 2026', 'best 3d printers 2026', 'amazon tech finds', 'bambu x1c review', 'auto leveling', 'corexy printer'], 'privacy_status': 'unlisted'}

    # youtube = get_authenticated_service()

    # video_id = upload_video(youtube, data)
    # print(f"[Main] ✅ Upload complete! Video ID: {video_id}")

    # thumbnail_path = f"{DATA_PATH}/thumbnail.png"
    # if os.path.exists(thumbnail_path):
    #     set_thumbnail(youtube, video_id, thumbnail_path)
    # else:
    #     print("[Main] Skipping: file not found.", flush=True)
    # print(f"[Main] ✅ Thumbnail uploaded!")

    # # comment_id = add_pinned_comment(
    # #     youtube,
    # #     video_id,
    # #     data.get("pinned_comment", "Links to products are in the description!")
    # # )

if __name__ == "__main__":
    main()