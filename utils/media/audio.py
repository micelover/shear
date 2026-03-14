from utils.core.config import DIR_PATH, DATA_PATH, SOURCE_PATH, UTILS_PATH
from utils.core.settings import SCRIPT_LENGTH
from utils.core.edit import open_ai_generation, open_ai_tts, inworld_tts, create_srt_from_transcription, transcribe_audio

from moviepy import AudioFileClip, concatenate_audioclips
import os
from dotenv import load_dotenv
from datetime import datetime
import re


load_dotenv()

class Audio():

    def __init__(self, pipeline):
        self.pipeline = pipeline

        now = datetime.now()
        self.year = now.year

        with open(f'{UTILS_PATH}/prompts/script.txt', 'r') as file:
            self.orignial_script_prompt = file.read()

        with open(f'{UTILS_PATH}/prompts/instructions/audio_instructions.txt', 'r') as file:
            self.audio_instructions = file.read()


    def _create_script(self, product):
        script_prompt = (self.orignial_script_prompt
            .replace("{product}", product)
            .replace("{low}", SCRIPT_LENGTH["low"])
            .replace("{high}", SCRIPT_LENGTH["high"])
        )
        script = open_ai_generation(script_prompt, model="gpt-4.1", temperature=0.5)

        return script

        # product.script = script

    def chunk_text(self, text, max_chars=1900):
        """
        Splits text into <= max_chars chunks,
        breaking at sentence boundaries when possible.
        """

        # Clean whitespace/newlines
        text = " ".join(text.split())

        # Split into sentences
        sentences = re.split(r'(?<=[.!?]) +', text)

        chunks = []
        current_chunk = ""

        for sentence in sentences:
            if len(current_chunk) + len(sentence) + 1 <= max_chars:
                current_chunk += (" " + sentence if current_chunk else sentence)
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = sentence

        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    def _generate_subtitles(self, audio_path, *, word_save_path=None, sentence_save_path=None):
        if not word_save_path and not sentence_save_path:
            return None
        
        return_words = word_save_path is not None
        return_sentences = sentence_save_path is not None

        transcription = transcribe_audio(audio_path)
 
        srt_dict = create_srt_from_transcription(transcription, return_words=return_words, return_sentences=return_sentences)
        if return_words:
            srt_dict["words"].save(word_save_path)

        if return_sentences:
            srt_dict["sentences"].save(sentence_save_path)

            print("Subtitles created successfully.")

    

    def generate_audio(self, product, paths):
        script = self._create_script(product.simple_title)
        self.pipeline.script = script
        script = script.replace("\n", " ")
        print(script)

        open_ai_tts(script=script, save_path=paths['audio'], instructions=self.audio_instructions)

        chunks = self.chunk_text(script)
        all_parts = []

        for i, chunk in enumerate(chunks):
            output_file = f"{paths['audio_dir']}/part_{i}.wav"
            inworld_tts(chunk, output_file, id="Alex", model="inworld-tts-1.5-mini", temperature=0.9)
            all_parts.append(AudioFileClip(output_file))

        print()

        concatenate_audio = concatenate_audioclips(all_parts)
        concatenate_audio.write_audiofile(paths['audio'])
        concatenate_audio.close()
        for part in all_parts:
            part.close()

        self._generate_subtitles(paths['audio'], word_save_path=paths['words_srt'], sentence_save_path=paths['sentences_srt'])




