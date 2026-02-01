# Ohh Brother - Project Context

Passive meeting transcription menu bar app for macOS.

## Tech Stack

- **Electron** - menu bar app (built with Bun)
- **Python** - audio capture + transcription subprocess
- **faster-whisper** - local speech-to-text (no cloud, no auth)

## Project Structure

```
electron/          # Electron main process
  main.ts          # Menu bar app, spawns Python
  settings.ts      # Config management
  preload.ts       # IPC bridge
python/            # Python subprocess
  transcriber.py   # Main daemon, IPC with Electron
  parakeet_wrapper.py  # Whisper transcription
  audio.py         # Mic capture with sounddevice
  diarize.py       # Stub (no speaker separation)
src/renderer/      # Settings UI HTML
```

## Key Commands

```bash
bun install              # Install JS deps
bun run dev              # Build + run Electron
bun run build            # Build only
bun run package          # Package for distribution
```

## Python Setup

```bash
cd python
python3.11 -m venv venv
./venv/bin/pip install -r requirements.txt
```

## How It Works

1. Electron menu bar app spawns Python subprocess
2. Python captures mic audio in chunks (sounddevice)
3. Every 5s, audio batch sent to faster-whisper
4. Transcript appended to markdown file in real-time
5. IPC over stdio (JSON messages)

## Audio Settings

- Sample rate: 16kHz (hardcoded, standard for speech recognition)
- Batch interval: 5 seconds
- VAD disabled (captures ambient audio)

## Transcripts

Saved to `~/Library/Application Support/OhhBrother/transcripts/`

Format:
```markdown
# Meeting - 2026-02-01 10:30 AM

[00:05] First transcribed sentence.
[00:12] Next sentence appears here.
```

## No Speaker Diarization

Speaker separation was removed - all open-source options require HuggingFace auth or don't support Python 3.11. Could be added back when a good library exists.
