"""Audio capture using sounddevice."""

import queue
import threading
from typing import Callable, Optional

import numpy as np
import sounddevice as sd


class AudioCapture:
    """Captures audio from the default microphone."""

    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        chunk_duration: float = 0.5,
    ):
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_duration = chunk_duration
        self.chunk_size = int(sample_rate * chunk_duration)

        self._audio_queue: queue.Queue[np.ndarray] = queue.Queue()
        self._recording = False
        self._stream: Optional[sd.InputStream] = None

    def _audio_callback(
        self,
        indata: np.ndarray,
        frames: int,
        time_info: dict,
        status: sd.CallbackFlags,
    ) -> None:
        """Called for each audio chunk."""
        if status:
            pass  # Could log status flags if needed
        self._audio_queue.put(indata.copy())

    def start(self) -> None:
        """Start audio capture."""
        if self._recording:
            return

        self._recording = True
        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype=np.float32,
            blocksize=self.chunk_size,
            callback=self._audio_callback,
        )
        self._stream.start()

    def stop(self) -> None:
        """Stop audio capture."""
        self._recording = False
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    def get_chunk(self, timeout: float = 1.0) -> Optional[np.ndarray]:
        """Get the next audio chunk from the queue."""
        try:
            return self._audio_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def get_all_chunks(self) -> np.ndarray:
        """Get all available chunks concatenated."""
        chunks = []
        while not self._audio_queue.empty():
            try:
                chunks.append(self._audio_queue.get_nowait())
            except queue.Empty:
                break
        if chunks:
            return np.concatenate(chunks)
        return np.array([], dtype=np.float32)

    @property
    def is_recording(self) -> bool:
        return self._recording


class AudioBuffer:
    """Accumulates audio for batch processing."""

    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate
        self._buffer: list[np.ndarray] = []
        self._lock = threading.Lock()

    def append(self, chunk: np.ndarray) -> None:
        """Add a chunk to the buffer."""
        with self._lock:
            self._buffer.append(chunk)

    def get_and_clear(self) -> np.ndarray:
        """Get all buffered audio and clear the buffer."""
        with self._lock:
            if not self._buffer:
                return np.array([], dtype=np.float32)
            audio = np.concatenate(self._buffer)
            self._buffer.clear()
            return audio

    def get_duration(self) -> float:
        """Get current buffer duration in seconds."""
        with self._lock:
            if not self._buffer:
                return 0.0
            total_samples = sum(len(chunk) for chunk in self._buffer)
            return total_samples / self.sample_rate

    def clear(self) -> None:
        """Clear the buffer."""
        with self._lock:
            self._buffer.clear()


if __name__ == "__main__":
    # Test audio capture
    print("Testing audio capture for 3 seconds...")
    capture = AudioCapture()
    buffer = AudioBuffer()

    capture.start()
    import time

    start = time.time()
    while time.time() - start < 3:
        chunk = capture.get_chunk(timeout=0.1)
        if chunk is not None:
            buffer.append(chunk)
            print(f"Captured {buffer.get_duration():.1f}s of audio", end="\r")
    capture.stop()

    audio = buffer.get_and_clear()
    print(f"\nTotal audio captured: {len(audio) / 16000:.2f} seconds")
    print(f"Audio shape: {audio.shape}, dtype: {audio.dtype}")
