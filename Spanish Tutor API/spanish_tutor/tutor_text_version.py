import time
import win32com.client
from tutor import claude
import re

_speaker = win32com.client.Dispatch("SAPI.SpVoice")
for _voice in _speaker.GetVoices():
    if "Helena" in _voice.GetDescription():
        _speaker.Voice = _voice
        break


def tts(text: str, rate: int = 0):
    _speaker.Rate = max(-10, min(10, rate))
    _speaker.Speak(text)
    _speaker.Rate = 0


BANNER = """
╔════════════════════════════════════════╗
║      Spanish Tutor — Text Mode         ║
║   Type in English or Spanish to chat.  ║
║   The tutor will speak its replies.    ║
║   Type  'quit'  at any time to exit.   ║
╚════════════════════════════════════════╝
"""


def main():
    print(BANNER)

    while True:
        try:
            user_input = input("You › ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\nAdiós!")
            break

        if not user_input:
            continue

        if user_input.lower() in ("quit", "exit", "q", "adios", "adiós"):
            print("\nAdiós!")
            break

        print("\nTutor is thinking...\n")
        full_reply = claude(user_input)

        # extract [SPEED:N] silently — never spoken
        speed = 0
        speed_match = re.match(r'^\[SPEED:(-?\d+)\]', full_reply.strip())
        if speed_match:
            speed = max(-10, min(0, int(speed_match.group(1))))
            full_reply = full_reply[speed_match.end():].strip()

        # parse [EN] and [ES] chunks
        chunks = re.split(r'(\[EN\]|\[ES\])', full_reply)
        current_lang = "ES"

        for chunk in chunks:
            chunk = chunk.strip()
            if chunk == "[EN]":
                current_lang = "EN"
            elif chunk == "[ES]":
                current_lang = "ES"
            elif chunk:
                if current_lang == "EN":
                    print(f"── {chunk}\n")
                    tts(chunk, rate=0)
                else:
                    print(f"Tutor › {chunk}\n")
                    tts(chunk, rate=speed)

        print("-" * 50 + "\n")


if __name__ == "__main__":
    main()
