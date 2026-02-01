"""Speaker diarization stub - no speaker separation."""

import numpy as np

SAMPLE_RATE = 16000  # Standard for speech recognition


class Diarizer:
    """Stub diarizer - no-op."""

    def __init__(self):
        pass

    def diarize(self, audio: np.ndarray) -> list[dict]:
        """Return empty - no speaker separation."""
        return []

    def diarize_with_offset(self, audio: np.ndarray, offset: float = 0.0) -> list[dict]:
        """Return empty - no speaker separation."""
        return []


def merge_transcript_with_speakers(
    transcript_segments: list[dict],
    speaker_segments: list[dict],
) -> list[dict]:
    """Pass through transcript segments without speaker labels."""
    return [
        {
            "text": trans["text"],
            "start": trans["start"],
            "end": trans["end"],
        }
        for trans in transcript_segments
    ]
