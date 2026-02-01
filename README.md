# Ohh Brother

Passive meeting transcription app for macOS with speaker diarization. Runs entirely local - no cloud transcription, no account required.

## Features

- **Local transcription** using NVIDIA Parakeet (no data leaves your machine)
- **Speaker diarization** using NVIDIA NeMo (identifies who said what)
- **Menu bar app** - start/stop recording with a click
- **Markdown transcripts** saved to `~/Library/Application Support/OhhBrother/transcripts/`
- **LLM summarization** (optional) - summarize meetings with Claude or GPT

## Requirements

- macOS 12+ (Apple Silicon or Intel)
- Python 3.9+
- Microphone access
- ~4GB disk space for ML models

## Installation

### From Homebrew (recommended)

```bash
brew install --cask ohh-brother
```

### Manual Installation

1. Download the latest release from GitHub
2. Move `Ohh Brother.app` to `/Applications`

## Post-Installation Setup

The Python ML environment requires one-time setup:

```bash
# Navigate to app resources
cd "/Applications/Ohh Brother.app/Contents/Resources/python"

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies (downloads ~2GB of ML models)
pip install -r requirements.txt
```

## Usage

1. Click the microphone icon in your menu bar
2. Click "Start Recording"
3. Speak - the app captures audio and transcribes in the background
4. Click "Stop Recording" when done
5. Find your transcript in History > [date/time]

### Summarization

1. Open Settings and add your Claude or OpenAI API key
2. After recording, click "Summarize Current"
3. The summary appears in a new window

## Transcript Format

Transcripts are saved as Markdown:

```markdown
# Meeting - 2026-02-01 10:30 AM
Duration: 45 minutes

## Transcript

[00:00:05] **SPEAKER_00**: Let's get started with the Q3 review.
[00:00:15] **SPEAKER_01**: Sure, I have the numbers here...
```

## Development

### Prerequisites

- [Bun](https://bun.sh) (JavaScript runtime)
- Python 3.9+
- Node.js (for Electron)

### Setup

```bash
# Clone repo
git clone https://github.com/OWNER/ohh-brother
cd ohh-brother

# Install JS dependencies
bun install

# Setup Python environment
./scripts/setup-python.sh

# Run in development
bun run dev
```

### Building

```bash
# Build Electron app
bun run build

# Package for distribution
bun run package
```

## Architecture

```
┌─────────────────────────────────────────────┐
│  Electron Menu Bar App (Bun runtime)        │
│  - Menu UI (start/stop, history, settings)  │
│  - LLM API calls for summarization          │
│  - Spawns/manages Python subprocess         │
└──────────────────┬──────────────────────────┘
                   │ spawns & IPC (stdio JSON)
┌──────────────────▼──────────────────────────┐
│  Python Subprocess                          │
│  - Audio capture (sounddevice)              │
│  - Parakeet transcription (NeMo)            │
│  - NeMo speaker diarization                 │
│  - Writes markdown to ~/Library/App Support │
└─────────────────────────────────────────────┘
```

## Privacy

- All transcription happens locally on your machine
- Audio is never sent to any server
- Transcripts are stored only in `~/Library/Application Support/OhhBrother/`
- LLM summarization (if enabled) sends transcript text to Claude or OpenAI

## Troubleshooting

### "Microphone access denied"
Grant microphone access in System Settings > Privacy & Security > Microphone

### Models downloading slowly
First run downloads ~2GB of ML models. This is one-time only.

### High CPU usage
Transcription is CPU-intensive. Processing happens in 10-second batches to balance latency and resource usage.

## License

MIT
