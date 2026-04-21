from __future__ import annotations

import time

from luiz.agent.brain import LuizBrain
from luiz.agent.tools import ToolRegistry
from luiz.audio.io import AudioInput, rms_energy
from luiz.audio.stt import STTEngine
from luiz.audio.tts import TTSEngine
from luiz.config import load_settings



def _contains_wake_word(text: str, wake_words: list[str]) -> bool:
    normalized = text.lower().strip()
    return any(w in normalized for w in wake_words)



def run() -> None:
    settings = load_settings()

    audio = AudioInput(sample_rate=settings.sample_rate)
    stt = STTEngine(model_size=settings.stt_model, sample_rate=settings.sample_rate)
    tts = TTSEngine()
    tools = ToolRegistry(scripts_dir=settings.scripts_dir)
    brain = LuizBrain(
        openai_model=settings.openai_model,
        openai_api_key=settings.openai_api_key,
        gemini_model=settings.gemini_model,
        gemini_api_key=settings.gemini_api_key,
        primary_llm=settings.primary_llm,
        dual_policy=settings.dual_policy,
        daily_token_budget=settings.daily_token_budget,
        quota_warning_ratio=settings.quota_warning_ratio,
        quota_sleep_ratio=settings.quota_sleep_ratio,
        quota_state_file=settings.quota_state_file,
        tools=tools,
    )

    print("Luiz iniciado. Diga 'Luiz' para chamar.")
    tts.speak("Luiz pronto. Diga Luiz para me chamar.")

    while True:
        try:
            wake_audio = audio.record(settings.listen_seconds)
            if rms_energy(wake_audio) < settings.energy_threshold:
                continue

            heard = stt.transcribe(wake_audio)
            if not heard:
                continue

            print(f"[escutado] {heard}")
            if not _contains_wake_word(heard, settings.wake_words):
                continue

            tts.speak("Sim, pode falar.")
            print("[luiz] aguardando comando...")

            cmd_audio = audio.record(settings.command_seconds)
            if rms_energy(cmd_audio) < settings.energy_threshold:
                tts.speak("Nao consegui ouvir seu comando.")
                continue

            command = stt.transcribe(cmd_audio)
            if not command:
                tts.speak("Nao consegui entender. Tente novamente.")
                continue

            print(f"[comando] {command}")

            if command.lower().strip() in {"sair", "encerrar", "desligar"}:
                farewell = "Ate logo. Encerrando o assistente."
                print(f"[luiz] {farewell}")
                tts.speak(farewell)
                break

            answer = brain.handle_command(command)
            print(f"[luiz] {answer}")
            tts.speak(answer)

            # Evita capturar o proprio TTS no loop imediatamente seguinte.
            time.sleep(0.2)
        except KeyboardInterrupt:
            print("\nEncerrado pelo usuario.")
            break
        except Exception as exc:
            print(f"Erro no loop principal: {exc}")
            tts.speak("Ocorreu um erro interno. Vou continuar operando.")
            time.sleep(0.5)
