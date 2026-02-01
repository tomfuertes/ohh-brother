"""Transcription wrapper using faster-whisper."""

import os
import tempfile
from typing import Optional

import numpy as np

# Lazy imports to speed up initial load
_whisper_model = None


def get_whisper_model():
    """Lazily load the Whisper model."""
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel

        # Use base model - good balance of speed and accuracy
        # Options: tiny, base, small, medium, large-v2, large-v3
        _whisper_model = WhisperModel("base", device="cpu", compute_type="int8")
    return _whisper_model


class Transcriber:
    """Transcribes audio using faster-whisper."""

    def __init__(self):
        self._model = None

    def _ensure_model(self) -> None:
        """Load model on first use."""
        if self._model is None:
            self._model = get_whisper_model()

    def transcribe(self, audio: np.ndarray) -> list[dict]:
        """
        Transcribe audio and return segments with timestamps.

        Args:
            audio: Audio data as float32 numpy array

        Returns:
            List of segments: [{"text": str, "start": float, "end": float}, ...]
        """
        self._ensure_model()

        if len(audio) == 0:
            return []

        # Ensure audio is the right shape
        if audio.ndim > 1:
            audio = audio.flatten()

        # faster-whisper can transcribe from numpy array directly
        segments_iter, info = self._model.transcribe(
            audio,
            beam_size=5,
            word_timestamps=True,
            vad_filter=False,  # Disabled to capture ambient/speaker audio
        )

        segments = []
        for segment in segments_iter:
            # Use segment-level (sentence/phrase), not word-level
            segments.append({
                "text": segment.text.strip(),
                "start": segment.start,
                "end": segment.end,
            })

        return segments

    def transcribe_streaming(
        self, audio: np.ndarray, offset: float = 0.0
    ) -> list[dict]:
        """
        Transcribe audio with a time offset applied to timestamps.

        Args:
            audio: Audio data
            offset: Time offset to add to all timestamps

        Returns:
            Segments with adjusted timestamps
        """
        segments = self.transcribe(audio)
        for seg in segments:
            seg["start"] += offset
            seg["end"] += offset
        return segments


if __name__ == "__main__":
    print("Testing faster-whisper transcription...")
    print("Loading model (this may take a moment on first run)...")

    transcriber = Transcriber()

    # Generate a test tone (1 second of sine wave)
    # In real usage, this would be actual speech
    duration = 1.0
    t = np.linspace(0, duration, int(16000 * duration), dtype=np.float32)
    test_audio = 0.5 * np.sin(2 * np.pi * 440 * t)  # 440 Hz tone

    print("Transcribing test audio...")
    segments = transcriber.transcribe(test_audio)
    print(f"Segments: {segments}")

    if not segments:
        print("(No speech detected in test tone - this is expected)")
