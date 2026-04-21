from __future__ import annotations

import io
from typing import Optional

import numpy as np
import soundfile as sf
from faster_whisper import WhisperModel


class STTEngine:
    def __init__(self, model_size: str = "tiny", sample_rate: int = 16000) -> None:
        self.sample_rate = sample_rate
        self.model = WhisperModel(model_size, device="cpu", compute_type="int8")

    def transcribe(self, audio: np.ndarray) -> str:
        if audio.size == 0:
            return ""

        wav_bytes = self._to_wav_bytes(audio)
        segments, _ = self.model.transcribe(wav_bytes, language="pt", vad_filter=True)
        text = " ".join(segment.text.strip() for segment in segments).strip()
        return text

    def _to_wav_bytes(self, audio: np.ndarray) -> io.BytesIO:
        wav_io = io.BytesIO()
        sf.write(wav_io, audio, self.sample_rate, format="WAV")
        wav_io.seek(0)
        return wav_io
