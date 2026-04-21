from __future__ import annotations

import json
from datetime import datetime, timedelta
from dataclasses import asdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

try:
    import google.generativeai as genai
except ImportError:
    genai = None
    
from openai import OpenAI

from luiz.agent.tools import ToolRegistry
 

SYSTEM_PROMPT = (
    "Voce e o Luiz, um assistente pessoal objetivo, tecnico e util. "
    "Responda em portugues do Brasil, com clareza e brevidade."
)

PRIMARY_PROMPT = (
    "Voce e o hemisferio analitico do Luiz. Foque em precisao, passos claros e resposta direta."
)

REVIEWER_PROMPT = (
    "Voce e o hemisferio critico do Luiz. Revise a resposta recebida. "
    "Se estiver correta, responda apenas com OK. "
    "Se houver falhas, retorne uma resposta final corrigida e objetiva em portugues."
)


@dataclass
class DailyQuotaState:
    date: str
    used_tokens: int = 0
    warned_70: bool = False
    warned_95: bool = False


@dataclass
class QuotaEvent:
    warning_70: bool = False
    sleep_95: bool = False


@dataclass
class AgentMemory:
    short_history: List[str] = field(default_factory=list)

    def add(self, role: str, message: str) -> None:
        self.short_history.append(f"{role}: {message}")
        if len(self.short_history) > 8:
            self.short_history = self.short_history[-8:]

    def as_text(self) -> str:
        return "\n".join(self.short_history[-6:])


class LuizBrain:
    def __init__(
        self,
        openai_model: str,
        openai_api_key: str,
        gemini_model: str,
        gemini_api_key: str,
        primary_llm: str,
        dual_policy: str,
        daily_token_budget: int,
        quota_warning_ratio: float,
        quota_sleep_ratio: float,
        quota_state_file: str,
        tools: ToolRegistry,
    ) -> None:
        self.openai_model = openai_model
        self.gemini_model = gemini_model
        self.primary_llm = primary_llm.lower().strip() if primary_llm else "openai"
        self.dual_policy = dual_policy.lower().strip() if dual_policy else "adaptive"
        self.daily_token_budget = max(1, daily_token_budget)
        self.quota_warning_ratio = min(max(quota_warning_ratio, 0.1), 0.99)
        self.quota_sleep_ratio = min(max(quota_sleep_ratio, 0.2), 0.995)
        if self.quota_sleep_ratio <= self.quota_warning_ratio:
            self.quota_sleep_ratio = min(self.quota_warning_ratio + 0.1, 0.995)
        self.quota_state_path = Path(quota_state_file)
        self.openai_client = OpenAI(api_key=openai_api_key) if openai_api_key else None

        self.gemini_enabled = bool(gemini_api_key)
        if self.gemini_enabled:
            genai.configure(api_key=gemini_api_key)

        self.tools = tools
        self.memory = AgentMemory()
        self.response_cache: Dict[str, str] = {}
        self._quota_state = self._load_quota_state()

    def _today_str(self) -> str:
        return datetime.now().strftime("%Y-%m-%d")

    def _load_quota_state(self) -> DailyQuotaState:
        today = self._today_str()
        if not self.quota_state_path.exists():
            state = DailyQuotaState(date=today)
            self._persist_quota_state(state)
            return state

        try:
            payload = json.loads(self.quota_state_path.read_text(encoding="utf-8"))
            state = DailyQuotaState(
                date=str(payload.get("date", today)),
                used_tokens=int(payload.get("used_tokens", 0)),
                warned_70=bool(payload.get("warned_70", False)),
                warned_95=bool(payload.get("warned_95", False)),
            )
        except Exception:
            state = DailyQuotaState(date=today)

        if state.date != today:
            state = DailyQuotaState(date=today)
            self._persist_quota_state(state)
        return state

    def _persist_quota_state(self, state: DailyQuotaState) -> None:
        self.quota_state_path.parent.mkdir(parents=True, exist_ok=True)
        self.quota_state_path.write_text(json.dumps(asdict(state), ensure_ascii=True, indent=2), encoding="utf-8")

    def _refresh_quota_if_new_day(self) -> None:
        if self._quota_state.date != self._today_str():
            self._quota_state = DailyQuotaState(date=self._today_str())
            self._persist_quota_state(self._quota_state)

    def _quota_ratio(self) -> float:
        return self._quota_state.used_tokens / self.daily_token_budget

    def _is_sleeping(self) -> bool:
        self._refresh_quota_if_new_day()
        return self._quota_ratio() >= self.quota_sleep_ratio

    def _sleep_message(self) -> str:
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%d/%m")
        return (
            "Minha energia de tokens chegou ao limite de descanso de 95%. "
            f"Vou dormir ate a cota diaria reiniciar. Me chame novamente amanha ({tomorrow})."
        )

    def _register_token_usage(self, used_tokens: int) -> QuotaEvent:
        self._refresh_quota_if_new_day()
        self._quota_state.used_tokens += max(0, used_tokens)

        event = QuotaEvent()
        ratio = self._quota_ratio()
        if ratio >= self.quota_warning_ratio and not self._quota_state.warned_70:
            self._quota_state.warned_70 = True
            event.warning_70 = True

        if ratio >= self.quota_sleep_ratio and not self._quota_state.warned_95:
            self._quota_state.warned_95 = True
            event.sleep_95 = True

        self._persist_quota_state(self._quota_state)
        return event

    def _event_message(self, event: QuotaEvent) -> str:
        if event.sleep_95:
            return (
                "Aviso: minha energia de tokens chegou em 95%. "
                "Vou descansar agora e retornar quando a cota diaria reiniciar."
            )
        if event.warning_70:
            return "Aviso: minha energia de tokens passou de 70% e esta acabando."
        return ""

    def handle_command(self, command: str) -> str:
        if self._is_sleeping():
            return self._sleep_message()

        self.memory.add("user", command)

        tool_result = self.tools.route_and_execute(command)
        if tool_result is not None:
            answer = tool_result.output
            self.memory.add("assistant", answer)
            return answer

        answer = self._ask_llm(command)
        self.memory.add("assistant", answer)
        return answer

    def _ask_llm(self, command: str) -> str:
        cached = self.response_cache.get(command.strip().lower())
        if cached:
            return cached

        if not self.openai_client and not self.gemini_enabled:
            return "Configure OPENAI_API_KEY e/ou GEMINI_API_KEY no .env para respostas inteligentes."

        prompt = (
            f"Contexto recente:\n{self.memory.as_text()}\n\n"
            f"Solicitacao atual: {command}"
        )

        primary_answer, reviewer_answer, event = self._run_brain_sides(command, prompt)
        event_message = self._event_message(event)

        if primary_answer and reviewer_answer:
            final_answer = primary_answer if reviewer_answer.strip().upper() == "OK" else reviewer_answer
            if event_message:
                final_answer = f"{final_answer}\n\n{event_message}"
            self.response_cache[command.strip().lower()] = final_answer
            return final_answer

        if primary_answer:
            if event_message:
                primary_answer = f"{primary_answer}\n\n{event_message}"
            self.response_cache[command.strip().lower()] = primary_answer
            return primary_answer

        if reviewer_answer and reviewer_answer.strip().upper() != "OK":
            if event_message:
                reviewer_answer = f"{reviewer_answer}\n\n{event_message}"
            self.response_cache[command.strip().lower()] = reviewer_answer
            return reviewer_answer

        return "Nao consegui gerar resposta agora. Verifique as chaves e tente novamente."

    def _run_brain_sides(self, command: str, prompt: str) -> tuple[Optional[str], Optional[str], QuotaEvent]:
        event = QuotaEvent()
        use_dual = self._should_use_dual(command)

        primary_answer, primary_tokens = self._ask_primary(prompt)
        event = self._merge_events(event, self._register_token_usage(primary_tokens))
        if not primary_answer:
            fallback, fallback_tokens = self._ask_secondary(prompt)
            event = self._merge_events(event, self._register_token_usage(fallback_tokens))
            return fallback, None, event

        if event.sleep_95:
            return primary_answer, None, event

        if not use_dual:
            return primary_answer, None, event

        review_prompt = (
            f"Contexto da solicitacao:\n{prompt}\n\n"
            f"Resposta para revisar:\n{primary_answer}"
        )
        reviewer_answer, reviewer_tokens = self._ask_secondary(review_prompt, reviewer_mode=True)
        event = self._merge_events(event, self._register_token_usage(reviewer_tokens))
        return primary_answer, reviewer_answer, event

    def _merge_events(self, first: QuotaEvent, second: QuotaEvent) -> QuotaEvent:
        return QuotaEvent(
            warning_70=first.warning_70 or second.warning_70,
            sleep_95=first.sleep_95 or second.sleep_95,
        )

    def _should_use_dual(self, command: str) -> bool:
        if self.dual_policy == "always":
            return True

        if self.dual_policy == "single":
            return False

        complex_keywords = [
            "planejar",
            "estrategia",
            "comparar",
            "analise",
            "analisar",
            "arquitetura",
            "multi",
            "passo",
            "detalhado",
            "critico",
            "seguranca",
            "financeiro",
            "contrato",
            "decisao",
        ]
        normalized = command.lower()
        if len(normalized) > 180:
            return True
        return any(k in normalized for k in complex_keywords)

    def _ask_primary(self, prompt: str) -> tuple[Optional[str], int]:
        if self.primary_llm == "gemini":
            return self._ask_gemini(prompt, role_prompt=PRIMARY_PROMPT)
        return self._ask_openai(prompt, role_prompt=PRIMARY_PROMPT)

    def _ask_secondary(self, prompt: str, reviewer_mode: bool = False) -> tuple[Optional[str], int]:
        role_prompt = REVIEWER_PROMPT if reviewer_mode else PRIMARY_PROMPT

        if self.primary_llm == "gemini":
            return self._ask_openai(prompt, role_prompt=role_prompt)
        return self._ask_gemini(prompt, role_prompt=role_prompt)

    def _ask_openai(self, prompt: str, role_prompt: str) -> tuple[Optional[str], int]:
        if not self.openai_client:
            return None, 0

        try:
            response = self.openai_client.responses.create(
                model=self.openai_model,
                input=[
                    {"role": "system", "content": f"{SYSTEM_PROMPT} {role_prompt}"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                max_output_tokens=220,
            )
            text = response.output_text.strip()
            usage = getattr(response, "usage", None)
            total_tokens = int(getattr(usage, "total_tokens", 0) or 0)
            return text or None, total_tokens
        except Exception:
            return None, 0

    def _ask_gemini(self, prompt: str, role_prompt: str) -> tuple[Optional[str], int]:
        if not self.gemini_enabled:
            return None, 0

        try:
            model = genai.GenerativeModel(self.gemini_model)
            response = model.generate_content(
                f"{SYSTEM_PROMPT} {role_prompt}\n\n{prompt}",
                generation_config={"temperature": 0.2, "max_output_tokens": 220},
            )
            text = getattr(response, "text", "")
            clean = text.strip() if text else ""
            usage = getattr(response, "usage_metadata", None)
            total_tokens = int(getattr(usage, "total_token_count", 0) or 0)
            return clean or None, total_tokens
        except Exception:
            return None, 0
