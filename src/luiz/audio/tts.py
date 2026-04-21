from __future__ import annotations

import pyttsx3


class TTSEngine:
    def __init__(self) -> None:
        self.engine = pyttsx3.init()
        self.engine.setProperty("rate", 180)

    def speak(self, text: str) -> None:
        self.engine.say(text)
        self.engine.runAndWait()
