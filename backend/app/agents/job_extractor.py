from __future__ import annotations

import json
import os
import re
import time
from typing import Literal
from urllib import error as urllib_error
from urllib import request as urllib_request

from ..data_loader import CatalogStore, load_catalog_store
from ..schemas.job_match import JobExtractResult

_STATIC_TOOL_TERMS = {
    "python",
    "sql",
    "aws",
    "docker",
    "kubernetes",
    "spark",
    "tableau",
    "power bi",
    "pandas",
    "numpy",
    "git",
    "linux",
    "excel",
    "terraform",
    "airflow",
    "snowflake",
}


def extract_job_skills(
    text: str,
    *,
    store: CatalogStore | None = None,
) -> tuple[JobExtractResult, Literal["used", "fallback", "disabled"], str | None]:
    provider, api_key, model, endpoint = _resolve_llm_target()
    if provider and api_key and endpoint:
        extracted, error = _extract_with_llm(
            text=text,
            provider=provider,
            api_key=api_key,
            model=model,
            endpoint=endpoint,
        )
        if extracted is not None:
            return extracted, "used", None
        return _fallback_extract(text, store=store), "fallback", error or "llm_extract_failed"
    return _fallback_extract(text, store=store), "disabled", None


def _extract_with_llm(
    *,
    text: str,
    provider: str,
    api_key: str,
    model: str,
    endpoint: str,
) -> tuple[JobExtractResult | None, str | None]:
    prompt_payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Extract skills from a pasted job description. "
                    "Return strict JSON only with keys: job_title, required_skills, preferred_skills, tools. "
                    "No extra keys. No salary claims. No guarantees."
                ),
            },
            {
                "role": "user",
                "content": text,
            },
        ],
        "temperature": 0,
        "max_tokens": 500,
    }
    if provider != "gemini":
        prompt_payload["response_format"] = {"type": "json_object"}
    req = urllib_request.Request(
        url=endpoint,
        method="POST",
        data=json.dumps(prompt_payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )

    retries = 1
    last_error: str | None = None
    for attempt in range(retries + 1):
        try:
            with urllib_request.urlopen(req, timeout=45) as response:
                raw = response.read().decode("utf-8")
        except urllib_error.HTTPError as exc:
            last_error = f"{provider}_http_{exc.code}"
            if attempt < retries and exc.code in {408, 409, 425, 429, 500, 502, 503, 504}:
                time.sleep(0.6 * (attempt + 1))
                continue
            return None, last_error
        except urllib_error.URLError:
            last_error = f"{provider}_network_error"
            if attempt < retries:
                time.sleep(0.6 * (attempt + 1))
                continue
            return None, last_error
        except TimeoutError:
            last_error = f"{provider}_timeout"
            if attempt < retries:
                time.sleep(0.6 * (attempt + 1))
                continue
            return None, last_error

        parsed = _parse_llm_json(raw)
        if parsed is None:
            last_error = f"{provider}_parse_error"
            if attempt < retries:
                time.sleep(0.4 * (attempt + 1))
                continue
            return None, last_error
        try:
            return JobExtractResult.model_validate(parsed), None
        except Exception:
            last_error = f"{provider}_schema_error"
            if attempt < retries:
                time.sleep(0.4 * (attempt + 1))
                continue
            return None, last_error
    return None, last_error or "llm_unknown"


def _parse_llm_json(raw: str) -> dict | None:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        payload = None

    if isinstance(payload, dict):
        content = payload.get("choices", [{}])[0].get("message", {}).get("content")
        if isinstance(content, str):
            obj = _parse_json_from_text(content)
            if isinstance(obj, dict):
                return obj
        # Some providers can return object directly in content-like field.
        if all(key in payload for key in {"job_title", "required_skills", "preferred_skills", "tools"}):
            return payload
    return _parse_json_from_text(raw)


def _parse_json_from_text(text: str) -> dict | None:
    content = text.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?", "", content).strip()
        content = re.sub(r"```$", "", content).strip()
    try:
        obj = json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, flags=re.DOTALL)
        if not match:
            return None
        try:
            obj = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return obj if isinstance(obj, dict) else None


def _fallback_extract(text: str, store: CatalogStore | None) -> JobExtractResult:
    catalog = store or _safe_load_store()
    lowered = text.lower()
    normalized = _normalize_text(lowered)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    job_title = lines[0][:120] if lines and len(lines[0]) <= 120 else None

    required_zone = _extract_zone(lowered, ["required", "requirements", "must have", "need to have"])
    preferred_zone = _extract_zone(lowered, ["preferred", "nice to have", "bonus", "plus"])

    required: set[str] = set()
    preferred: set[str] = set()
    tools: set[str] = set()

    for term in _STATIC_TOOL_TERMS:
        if _contains_phrase(normalized, term):
            tools.add(term)

    if catalog is not None:
        for skill in catalog.skills:
            names = [skill.name, *skill.aliases]
            for raw_name in names:
                phrase = _normalize_text(raw_name)
                if not phrase or len(phrase) < 2:
                    continue
                if not _contains_phrase(normalized, phrase):
                    continue
                if required_zone and _contains_phrase(_normalize_text(required_zone), phrase):
                    required.add(raw_name)
                elif preferred_zone and _contains_phrase(_normalize_text(preferred_zone), phrase):
                    preferred.add(raw_name)
                else:
                    preferred.add(raw_name)

    # Conservative keyword fallback for common role text.
    for token in re.findall(r"[a-z0-9\+#\.]+", lowered):
        if token in {"python", "sql", "statistics", "probability", "security", "cloud", "api", "linux"}:
            preferred.add(token)

    return JobExtractResult(
        job_title=job_title,
        required_skills=sorted(required),
        preferred_skills=sorted(preferred),
        tools=sorted(tools),
    )


def _extract_zone(text: str, markers: list[str], width: int = 650) -> str:
    for marker in markers:
        idx = text.find(marker)
        if idx >= 0:
            return text[idx : min(len(text), idx + width)]
    return ""


def _contains_phrase(text: str, phrase: str) -> bool:
    if not phrase:
        return False
    pattern = r"\b" + re.escape(phrase) + r"\b"
    return re.search(pattern, text) is not None


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\+#\. ]+", " ", value.lower())).strip()


def _safe_load_store() -> CatalogStore | None:
    try:
        return load_catalog_store()
    except Exception:
        return None


def _resolve_llm_target() -> tuple[str | None, str, str, str]:
    provider_pref = os.getenv("LLM_PROVIDER", "auto").strip().lower()
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()

    openai_model = os.getenv("OPENAI_MODEL_JOB_EXTRACT", "").strip() or os.getenv("OPENAI_MODEL", "").strip() or "gpt-4o-mini"
    gemini_model = os.getenv("GEMINI_MODEL_JOB_EXTRACT", "").strip() or os.getenv("GEMINI_MODEL", "").strip() or "gemini-2.0-flash"
    groq_model = os.getenv("GROQ_MODEL_JOB_EXTRACT", "").strip() or os.getenv("GROQ_MODEL", "").strip() or "llama-3.3-70b-versatile"

    if provider_pref == "openai":
        if openai_key:
            return "openai", openai_key, openai_model, "https://api.openai.com/v1/chat/completions"
        return None, "", "", ""
    if provider_pref == "gemini":
        if gemini_key:
            return "gemini", gemini_key, gemini_model, "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
        return None, "", "", ""
    if provider_pref == "groq":
        if groq_key:
            return "groq", groq_key, groq_model, "https://api.groq.com/openai/v1/chat/completions"
        return None, "", "", ""

    if openai_key:
        return "openai", openai_key, openai_model, "https://api.openai.com/v1/chat/completions"
    if gemini_key:
        return "gemini", gemini_key, gemini_model, "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
    if groq_key:
        return "groq", groq_key, groq_model, "https://api.groq.com/openai/v1/chat/completions"
    return None, "", "", ""
