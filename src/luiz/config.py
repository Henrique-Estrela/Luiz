import os
from dataclasses import dataclass
from typing import List

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    openai_api_key: str
    gemini_api_key: str
    openai_model: str
    gemini_model: str
    primary_llm: str
    dual_policy: str
    daily_token_budget: int
    quota_warning_ratio: float
    quota_sleep_ratio: float
    quota_state_file: str
    wake_words: List[str]
    stt_model: str
    sample_rate: int
    listen_seconds: float
    command_seconds: float
    energy_threshold: float
    scripts_dir: str



def load_settings() -> Settings:
    wake_words_raw = os.getenv("LUIZ_WAKE_WORDS", "luiz,luis")
    wake_words = [w.strip().lower() for w in wake_words_raw.split(",") if w.strip()]

    return Settings(
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
        openai_model=os.getenv("LUIZ_OPENAI_MODEL", "gpt-4o-mini"),
        gemini_model=os.getenv("LUIZ_GEMINI_MODEL", "gemini-1.5-flash"),
        primary_llm=os.getenv("LUIZ_PRIMARY_LLM", "openai"),
        dual_policy=os.getenv("LUIZ_DUAL_POLICY", "adaptive"),
        daily_token_budget=int(os.getenv("LUIZ_DAILY_TOKEN_BUDGET", "40000")),
        quota_warning_ratio=float(os.getenv("LUIZ_QUOTA_WARNING_RATIO", "0.70")),
        quota_sleep_ratio=float(os.getenv("LUIZ_QUOTA_SLEEP_RATIO", "0.95")),
        quota_state_file=os.getenv("LUIZ_QUOTA_STATE_FILE", ".luiz/quota_state.json"),
        wake_words=wake_words,
        stt_model=os.getenv("LUIZ_STT_MODEL", "tiny"),
        sample_rate=int(os.getenv("LUIZ_SAMPLE_RATE", "16000")),
        listen_seconds=float(os.getenv("LUIZ_INPUT_SECONDS", "2.5")),
        command_seconds=float(os.getenv("LUIZ_COMMAND_SECONDS", "8")),
        energy_threshold=float(os.getenv("LUIZ_ENERGY_THRESHOLD", "0.01")),
        scripts_dir=os.getenv("LUIZ_SCRIPTS_DIR", "scripts"),
    )
