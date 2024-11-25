from PIL import Image, ImageSequence
import moviepy
from moviepy.editor import *



def scale_vid(path, unedit_path, scale, new_path=None):
    print("scale_vid", unedit_path)
    clip = VideoFileClip(unedit_path)
    back = ImageClip("source/background/seeyjj.jpg")
    reClip = clip.resize(height=720) 
    # reClip = clip

    duration = reClip.duration
    final = CompositeVideoClip([back, clip.set_position("center")])
    if duration<20:
        final = final.set_duration(duration)
    else:
        final = final.set_duration(20)

    final.write_videofile(path)


# def add_background_vid(back, vid):
#     # vidCopy = VideoFileClip(vid)
#     vidCopy = vid.copy()
#     backCopy = back.copy()
#     # overlay = ImageClip(backCopy).set_pos(("center","center"))
#     final_video = CompositeVideoClip([back, vid])  
#     return final_video

# if __name__ == "__main__":
#     scale_gif(f"Post-qtehpj.gif", (1280,720),"test.gif")