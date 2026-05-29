import customtkinter as ctk
import tkinter as tk
import threading
import math
import time
import sounddevice as sd
import scipy.io.wavfile as wav
import numpy as np
import threading
import whisper
import anthropic
from dotenv import load_dotenv
import os
import win32com.client
import re


load_dotenv()
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
whisper_model = whisper.load_model("base")
speaker_english = win32com.client.Dispatch("SAPI.SpVoice")
speaker_spanish = win32com.client.Dispatch("SAPI.SpVoice")


for voice in speaker_english.GetVoices():
    if "Zira" in voice.GetDescription():
        speaker_english.Voice = voice
        break

for voice in speaker_spanish.GetVoices():
    if "Helena" in voice.GetDescription():
        speaker_spanish.Voice = voice
        break



SAMPLE_RATE = 44100
AUDIO_FILE = "input.wav"
conversation_history = []



def record_audio():
    
    chunks = []
    stop_flag = threading.Event()

    def callback(indata, frame_count, time_info, status):
        if not stop_flag.is_set():
            chunks.append(indata.copy())

    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, callback=callback):
        input("Press Enter to start recording...")
        input("Press Enter to stop...")
        stop_flag.set()

    try:
        audio = np.concatenate(chunks, axis=0)
        wav.write(AUDIO_FILE, SAMPLE_RATE, audio)
        print("Audio saved.")
        return AUDIO_FILE
    except Exception as e:
        print(f"Error saving audio: {e}")
        return None
    

def transcribe(file_path):
    result = whisper_model.transcribe(file_path, language="es")
    transcript = result["text"]
    return transcript

def claude(transcript):
    conversation_history.append({"role": "user", "content": transcript})

    response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=1024,
    system="""You are an encouraging and patient Spanish tutor having a natural spoken conversation with a beginner to intermediate English-speaking student.

Your response must always follow this exact format with no deviation:

[SPEED:N][EN]correction text here[ES]spanish reply here

Rules for each part:

[SPEED:N] — Always start your response with this tag. N is an integer from -10 to 0. This is consumed silently by the app and is never spoken, so never reference it. Use 0 for normal speed. Only go negative if the student explicitly asks to repeat something, asks to slow down, or clearly expresses confusion — pick the value that fits how lost they seem.

[EN] — Write any corrections here in English as warm natural tutor speech, as if mid-conversation — for example "just a small one, in the past tense you say tuve not tenía there" or "remember the word order flips in questions". Do not announce it as a correction. Skip accent errors since the student cannot type them. If there are no corrections, leave this section completely empty — just write [EN][ES] with nothing between them.

[ES] — Your Spanish conversational reply. 2 to 4 sentences, beginner to intermediate level, everyday vocabulary. If the student wrote in English gently encourage them to try in Spanish. Match complexity to their confidence. Write as completely natural spoken Spanish — no formatting, no symbols, no brackets, nothing that would sound unnatural read aloud.""",
    messages=conversation_history
    )
    reply = response.content[0].text
    conversation_history.append({"role": "assistant", "content": reply})
    return reply



def tts(reply: str, rate: int = 0):
    chunks = re.split(r'(\[EN\]|\[ES\])', reply)
    current_speaker = speaker_spanish  # default to Spanish
    
    for chunk in chunks:
        chunk = chunk.strip()
        if chunk == "[EN]":
            current_speaker = speaker_english
        elif chunk == "[ES]":
            current_speaker = speaker_spanish
        elif chunk:
            current_speaker.Rate = rate
            current_speaker.Speak(chunk)

"""

def main():

    while True:
        audio_file = record_audio()
        transcript = transcribe(audio_file)
        reply = claude(transcript)
        tts(reply)
        
"""

def main():
    while True:
        transcript = "hola, cómo estás"
        reply = claude(transcript)
        tts(reply)


if __name__ == "__main__":
    main()






#prompt using eng and esp voices together - doesnt flow very well but works 
"""You are an encouraging and patient Spanish tutor having a real conversation with a beginner to intermediate English-speaking student.

You must always respond using exactly this structure, using [EN] and [ES] tags to indicate which language should be spoken aloud:

[EN] Any corrections to grammar or vocabulary mistakes in a warm reminder-style tone. When you need to say a Spanish word or phrase as part of the correction, wrap just that part in [ES] and [EN] tags so it is spoken in the Spanish voice — for example: [EN] just a small one, remember it's [ES] estuve [EN] not [ES] fui [EN] in that context. Then carry on in English. For example: "[EN] just a small one — remember it's [ES] estuve [EN] not [ES] fui [EN] in that context." Only flag real mistakes, not minor punctuation or accents. If there are no mistakes, skip this entirely.
[ES] Your Spanish conversational reply. Keep language at beginner to intermediate level, 2 to 4 sentences, everyday vocabulary. If the student wrote in English, gently encourage them to try in Spanish.

Rules:
- You can switch between [EN] and [ES] multiple times if it helps — for example give a correction in [EN] then immediately model the correct phrase in [ES] so they hear it spoken properly
- If the student is struggling, you can explain more in [EN] before continuing in [ES]
- If the student is doing well, stay almost entirely in [ES]
- The [ES] and [EN] tags will be read by a TTS engine so never use bullet points, brackets, symbols or any formatting — just natural spoken sentences as if a real conversation betweena tutor and student is taking place
- Never include the tags themselves in a way that sounds unnatural — the text after each tag should flow as if spoken aloud"""