# Tutor AI

A small desktop app for practising spoken Spanish. You type or talk to it and it
talks back — replies in Spanish, corrections in English. Uses Claude for the
conversation, Whisper for speech-to-text, and the OS's built-in voices for output.

## Setup

Needs Python 3.11+ and an Anthropic API key.

```
cd "Spanish Tutor API/spanish_tutor"
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Then make a `.env` file in that folder with your key:

```
ANTHROPIC_API_KEY=sk-ant-...
```

## Running

```
python tutorGUI.py
```

Type in the box or press the mic button to talk. Replies are printed and spoken aloud.

## Notes

- TTS uses whatever the OS provides — `say` on macOS, SAPI on Windows. On Windows
  set `SPEECH = True` at the top of `tutor.py` to enable the voices (needs pywin32).
- First run downloads a ~140MB Whisper model. If your network does HTTPS inspection
  it'll fail on a cert error — grab it with curl into `~/.cache/whisper/` instead.
- Voices live in `tutor.py` (`MAC_VOICE_ES` / `MAC_VOICE_EN`); `say -v '?'` lists them.
- Mic button greyed out = whisper/sounddevice missing, or the model didn't download.
- Running with the wrong Python is the usual cause of import errors — use the venv.

## Files

- `tutor.py` — Claude call + speech in/out
- `tutorGUI.py` — the GUI
- `db.py` — progress logging, not wired up yet
