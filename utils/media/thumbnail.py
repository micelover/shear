from utils.core.config import DATA_PATH
from utils.core.models import release_dino
from utils.thumbnail.flux_design1 import create_flux_design

from PIL import Image
import gc
import os




def flux_design(product, product_type):
    create_flux_design(product, product_type)


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
    flux_design(pipeline.product, pipeline.product_type)
    release_dino()  # free ~800MB immediately after DINO is done

    compress_thumbnail(f"{DATA_PATH}/thumbnail.png")

    gc.collect()    





        


