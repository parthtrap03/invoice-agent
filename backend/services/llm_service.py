from __future__ import annotations

"""Free local LLM integration via Ollama (optional, zero-cost).

If Ollama (https://ollama.com) is running locally, the app uses it for:
  - natural-language rephrasing of finance Q&A answers
  - vision extraction of scanned invoice images (with a vision model)

If Ollama is not installed/running, every helper degrades gracefully and the
system stays fully deterministic - nothing breaks, no API keys, no cost.
"""

import base64
import json
import urllib.error
import urllib.request
from typing import Any, Optional

import anyio

OLLAMA_URL = "http://localhost:11434"
DEFAULT_MODEL = "llama3.2"
VISION_MODELS = ("llama3.2-vision", "llava", "qwen2.5vl", "minicpm-v", "moondream")

_TIMEOUT = 60


def _http_json(url: str, payload: dict[str, Any] | None = None, timeout: int = _TIMEOUT) -> Any:
    if payload is None:
        req = urllib.request.Request(url)
    else:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


class OllamaLLM:
    """Thin client for a locally running Ollama server. All methods are safe
    to call when Ollama is absent - they return None / False instead of raising."""

    def __init__(self, base_url: str = OLLAMA_URL):
        self.base_url = base_url

    def _list_models_sync(self) -> list[str]:
        try:
            data = _http_json(f"{self.base_url}/api/tags", timeout=2)
            return [m["name"].split(":")[0] for m in data.get("models", [])]
        except (urllib.error.URLError, OSError, ValueError, KeyError):
            return []

    async def available_models(self) -> list[str]:
        return await anyio.to_thread.run_sync(self._list_models_sync)

    async def is_available(self) -> bool:
        return bool(await self.available_models())

    async def pick_model(self, vision: bool = False) -> Optional[str]:
        models = await self.available_models()
        if not models:
            return None
        if vision:
            for candidate in VISION_MODELS:
                if candidate in models:
                    return candidate
            return None
        for candidate in (DEFAULT_MODEL, *models):
            if candidate in models:
                return candidate
        return models[0]

    def _generate_sync(self, model: str, prompt: str, image_path: Optional[str]) -> Optional[str]:
        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0},  # deterministic as possible
        }
        if image_path:
            with open(image_path, "rb") as f:
                payload["images"] = [base64.b64encode(f.read()).decode()]
        try:
            data = _http_json(f"{self.base_url}/api/generate", payload, timeout=180)
            return data.get("response")
        except (urllib.error.URLError, OSError, ValueError):
            return None

    async def generate(self, prompt: str, model: Optional[str] = None, image_path: Optional[str] = None) -> Optional[str]:
        model = model or await self.pick_model(vision=image_path is not None)
        if model is None:
            return None
        return await anyio.to_thread.run_sync(self._generate_sync, model, prompt, image_path)


_llm: OllamaLLM | None = None


def get_local_llm() -> OllamaLLM:
    global _llm
    if _llm is None:
        _llm = OllamaLLM()
    return _llm


async def rephrase_answer(question: str, deterministic_answer: str, data: Any) -> Optional[str]:
    """Ask the local LLM to phrase the exact computed numbers naturally.
    Returns None when no local LLM is available (caller keeps the original)."""
    llm = get_local_llm()
    prompt = (
        "You are a finance assistant. Rephrase the following computed answer "
        "into one or two natural, friendly sentences. You MUST keep every "
        "number and currency amount EXACTLY as given - never recompute or "
        "round. Do not add information.\n\n"
        f"User question: {question}\n"
        f"Computed answer: {deterministic_answer}\n"
        f"Supporting data: {json.dumps(data, default=str)[:1500]}\n\n"
        "Rephrased answer:"
    )
    result = await llm.generate(prompt)
    return result.strip() if result else None
