from utils.core.config import DIR_PATH, DATA_PATH, SOURCE_PATH, UTILS_PATH

from moviepy import (
    TextClip, ColorClip,CompositeVideoClip
)




open_sans = f"{SOURCE_PATH}/font/Open_Sans/OpenSans-Bold.ttf"

def dual_slide_overlay(product_number, product_name, video_size=(1280,720), duration=4, start_time=0):
    w, h = video_size

    number_box_size = (int(w * 0.25), int(h * 0.1))
    title_box_size  = (int(w * 0.8), int(h * 0.18))

    V_PAD = 40

    txt_num = (TextClip(
        font=open_sans, 
        text=product_number, 
        font_size=60, 
        color="#1976D2",
        size=(number_box_size[0], number_box_size[1] + V_PAD),
    ).with_duration(duration))
    txt_num_w, txt_num_h = txt_num.size

    txt_title = (TextClip(
        font=open_sans, 
        text=product_name, 
        font_size=60, 
        color="white",
        size=(None, title_box_size[1] + V_PAD),
    ).with_duration(duration))
    txt_title_w, txt_title_h = txt_title.size

    number_box = ColorClip(size=(txt_num_w, number_box_size[1]), color=(255, 255, 255)).with_duration(duration)
    title_box  = ColorClip(size=(txt_title_w, title_box_size[1]),  color=(25,118,210)).with_duration(duration)
    num_w, num_h     = map(int, txt_num.size)
    title_w, title_h = map(int, txt_title.size)

    # Timing
    enter_time = 0.2
    exit_time  = 0.3
    hold_time  = duration - (enter_time + exit_time)

    # Y positions (stacked like in screenshot)
    number_txt_y = h//2 - title_box_size[1]//2 - number_box_size[1] - 30
    number_box_y = h//2 - title_box_size[1]//2 - number_box_size[1] - 10

    title_y  = h//2 - title_box_size[1]//2

    # Targets (center positions for boxes)
    number_target_x = w//2 - txt_num_w//2
    title_target_x  = w//2 - txt_title_w//2

    def slide_in_right(t, target_x, clip_w, y):
        if t < enter_time:
            progress = min(t / enter_time, 1)
            # start fully offscreen right → move to target_x
            x = int(w + (target_x - w) * progress)

        elif t < enter_time + hold_time:
            x = target_x

        else:
            progress = min((t - enter_time - hold_time) / exit_time, 1)
            # move from target_x → fully offscreen right
            x = int(target_x + progress * (w - target_x))

        return (x, y)

    def slide_in_left(t, target_x, clip_w, y):
        if t < enter_time:
            progress = min(t / enter_time, 1)
            x = int(-clip_w + progress * (target_x + clip_w))
        elif t < enter_time + hold_time:
            x = target_x
        else:
            progress = min((t - enter_time - hold_time) / exit_time, 1)
            x = int(target_x - progress * (target_x + clip_w))

        return (x, y)

    # Apply box animations
    number_box = number_box.with_position(
        lambda t: slide_in_left(t, number_target_x, number_box.w, number_box_y)
    )

    title_box = title_box.with_position(
        lambda t: slide_in_right(t, title_target_x, title_box.w, title_y)
    )

    txt_num = txt_num.with_position(
        lambda t: (
            slide_in_left(t, number_target_x, txt_num.w, number_txt_y)[0],
            number_txt_y + (number_box_size[1] - num_h) // 2
        )
    )

    txt_title = txt_title.with_position(
        lambda t: (
            slide_in_right(t, title_target_x, txt_title.w, title_y)[0],
            title_y + (title_box_size[1] - title_h) // 2
        )
    )

    overlay = CompositeVideoClip([number_box, title_box, txt_num, txt_title], size=video_size)
    return overlay.with_start(start_time).with_duration(duration)

