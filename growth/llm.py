"""Minimal OpenAI-compatible chat client (stdlib only).

Works with DeepSeek / Doubao / Tongyi / SiliconFlow / OpenAI and any
OpenAI-compatible endpoint. Configure via env:
    GROWTH_LLM_BASE_URL  (preferred) or GROWTH_LLM_BASE
                         default https://api.deepseek.com/v1
    GROWTH_LLM_KEY       (falls back to DEEPSEEK_API_KEY / OPENAI_API_KEY)
    GROWTH_LLM_MODEL     default deepseek-chat
If no key is configured the layer degrades gracefully: rules are stored raw.
"""

from __future__ import annotations

import json
import os
import urllib.request


class LLM:
    def __init__(self) -> None:
        self.base = (
            os.environ.get("GROWTH_LLM_BASE_URL")
            or os.environ.get("GROWTH_LLM_BASE")
            or "https://api.deepseek.com/v1"
        )
        self.key = (
            os.environ.get("GROWTH_LLM_KEY")
            or os.environ.get("DEEPSEEK_API_KEY")
            or os.environ.get("OPENAI_API_KEY")
            or ""
        )
        self.model = os.environ.get("GROWTH_LLM_MODEL", "deepseek-chat")

    def available(self) -> bool:
        return bool(self.key)

    def chat(self, system: str, user: str, max_tokens: int = 800) -> str | None:
        if not self.available():
            return None
        body = json.dumps(
            {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": 0.2,
                "max_tokens": max_tokens,
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            self.base.rstrip("/") + "/chat/completions",
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.key}",
            },
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"]
