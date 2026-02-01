#!/usr/bin/env python3
"""Main transcription daemon with IPC for Electron."""

import argparse
import json
import os
import sys
import signal
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from audio import AudioCapture, AudioBuffer
from parakeet_wrapper import Transcriber
from diarize import Diarizer, merge_transcript_with_speakers


class TranscriptionDaemon:
    """Main transcription process that communicates with Electron via stdio."""

    def __init__(
        self,
        output_dir: Path,
        sample_rate: int = 16000,
        process_interval: float = 10.0,  # Process every 10 seconds
    ):
        self.output_dir = output_dir
        self.sample_rate = sample_rate
        self.process_interval = process_interval

        self.audio_capture = AudioCapture(sample_rate=sample_rate)
        self.audio_buffer = AudioBuffer(sample_rate=sample_rate)
        self.transcriber = Transcriber(sample_rate=sample_rate)
        self.diarizer = Diarizer(sample_rate=sample_rate)

        self._recording = False
        self._current_session: Optional[str] = None
        self._session_start: Optional[datetime] = None
        self._all_segments: list[dict] = []
        self._total_audio_duration: float = 0.0
        self._running = True
        self._processing_thread: Optional[threading.Thread] = None

        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def send_message(self, msg: dict) -> None:
        """Send JSON message to Electron via stdout."""
        print(json.dumps(msg), flush=True)

    def send_status(self) -> None:
        """Send current status to Electron."""
        self.send_message(
            {
                "type": "status",
                "recording": self._recording,
                "duration": self._total_audio_duration,
                "session": self._current_session,
            }
        )

    def send_transcript(self, segment: dict) -> None:
        """Send a transcript segment to Electron."""
        self.send_message(
            {
                "type": "transcript",
                "speaker": segment.get("speaker", "UNKNOWN"),
                "text": segment["text"],
                "start": segment["start"],
                "end": segment["end"],
            }
        )

    def send_error(self, message: str) -> None:
        """Send an error message to Electron."""
        self.send_message({"type": "error", "message": message})

    def _get_session_filename(self) -> str:
        """Generate filename for current session."""
        if self._session_start:
            return self._session_start.strftime("%Y-%m-%d_%H-%M")
        return datetime.now().strftime("%Y-%m-%d_%H-%M")

    def _save_transcript(self) -> None:
        """Save current transcript to markdown file."""
        if not self._all_segments:
            return

        filename = self._get_session_filename() + ".md"
        filepath = self.output_dir / filename

        # Calculate duration
        duration_mins = int(self._total_audio_duration // 60)
        duration_str = f"{duration_mins} minutes" if duration_mins > 0 else "< 1 minute"

        # Build markdown content
        lines = [
            f"# Meeting - {self._session_start.strftime('%Y-%m-%d %I:%M %p') if self._session_start else 'Unknown'}",
            f"Duration: {duration_str}",
            "",
            "## Transcript",
            "",
        ]

        for seg in self._all_segments:
            timestamp = self._format_timestamp(seg["start"])
            speaker = seg.get("speaker", "UNKNOWN")
            text = seg["text"].strip()
            lines.append(f"[{timestamp}] **{speaker}**: {text}")
            lines.append("")

        filepath.write_text("\n".join(lines))

        self.send_message(
            {
                "type": "saved",
                "path": str(filepath),
                "segments": len(self._all_segments),
            }
        )

    def _format_timestamp(self, seconds: float) -> str:
        """Format seconds as HH:MM:SS or MM:SS."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"

    def _process_audio(self) -> None:
        """Process accumulated audio buffer."""
        audio = self.audio_buffer.get_and_clear()
        if len(audio) == 0:
            return

        audio_duration = len(audio) / self.sample_rate
        offset = self._total_audio_duration

        try:
            # Transcribe
            transcript_segments = self.transcriber.transcribe_streaming(audio, offset)

            # Diarize
            speaker_segments = self.diarizer.diarize_with_offset(audio, offset)

            # Merge
            merged = merge_transcript_with_speakers(transcript_segments, speaker_segments)

            # Add to session and send to Electron
            for seg in merged:
                self._all_segments.append(seg)
                self.send_transcript(seg)

            self._total_audio_duration += audio_duration

            # Save periodically
            self._save_transcript()

        except Exception as e:
            self.send_error(f"Processing error: {str(e)}")

    def _processing_loop(self) -> None:
        """Background thread for processing audio."""
        while self._running and self._recording:
            # Collect audio chunks
            while self._recording:
                chunk = self.audio_capture.get_chunk(timeout=0.1)
                if chunk is not None:
                    self.audio_buffer.append(chunk)

                # Check if we have enough audio to process
                if self.audio_buffer.get_duration() >= self.process_interval:
                    break

            if self._recording:
                self._process_audio()
                self.send_status()

    def start_recording(self) -> None:
        """Start a new recording session."""
        if self._recording:
            return

        self._recording = True
        self._session_start = datetime.now()
        self._current_session = self._get_session_filename()
        self._all_segments = []
        self._total_audio_duration = 0.0

        self.audio_capture.start()
        self._processing_thread = threading.Thread(target=self._processing_loop)
        self._processing_thread.start()

        self.send_status()
        self.send_message({"type": "started", "session": self._current_session})

    def stop_recording(self) -> None:
        """Stop the current recording session."""
        if not self._recording:
            return

        self._recording = False
        self.audio_capture.stop()

        # Process any remaining audio
        if self._processing_thread:
            self._processing_thread.join(timeout=5.0)
        self._process_audio()

        # Final save
        self._save_transcript()

        self.send_message(
            {
                "type": "stopped",
                "session": self._current_session,
                "segments": len(self._all_segments),
                "duration": self._total_audio_duration,
            }
        )

        self._current_session = None
        self._session_start = None

    def handle_command(self, cmd: dict) -> None:
        """Handle a command from Electron."""
        command = cmd.get("command")

        if command == "start":
            self.start_recording()
        elif command == "stop":
            self.stop_recording()
        elif command == "status":
            self.send_status()
        elif command == "quit":
            self.stop_recording()
            self._running = False
        else:
            self.send_error(f"Unknown command: {command}")

    def run(self) -> None:
        """Main loop - read commands from stdin."""
        # Handle signals
        def signal_handler(sig, frame):
            self.stop_recording()
            self._running = False
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        self.send_message({"type": "ready"})

        while self._running:
            try:
                line = sys.stdin.readline()
                if not line:
                    break

                line = line.strip()
                if not line:
                    continue

                cmd = json.loads(line)
                self.handle_command(cmd)

            except json.JSONDecodeError as e:
                self.send_error(f"Invalid JSON: {str(e)}")
            except Exception as e:
                self.send_error(f"Error: {str(e)}")

        # Cleanup
        self.stop_recording()


def test_mode():
    """Run a quick test of the transcription pipeline."""
    print("Running transcription test...", file=sys.stderr)

    import numpy as np
    from audio import AudioCapture, AudioBuffer

    print("1. Testing audio capture for 5 seconds...", file=sys.stderr)
    capture = AudioCapture()
    buffer = AudioBuffer()

    capture.start()
    start = time.time()
    while time.time() - start < 5:
        chunk = capture.get_chunk(timeout=0.1)
        if chunk is not None:
            buffer.append(chunk)
        print(f"\r   Captured: {buffer.get_duration():.1f}s", end="", file=sys.stderr)
    capture.stop()
    print(file=sys.stderr)

    audio = buffer.get_and_clear()
    print(f"   Audio shape: {audio.shape}", file=sys.stderr)

    if len(audio) == 0:
        print("ERROR: No audio captured. Check microphone permissions.", file=sys.stderr)
        return

    print("2. Testing transcription...", file=sys.stderr)
    transcriber = Transcriber()
    segments = transcriber.transcribe(audio)
    print(f"   Transcript segments: {len(segments)}", file=sys.stderr)
    for seg in segments:
        print(f"   [{seg['start']:.1f}-{seg['end']:.1f}] {seg['text']}", file=sys.stderr)

    hf_token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN")
    if hf_token:
        print("3. Testing diarization...", file=sys.stderr)
        diarizer = Diarizer()
        speaker_segments = diarizer.diarize(audio)
        print(f"   Speaker segments: {len(speaker_segments)}", file=sys.stderr)
        for seg in speaker_segments:
            print(
                f"   [{seg['start']:.1f}-{seg['end']:.1f}] {seg['speaker']}",
                file=sys.stderr,
            )
    else:
        print("3. Skipping diarization (no HF_TOKEN)", file=sys.stderr)

    print("\nTest complete!", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="Ohh Brother Transcription Daemon")
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run a quick test of the transcription pipeline",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=os.path.expanduser(
            "~/Library/Application Support/OhhBrother/transcripts"
        ),
        help="Directory to save transcripts",
    )
    parser.add_argument(
        "--sample-rate",
        type=int,
        default=16000,
        help="Audio sample rate (default: 16000)",
    )
    parser.add_argument(
        "--process-interval",
        type=float,
        default=10.0,
        help="Process audio every N seconds (default: 10)",
    )

    args = parser.parse_args()

    if args.test:
        test_mode()
        return

    daemon = TranscriptionDaemon(
        output_dir=Path(args.output_dir),
        sample_rate=args.sample_rate,
        process_interval=args.process_interval,
    )
    daemon.run()


if __name__ == "__main__":
    main()
