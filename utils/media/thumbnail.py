from utils.core.config import DATA_PATH
from utils.core.models import release_dino
from utils.thumbnail.images import get_images
from utils.thumbnail.ai_design1 import create_ai_design1

from PIL import Image
import gc
import os




def ai_design1(product, product_type):
    all_img = get_images(product.title, product_type, fetch_count=4, num_images=1)

    if not all_img:
        print("❌ No images found for thumbnail")
        return

    create_ai_design1(product, all_img[0], product_type)

def compress_thumbnail(thumbnail_path):
    max_size = 2 * 1024 * 1024  # 2MB
    if os.path.getsize(thumbnail_path) <= max_size:
        return

    img = Image.open(thumbnail_path)

    # --- CROP TO 16:9 ---
    target_ratio = 16 / 9
    current_ratio = img.width / img.height

    if current_ratio > target_ratio:
        # Too wide → crop sides
        new_width = int(img.height * target_ratio)
        left = (img.width - new_width) // 2
        img = img.crop((left, 0, left + new_width, img.height))
    else:
        # Too tall → crop top/bottom
        new_height = int(img.width / target_ratio)
        top = (img.height - new_height) // 2
        img = img.crop((0, top, img.width, top + new_height))

    # --- RESIZE ---
    img = img.resize((1280, 720), Image.Resampling.LANCZOS)

    # --- SAVE PNG ---
    img.save(thumbnail_path, 'PNG', optimize=True)

    # --- FALLBACK TO JPEG IF TOO BIG ---
    if os.path.getsize(thumbnail_path) > max_size:
        jpg_path = thumbnail_path.replace('.png', '.jpg')
        img.save(jpg_path, 'JPEG', quality=85)
        os.replace(jpg_path, thumbnail_path)

def generate_thumbnail(pipeline):

    # design1(product)
    # design2(product)
    ai_design1(pipeline.product, pipeline.product_type)
    release_dino()  # free ~800MB immediately after DINO is done

    thumbnail_path = f"{DATA_PATH}/thumbnail.png"
    if os.path.exists(thumbnail_path):
        compress_thumbnail(thumbnail_path)
    else:
        print("⚠️ Thumbnail was not generated, skipping compression.")

    gc.collect()





        


