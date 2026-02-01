"""Speaker diarization using NVIDIA NeMo."""

import os
import tempfile
from typing import Optional

import numpy as np

# Lazy imports
_diarization_model = None


def get_diarization_model():
    """Lazily load the NeMo diarization model."""
    global _diarization_model
    if _diarization_model is None:
        from nemo.collections.asr.models import ClusteringDiarizer

        # NeMo diarization config
        config = {
            "diarizer": {
                "manifest_filepath": None,  # Set per-call
                "out_dir": None,  # Set per-call
                "oracle_vad": False,
                "collar": 0.25,
                "ignore_overlap": True,
                "vad": {
                    "model_path": "vad_multilingual_marblenet",
                    "parameters": {
                        "onset": 0.8,
                        "offset": 0.6,
                        "min_duration_on": 0.3,
                        "min_duration_off": 0.3,
                    },
                },
                "speaker_embeddings": {
                    "model_path": "titanet_large",
                    "parameters": {
                        "window_length_in_sec": 1.5,
                        "shift_length_in_sec": 0.75,
                        "multiscale_weights": [1, 1, 1],
                        "save_embeddings": False,
                    },
                },
                "clustering": {
                    "parameters": {
                        "oracle_num_speakers": False,
                        "max_num_speakers": 8,
                        "enhanced_count_thres": 80,
                        "max_rp_threshold": 0.25,
                        "sparse_search_volume": 30,
                    },
                },
            }
        }

        _diarization_model = config

    return _diarization_model


class Diarizer:
    """Performs speaker diarization on audio using NeMo."""

    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate
        self._initialized = False

    def _run_diarization(self, audio_path: str, output_dir: str) -> list[dict]:
        """Run NeMo clustering diarizer on an audio file."""
        from nemo.collections.asr.models import ClusteringDiarizer
        from omegaconf import OmegaConf
        import json

        # Create manifest file (NeMo requirement)
        manifest_path = os.path.join(output_dir, "manifest.json")
        with open(manifest_path, "w") as f:
            manifest_entry = {
                "audio_filepath": audio_path,
                "offset": 0,
                "duration": None,
                "label": "infer",
                "text": "-",
                "num_speakers": None,
                "rttm_filepath": None,
                "uem_filepath": None,
            }
            f.write(json.dumps(manifest_entry) + "\n")

        # Configure diarizer
        config = OmegaConf.create({
            "diarizer": {
                "manifest_filepath": manifest_path,
                "out_dir": output_dir,
                "oracle_vad": False,
                "collar": 0.25,
                "ignore_overlap": True,
                "vad": {
                    "model_path": "vad_multilingual_marblenet",
                    "parameters": {
                        "onset": 0.8,
                        "offset": 0.6,
                        "min_duration_on": 0.3,
                        "min_duration_off": 0.3,
                    },
                },
                "speaker_embeddings": {
                    "model_path": "titanet_large",
                    "parameters": {
                        "window_length_in_sec": 1.5,
                        "shift_length_in_sec": 0.75,
                        "multiscale_weights": [1, 1, 1],
                        "save_embeddings": False,
                    },
                },
                "clustering": {
                    "parameters": {
                        "oracle_num_speakers": False,
                        "max_num_speakers": 8,
                        "enhanced_count_thres": 80,
                        "max_rp_threshold": 0.25,
                        "sparse_search_volume": 30,
                    },
                },
            }
        })

        # Run diarization
        diarizer = ClusteringDiarizer(cfg=config)
        diarizer.diarize()

        # Parse RTTM output
        rttm_path = os.path.join(output_dir, "pred_rttms", os.path.basename(audio_path).replace(".wav", ".rttm"))
        segments = self._parse_rttm(rttm_path)

        return segments

    def _parse_rttm(self, rttm_path: str) -> list[dict]:
        """Parse RTTM file into segment list."""
        segments = []
        if not os.path.exists(rttm_path):
            return segments

        with open(rttm_path, "r") as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 8 and parts[0] == "SPEAKER":
                    start = float(parts[3])
                    duration = float(parts[4])
                    speaker = parts[7]
                    segments.append({
                        "speaker": speaker,
                        "start": start,
                        "end": start + duration,
                    })

        return sorted(segments, key=lambda x: x["start"])

    def diarize(self, audio: np.ndarray) -> list[dict]:
        """
        Perform speaker diarization on audio.

        Args:
            audio: Audio data as float32 numpy array

        Returns:
            List of speaker segments: [{"speaker": str, "start": float, "end": float}, ...]
        """
        if len(audio) == 0:
            return []

        # Ensure audio is the right shape
        if audio.ndim > 1:
            audio = audio.flatten()

        # Create temp directory for NeMo outputs
        with tempfile.TemporaryDirectory() as temp_dir:
            # Write audio file
            audio_path = os.path.join(temp_dir, "audio.wav")
            import scipy.io.wavfile as wav
            audio_int16 = (audio * 32767).astype(np.int16)
            wav.write(audio_path, self.sample_rate, audio_int16)

            # Run diarization
            segments = self._run_diarization(audio_path, temp_dir)

        return segments

    def diarize_with_offset(
        self, audio: np.ndarray, offset: float = 0.0
    ) -> list[dict]:
        """
        Diarize audio with a time offset applied to timestamps.

        Args:
            audio: Audio data
            offset: Time offset to add to all timestamps

        Returns:
            Segments with adjusted timestamps
        """
        segments = self.diarize(audio)
        for seg in segments:
            seg["start"] += offset
            seg["end"] += offset
        return segments


def merge_transcript_with_speakers(
    transcript_segments: list[dict],
    speaker_segments: list[dict],
) -> list[dict]:
    """
    Merge transcript segments with speaker labels.

    Args:
        transcript_segments: [{"text": str, "start": float, "end": float}, ...]
        speaker_segments: [{"speaker": str, "start": float, "end": float}, ...]

    Returns:
        [{"text": str, "start": float, "end": float, "speaker": str}, ...]
    """
    result = []

    for trans in transcript_segments:
        trans_mid = (trans["start"] + trans["end"]) / 2

        # Find the speaker segment that contains the midpoint
        speaker = "UNKNOWN"
        for spk in speaker_segments:
            if spk["start"] <= trans_mid <= spk["end"]:
                speaker = spk["speaker"]
                break

        result.append(
            {
                "text": trans["text"],
                "start": trans["start"],
                "end": trans["end"],
                "speaker": speaker,
            }
        )

    return result


if __name__ == "__main__":
    print("Testing NeMo diarization...")

    diarizer = Diarizer()

    # Generate test audio (3 seconds of noise)
    duration = 3.0
    t = np.linspace(0, duration, int(16000 * duration), dtype=np.float32)
    test_audio = 0.1 * np.random.randn(len(t)).astype(np.float32)

    print("Running diarization on test audio...")
    segments = diarizer.diarize(test_audio)
    print(f"Speaker segments: {segments}")
    if not segments:
        print("(No speakers detected in noise - this is expected)")
