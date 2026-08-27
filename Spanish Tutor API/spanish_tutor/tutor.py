import re
import os
import platform
import shutil
import subprocess
import anthropic
from dotenv import load_dotenv

# ── Voice OUTPUT (text-to-speech) ───────────────────────────────────────────
# Windows uses the SAPI voices (Zira/Helena) and needs pywin32 — set SPEECH =
# True on Windows to turn them on. macOS uses the built-in `say` command
# instead (handled below), so leave SPEECH = False there.
SPEECH = False

if SPEECH:
    import win32com.client

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

# Pick the speech engine:
#   Windows -> SAPI (needs SPEECH=True above)
#   macOS   -> the built-in `say` command (Mónica for Spanish, Samantha for English)
#   other   -> just print the reply
if SPEECH:
    TTS_BACKEND = "sapi"
elif platform.system() == "Darwin" and shutil.which("say"):
    TTS_BACKEND = "say"
else:
    TTS_BACKEND = "print"

MAC_VOICE_ES = "Mónica"      # `say -v '?'` lists other options
MAC_VOICE_EN = "Samantha"


# ── Voice INPUT (microphone -> text) ────────────────────────────────────────
# Works on any OS as long as whisper + sounddevice are installed. If they're
# missing (or fail to load) MIC stays False, the mic button is disabled, and
# text input still works.
try:
    import numpy as np
    import sounddevice as sd
    import scipy.io.wavfile as wav
    import whisper

    whisper_model = whisper.load_model("base")
    MIC = True
except Exception as exc:   # any import/model-load failure just disables the mic
    MIC = False
    print(f"Microphone disabled — speech-to-text unavailable ({exc})")


load_dotenv()
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))



SAMPLE_RATE = 16000   # whisper's native rate — record here so no resampling is needed
AUDIO_FILE = "input.wav"
conversation_history = []



class Recorder:
    """Non-blocking mic recorder for the GUI.

    Call start() to begin capturing, then stop() to finish and write the
    audio to a wav file. stop() returns the file path, or None if nothing
    was captured (e.g. the mic was toggled off instantly).
    """

    def __init__(self, samplerate: int = SAMPLE_RATE):
        self.samplerate = samplerate
        self._chunks = []
        self._stream = None

    def start(self) -> None:
        self._chunks = []

        def callback(indata, frame_count, time_info, status):
            self._chunks.append(indata.copy())

        self._stream = sd.InputStream(
            samplerate=self.samplerate, channels=1, callback=callback
        )
        self._stream.start()

    def stop(self, file_path: str = AUDIO_FILE):
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        if not self._chunks:
            return None

        audio = np.concatenate(self._chunks, axis=0)
        wav.write(file_path, self.samplerate, audio)
        return file_path


def transcribe(file_path: str) -> str:
    # Decode the wav ourselves and pass whisper a float32 array, so we don't
    # need ffmpeg installed (whisper only shells out to ffmpeg for file paths).
    sr, audio = wav.read(file_path)
    if np.issubdtype(audio.dtype, np.integer):
        audio = audio.astype(np.float32) / np.iinfo(audio.dtype).max
    else:
        audio = audio.astype(np.float32)
    if audio.ndim > 1:                     # stereo -> mono
        audio = audio.mean(axis=1)
    result = whisper_model.transcribe(audio, language="es")
    return result["text"]


def claude(transcript: str) -> str:
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


def strip_speed(full_reply: str):
    """Pull the leading [SPEED:N] tag off a reply.

    Returns (speed, body) where speed is clamped to -10..0 and body is the
    reply with the tag removed. [EN]/[ES] tags are left intact for tts().
    """
    speed = 0
    body = full_reply.strip()
    match = re.match(r'^\[SPEED:(-?\d+)\]', body)
    if match:
        speed = max(-10, min(0, int(match.group(1))))
        body = body[match.end():].strip()
    return speed, body


def tts(reply: str, rate: int = 0):
    """Speak (or print) a reply, switching language per [EN]/[ES] tag."""
    lang = "ES"  # default to Spanish
    for chunk in re.split(r'(\[EN\]|\[ES\])', reply):
        chunk = chunk.strip()
        if chunk == "[EN]":
            lang = "EN"
        elif chunk == "[ES]":
            lang = "ES"
        elif chunk:
            _speak(chunk, lang, rate)


def _speak(text: str, lang: str, rate: int) -> None:
    if TTS_BACKEND == "sapi":
        speaker = speaker_english if lang == "EN" else speaker_spanish
        speaker.Rate = rate
        speaker.Speak(text)

    elif TTS_BACKEND == "say":
        # Always print the transcript too, so you see and hear the reply.
        print(("  (correction) " if lang == "EN" else "Tutor › ") + text)
        voice = MAC_VOICE_EN if lang == "EN" else MAC_VOICE_ES
        wpm = max(90, 175 + rate * 9)   # rate 0 -> ~175 wpm, negative = slower
        subprocess.run(["say", "-v", voice, "-r", str(wpm), text])

    else:  # print only
        print(("  (correction) " if lang == "EN" else "Tutor › ") + text)




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
