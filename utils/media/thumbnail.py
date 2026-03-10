from utils.core.config import DIR_PATH, DATA_PATH, SOURCE_PATH, UTILS_PATH
from utils.core.settings import THUMBNAIL_IMG_COUNT
from utils.thumbnail.design1 import create_design1
from utils.thumbnail.design2 import create_design2
from utils.thumbnail.ai_design1 import create_ai_design1
from utils.thumbnail.images import get_images

from datetime import datetime
from PIL import Image
import gc
import random
import torch
import os




impact = f"{SOURCE_PATH}/font/Impact-Font/impact.ttf"
anton = f"{SOURCE_PATH}/font/Anton/Anton-Regular.ttf"  
all_font_path = [impact, anton]

now = datetime.now()
year = now.year

with open(f'{UTILS_PATH}/prompts/size_classify.txt', 'r') as file:
    orignial_size_classify_prompt = file.read()

with open(f'{UTILS_PATH}/prompts/image/ai_design_small.txt', 'r') as file:
    orignial_ai_design_small_prompt = file.read()

with open(f'{UTILS_PATH}/prompts/image/ai_design_big.txt', 'r') as file:
    orignial_ai_design_big_prompt = file.read()

def design1(product):
    img_info = THUMBNAIL_IMG_COUNT['design1']

    all_img = get_images(product, fetch_count=img_info[0], num_images=img_info[1])
    # all_img = ['/Users/gladwynli/Documents/bots/shear/data/thumbnail/img_b71782b5.png', '/Users/gladwynli/Documents/bots/shear/data/thumbnail/img_daddd8c3.png', '/Users/gladwynli/Documents/bots/shear/data/thumbnail/img_ef1dbf12.png', '/Users/gladwynli/Documents/bots/shear/data/thumbnail/img_f547bfd8.png']
    print(all_img)

    create_design1(
        product_images=all_img,
        output_path=f"{DATA_PATH}/thumbnail.png"
    )

def design2(product):
    img_info = THUMBNAIL_IMG_COUNT['design2']

    all_img = get_images(product, fetch_count=img_info[0], num_images=img_info[1], workers=4)
    print("all_img", all_img)

    create_design2(
        product_images=all_img,
        output_path=f"{DATA_PATH}/thumbnail.png"
    )

def ai_design(product, product_type):
    img_info = THUMBNAIL_IMG_COUNT['ai_design']

    all_img = get_images(product, fetch_count=img_info[0], num_images=img_info[1], workers=4)
    # all_img = ['/Users/gladwynli/Documents/bots/shear/data/thumbnail/img_d7f2d9da.png', '/Users/gladwynli/Documents/bots/shear/data/thumbnail/img_8e0b0397.png', '/Users/gladwynli/Documents/bots/shear/data/thumbnail/img_0073911c.png', '/Users/gladwynli/Documents/bots/shear/data/thumbnail/img_ff57184b.png']
    print(all_img)

    # Pick 2 random images safely
    chosen_imgs = random.sample(all_img, min(2, len(all_img)))

    create_ai_design1(
        product,
        chosen_imgs,
        product_type
    )


def compress_thumbnail(thumbnail_path):
    max_size = 2 * 1024 * 1024  # 2MB
    if os.path.getsize(thumbnail_path) <= max_size:
        return

    img = Image.open(thumbnail_path)
    # Resize to 1280x720 if larger
    if img.width > 1280 or img.height > 720:
        img.thumbnail((1280, 720), Image.Resampling.LANCZOS)

    # Save optimized PNG
    img.save(thumbnail_path, 'PNG', optimize=True)

    # If still >2MB, convert to JPEG
    if os.path.getsize(thumbnail_path) > max_size:
        img.save(thumbnail_path.replace('.png', '.jpg'), 'JPEG', quality=85)
        os.rename(thumbnail_path.replace('.png', '.jpg'), thumbnail_path)


def generate_thumbnail(pipeline):  

    # design1(product)
    # design2(product)
    ai_design(pipeline.product, pipeline.product_type)

    compress_thumbnail(f"{DATA_PATH}/thumbnail.png")

    gc.collect()    





        


