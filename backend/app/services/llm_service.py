from __future__ import annotations

import os
import logging
import time
from typing import Any, Dict

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None

from app.services.observability import store

logger = logging.getLogger(__name__)


class LLMService:
    def __init__(self) -> None:
        self.api_key = os.getenv("OPENAI_API_KEY", "")
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.client = OpenAI(api_key=self.api_key) if OpenAI and self.api_key else None

    def generate(self, prompt: str, system_prompt: str = "You are a helpful logistics analyst.") -> str:
        if not self.client:
            return self._fallback_response(prompt)
        started = time.perf_counter()
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
            )
            latency_ms = (time.perf_counter() - started) * 1000
            usage = response.usage
            prompt_tokens = usage.prompt_tokens if usage else 0
            completion_tokens = usage.completion_tokens if usage else 0
            input_rate = float(os.getenv("LLM_INPUT_COST_PER_MILLION", "0.15"))
            output_rate = float(os.getenv("LLM_OUTPUT_COST_PER_MILLION", "0.60"))
            estimated_cost = (prompt_tokens * input_rate + completion_tokens * output_rate) / 1_000_000
            store.record_llm_call(
                model_name=self.model,
                provider="openai",
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                latency_ms=latency_ms,
                status="SUCCESS",
                estimated_cost=estimated_cost,
            )
            return response.choices[0].message.content or ""
        except Exception as error:
            latency_ms = (time.perf_counter() - started) * 1000
            logger.exception("LLM request failed; deterministic fallback is being used")
            store.record_llm_call(
                model_name=self.model,
                provider="openai",
                prompt_tokens=0,
                completion_tokens=0,
                latency_ms=latency_ms,
                status="ERROR",
                error=type(error).__name__,
            )
            store.record_error(type(error).__name__, "LLM request failed.", severity="ERROR")
            return self._fallback_response(prompt)

    def _fallback_response(self, prompt: str) -> str:
        lower = prompt.lower()
        if "risk" in lower or "classify" in lower:
            return '{"risk_class": "HIGH", "confidence": 0.88, "recommended_action": "Escalate supplier and initiate contingency planning"}'
        if "policy" in lower:
            return "Supplier delay policy requires escalation if the delay exceeds 3 days and inventory coverage falls below safety stock."
        return "The system generated a grounded operational summary using deterministic workflow logic and synthetic evidence."


llm_service = LLMService()
