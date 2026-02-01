"""Parakeet transcription wrapper using NVIDIA NeMo."""

import os
import tempfile
from typing import Optional

import numpy as np

# Lazy imports to speed up initial load
_asr_model = None


def get_asr_model():
    """Lazily load the Parakeet ASR model."""
    global _asr_model
    if _asr_model is None:
        import nemo.collections.asr as nemo_asr

        # Use Parakeet TDT model - good balance of speed and accuracy
        _asr_model = nemo_asr.models.ASRModel.from_pretrained(
            "nvidia/parakeet-tdt-0.6b"
        )
        _asr_model.eval()
    return _asr_model


class Transcriber:
    """Transcribes audio using Parakeet."""

    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate
        self._model = None

    def _ensure_model(self) -> None:
        """Load model on first use."""
        if self._model is None:
            self._model = get_asr_model()

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

        # Write to temp file (NeMo expects file paths)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            temp_path = f.name
            import scipy.io.wavfile as wav

            # Convert to int16 for wav file
            audio_int16 = (audio * 32767).astype(np.int16)
            wav.write(f.name, self.sample_rate, audio_int16)

        try:
            # Transcribe with timestamps
            result = self._model.transcribe(
                [temp_path],
                return_hypotheses=True,
            )

            segments = []

            # Handle different result formats
            if hasattr(result, "__iter__"):
                hypotheses = result[0] if result else []
            else:
                hypotheses = [result]

            for hyp in hypotheses:
                if hasattr(hyp, "timestep") and hyp.timestep:
                    # Has word-level timestamps
                    for word_info in hyp.timestep:
                        segments.append(
                            {
                                "text": word_info.word,
                                "start": word_info.start_offset,
                                "end": word_info.end_offset,
                            }
                        )
                elif hasattr(hyp, "text"):
                    # Just full text, estimate timestamps
                    duration = len(audio) / self.sample_rate
                    segments.append(
                        {
                            "text": hyp.text,
                            "start": 0.0,
                            "end": duration,
                        }
                    )
                elif isinstance(hyp, str):
                    duration = len(audio) / self.sample_rate
                    segments.append(
                        {
                            "text": hyp,
                            "start": 0.0,
                            "end": duration,
                        }
                    )

            return segments

        finally:
            os.unlink(temp_path)

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
    print("Testing Parakeet transcription...")
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
