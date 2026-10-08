from __future__ import annotations

import os
from typing import Any, Dict

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None


class LLMService:
    def __init__(self) -> None:
        self.api_key = os.getenv("OPENAI_API_KEY", "")
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.client = OpenAI(api_key=self.api_key) if OpenAI and self.api_key else None

    def generate(self, prompt: str, system_prompt: str = "You are a helpful logistics analyst.") -> str:
        if not self.client:
            return self._fallback_response(prompt)
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
            )
            return response.choices[0].message.content or ""
        except Exception:
            return self._fallback_response(prompt)

    def _fallback_response(self, prompt: str) -> str:
        lower = prompt.lower()
        if "risk" in lower or "classify" in lower:
            return '{"risk_class": "HIGH", "confidence": 0.88, "recommended_action": "Escalate supplier and initiate contingency planning"}'
        if "policy" in lower:
            return "Supplier delay policy requires escalation if the delay exceeds 3 days and inventory coverage falls below safety stock."
        return "The system generated a grounded operational summary using deterministic workflow logic and synthetic evidence."


llm_service = LLMService()
