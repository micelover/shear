from datetime import date
import os
import praw
from dotenv import load_dotenv
import requests
import json
from utils.Scalegif import scale_vid
from RedDownloader import RedDownloader
import shutil


load_dotenv()


class RedditBot():

    def __init__(self):
        self.reddit = praw.Reddit(
            client_id=os.getenv('client_id'),
            client_secret=os.getenv('client_secret'),
            user_agent=os.getenv('user_agent'),
        )

        dir_path = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
        self.data_path = os.path.join(dir_path, "data/")
        self.post_data = []
        self.already_posted = []

        #   Check for a posted_already.json file
        self.posted_already_path = os.path.join(
            self.data_path, "posted_already.json")
        if os.path.isfile(self.posted_already_path):
            print("Loading posted_already.json from data folder.")
            with open(self.posted_already_path, "r") as file:
                self.already_posted = json.load(file)

    def get_posts(self, sub="memes"):
        self.post_data = []
        subreddit = self.reddit.subreddit(sub)
        posts = []
        for submission in subreddit.top("day", limit=100):
            if submission.stickied:
                print("Mod Post")
            else:
                posts.append(submission)

        return posts

    def create_data_folder(self):
        today = date.today()
        dt_string = today.strftime("%m%d%Y")
        data_folder_path = os.path.join(self.data_path, f"{dt_string}/")

        check_folder = os.path.isdir(data_folder_path)
        # If folder doesn't exist, then create it.
        if check_folder:
            shutil.rmtree(self.data_path)
        
        os.makedirs(data_folder_path)
        os.makedirs(f"{self.data_path}unedit/")

    def save_image(self, submission, scale=(1280, 720)):
        print("RedditBot1", submission.url.lower())
        # file = RedDownloader.Download(url = submission.url.lower() , output="diddy" , quality = 720, destination="D:/Pictures/")
        # print("Redditbot", submission.url.lower())
        try:
            if submission.post_hint == "hosted:video" and "gifv" not in submission.url.lower():

                # Get all images to ignore
                dt_string = date.today().strftime("%m%d%Y")
                data_folder_path = os.path.join(self.data_path, f"{dt_string}/")
                CHECK_FOLDER = os.path.isdir(data_folder_path)
                # CHECK_FOLDER = os.path.isdir(self.data_path)
                if CHECK_FOLDER and len(self.post_data) < 41 and not submission.over_18 and submission.id not in self.already_posted:
                    print("RedditBot2", len(self.post_data))
                    # Get the image and write the path

                    # path = f"{data_folder_path}"
                    path = f"{self.data_path}"
                    unedit_folder_path = f"{self.data_path}unedit/"
                    unedit_image_path = f"{self.data_path}unedit/Post-{submission.id}{submission.url.lower()[-4:]}.mp4"
                    image_path = f"{path}{dt_string}/Post-{submission.id}{submission.url.lower()[-4:]}.mp4"
                    file = RedDownloader.Download(url=submission.url.lower(), output=f"Post-{submission.id}{submission.url.lower()[-4:]}", destination=unedit_folder_path)
                    scale_vid(image_path, f"{unedit_image_path}", scale)

                    # Could do transforms on images like resize!
                    # add_background(image_path, scale)

                    # cv2.imwrite(f"{image_path}", image)
                    # submission.comment_sort = 'best'

                    # # Get best comment.
                    # best_comment = None
                    # best_comment_2 = None

                    # for top_level_comment in submission.comments:
                    #     # Here you can fetch data off the comment.
                    #     # For the sake of example, we're just printing the comment body.
                    #     if len(top_level_comment.body) <= 140 and "http" not in top_level_comment.body:
                    #         if best_comment is None:
                    #             best_comment = top_level_comment
                    #         else:
                    #             best_comment_2 = top_level_comment
                    #             break

                    # best_comment.reply_sort = "top"
                    # best_comment.refresh()
                    # replies = best_comment.replies

                    # best_reply = None
                    # for top_level_comment in replies:
                    #     # Here you can fetch data off the comment.
                    #     # For the sake of example, we're just printing the comment body.
                    #     best_reply = top_level_comment
                    #     if len(best_reply.body) <= 140 and "http" not in best_reply.body:
                    #         break

                    # if best_reply is not None:
                    #     best_reply = best_reply.body
                    # else:
                    #     best_reply = "MIA"
                    #     if best_comment_2 is not None:
                    #         best_reply = best_comment_2.body

                    data_file = {
                        "image_path": image_path,
                        'id': submission.id,
                        "title": submission.title,
                        "score": submission.score,
                        "18": submission.over_18,
                        # "Best_comment": best_comment.body,
                        # "best_reply": best_reply
                    }

                    self.post_data.append(data_file)
                    self.already_posted.append(submission.id)
                    with open(f"{data_folder_path}{submission.id}.json", "w") as outfile:
                        json.dump(data_file, outfile)
                    with open(self.posted_already_path, "w") as outfile:
                        json.dump(self.already_posted, outfile)
                else:
                    return None
        except:
            print("ERROR")
            
