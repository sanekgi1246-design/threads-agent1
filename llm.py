"""Любая нейросеть с OpenAI-совместимым API. По умолчанию — бесплатный Groq."""
import json
import re

import requests

from common import env

DEFAULT_BASE = "https://api.groq.com/openai/v1"
# Пробуем по порядку: если провайдер убрал модель, берём следующую
DEFAULT_MODELS = "llama-3.3-70b-versatile,openai/gpt-oss-120b,llama-3.1-8b-instant"


def chat(system: str, user: str, temperature: float = 0.9) -> str:
    base = env("LLM_BASE_URL", DEFAULT_BASE).rstrip("/")
    key = env("LLM_API_KEY", required=True)
    models = [m.strip() for m in env("LLM_MODEL", DEFAULT_MODELS).split(",") if m.strip()]
    last_err = None
    for model in models:
        try:
            r = requests.post(
                f"{base}/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json={"model": model, "temperature": temperature,
                      "messages": [{"role": "system", "content": system},
                                   {"role": "user", "content": user}]},
                timeout=90,
            )
            if r.status_code >= 400:
                raise RuntimeError(f"{model}: {r.status_code} {r.text[:300]}")
            return r.json()["choices"][0]["message"]["content"]
        except Exception as e:  # noqa: BLE001
            last_err = e
            print("LLM fallback:", e)
    raise RuntimeError(f"Все модели недоступны: {last_err}")


def chat_json(system: str, user: str) -> dict:
    raw = chat(system, user)
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        raise ValueError(f"LLM не вернула JSON: {raw[:200]}")
    return json.loads(m.group(0))
