from __future__ import annotations

import numpy as np
import sounddevice as sd


class AudioInput:
    def __init__(self, sample_rate: int, channels: int = 1) -> None:
        self.sample_rate = sample_rate
        self.channels = channels

    def record(self, seconds: float) -> np.ndarray:
        frames = int(seconds * self.sample_rate)
        audio = sd.rec(frames, samplerate=self.sample_rate, channels=self.channels, dtype="float32")
        sd.wait()
        return audio.reshape(-1)



def rms_energy(audio: np.ndarray) -> float:
    if audio.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(audio))))
