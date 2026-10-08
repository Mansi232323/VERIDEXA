"""
VERIDEXA  LLM abstraction layer (optional).

The app is 100% functional with this disabled — insight_generator.py
produces solid template-based narration from real computed facts with
zero API dependency. This module exists only to optionally re-phrase
that narration more fluently using an LLM, WITHOUT ever letting the
LLM invent a number: it is only ever given already-computed facts and
asked to phrase them, never asked to compute or guess anything.

Swappable providers, all wired up below: groq | openai | anthropic |
ollama (local, no API key needed). Set LLM_PROVIDER / LLM_API_KEY /
LLM_MODEL (and LLM_BASE_URL for ollama) in .env to enable.
"""
from __future__ import annotations

import json

from config.settings import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, LLM_PROVIDER
from utils.logger import get_logger

log = get_logger(__name__)

USE_LLM_PHRASING = False  # flip to True once you've set provider/key in .env

# Providers that need an API key. "ollama" talks to a local server instead,
# so it's deliberately left out of this check.
_KEYED_PROVIDERS = {"groq", "openai", "anthropic"}


def llm_available() -> bool:
    if not USE_LLM_PHRASING or LLM_PROVIDER == "none":
        return False
    if LLM_PROVIDER in _KEYED_PROVIDERS:
        return bool(LLM_API_KEY)
    return LLM_PROVIDER == "ollama"


def rephrase_insight(facts: dict, base_narration: dict) -> dict:
    """Optionally ask an LLM to phrase `base_narration` more fluently.
    `facts` is passed only as read-only grounding context the prompt
    explicitly forbids introducing any number not already present in
    `facts` or `base_narration`. On any failure, falls back to the
    already-correct template narration untouched."""
    if not llm_available():
        return base_narration

    try:
        import requests
    except ImportError:
        log.warning("`requests` not installed; skipping LLM phrasing.")
        return base_narration

    system_prompt = (
        "You are a business analyst assistant. You will be given ALREADY "
        "COMPUTED facts and a draft narration. Rephrase the draft to be more "
        "natural and engaging, in the same four-part Finding/Explanation/"
        "Business Impact/Recommendation structure. You MUST NOT introduce, "
        "change, or estimate any number that isn't already present in the "
        "facts or draft. Return strict JSON with keys: finding, explanation, "
        "business_impact, recommendation."
    )
    user_prompt = json.dumps({"facts": facts, "draft": base_narration})

    try:
        if LLM_PROVIDER == "groq":
            parsed = _chat_completions_json(
                url="https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {LLM_API_KEY}"},
                model=LLM_MODEL or "llama-3.3-70b-versatile",
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                requests=requests,
            )
        elif LLM_PROVIDER == "openai":
            parsed = _chat_completions_json(
                url="https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {LLM_API_KEY}"},
                model=LLM_MODEL or "gpt-4o-mini",
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                requests=requests,
            )
        elif LLM_PROVIDER == "anthropic":
            resp = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": LLM_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": LLM_MODEL or "claude-haiku-4-5-20251001",
                    "max_tokens": 1024,
                    "system": system_prompt + " Return ONLY the JSON object, no other text.",
                    "messages": [{"role": "user", "content": user_prompt}],
                },
                timeout=15,
            )
            resp.raise_for_status()
            content = resp.json()["content"][0]["text"]
            parsed = json.loads(_strip_code_fence(content))
        elif LLM_PROVIDER == "ollama":
            # Local server, e.g. `ollama serve` — no API key required.
            resp = requests.post(
                f"{LLM_BASE_URL.rstrip('/')}/api/chat",
                json={
                    "model": LLM_MODEL or "llama3",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "format": "json",
                    "stream": False,
                },
                timeout=30,
            )
            resp.raise_for_status()
            content = resp.json()["message"]["content"]
            parsed = json.loads(_strip_code_fence(content))
        else:
            log.info("LLM provider '%s' not wired up in this build; using template narration.", LLM_PROVIDER)
            return base_narration

        # Guardrail: keep only the four expected keys; anything else is dropped.
        return {k: parsed.get(k, base_narration[k]) for k in
                ("finding", "explanation", "business_impact", "recommendation")}
    except Exception:
        log.exception("LLM phrasing failed; falling back to template narration.")
        return base_narration


def _chat_completions_json(url: str, headers: dict, model: str, system_prompt: str,
                            user_prompt: str, requests) -> dict:
    """Shared call shape for OpenAI-compatible `/chat/completions` APIs
    (OpenAI itself, and Groq, which mirrors the same schema)."""
    resp = requests.post(
        url,
        headers=headers,
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.4,
        },
        timeout=15,
    )
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    return json.loads(_strip_code_fence(content))


def _strip_code_fence(text: str) -> str:
    """Some providers wrap JSON in ```json ... ``` even when not asked to."""
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    return text.strip()
