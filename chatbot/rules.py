"""OpenRouter AI integration helpers for the patient chatbot."""

import base64
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SYSTEM_PROMPT = (
    "You are a helpful medical assistant. You provide general health advice only. "
    "You do NOT diagnose or prescribe. Give complete, clear, practical responses. "
    "Always include one explicit doctor recommendation line in this format: "
    "Suggested doctor: <doctor type>. Place this line at the end of the response. "
    "For common mild symptoms, prefer General Physician."
)
DISCLAIMER = "This is not medical advice. Please consult a doctor."
EMERGENCY_TERMS = ["chest pain", "difficulty breathing", "severe pain"]

DOCTOR_KEYWORDS: dict[str, list[str]] = {
    "Cardiologist": ["chest", "heart", "palpitation", "bp", "blood pressure"],
    "Dermatologist": ["skin", "rash", "itch", "acne", "eczema"],
    "ENT Specialist": ["ear", "nose", "throat", "sinus", "tonsil"],
    "Neurologist": ["migraine", "seizure", "numb", "head injury", "faint"],
    "Orthopedic Doctor": ["joint", "bone", "fracture", "back pain", "knee"],
    "Gynecologist": ["period", "pregnan", "pelvic", "menstrual"],
    "Pulmonologist": ["asthma", "wheez", "lung", "persistent cough"],
    "Gastroenterologist": ["stomach", "abdomen", "vomit", "diarrhea", "constipation"],
}

DEFAULT_MODEL = "deepseek"
SUPPORTED_MODELS = {
    "deepseek": "GPT-4",
    "gemini": "Gemini 2.5 Flash",
}

MODEL_ALIASES = {
    "deepseek-chat": "deepseek",
    "deepseek/deepseek-chat-v3-0324": "deepseek",
    "gemini-1.5-flash": "gemini",
    "gemini 1.5 flash": "gemini",
    "google/gemini-1.5-flash": "gemini",
}



def _with_disclaimer(text: str) -> str:
    """Ensure every chatbot message includes the required disclaimer."""
    safe_text = (text or "").strip()
    if DISCLAIMER.lower() in safe_text.lower():
        return safe_text
    return f"{safe_text} {DISCLAIMER}".strip()


def _is_emergency_query(user_message: str) -> bool:
    """Detect high-risk phrases that should bypass normal chatbot flow."""
    normalized = (user_message or "").lower()
    return any(term in normalized for term in EMERGENCY_TERMS)


def _suggest_doctor_type(user_message: str) -> str:
    """Return a doctor specialty suggestion based on symptom keywords."""
    normalized = (user_message or "").lower()

    if _is_emergency_query(normalized):
        return "Emergency Medicine / ER"

    for doctor_type, keywords in DOCTOR_KEYWORDS.items():
        if any(keyword in normalized for keyword in keywords):
            return doctor_type

    return "General Physician"


def _with_doctor_suggestion(reply_text: str, user_message: str) -> str:
    """Ensure every reply contains an explicit doctor recommendation line."""
    content = (reply_text or "").strip()
    if "suggested doctor:" in content.lower():
        return content

    doctor_type = _suggest_doctor_type(user_message)
    if not content:
        return f"Suggested doctor: {doctor_type}."
    return f"{content}\n\nSuggested doctor: {doctor_type}."


def normalize_model_choice(model_choice: str | None) -> str:
    """Return a safe model identifier from user input."""
    normalized = (model_choice or "").strip().lower()

    if normalized in MODEL_ALIASES:
        return MODEL_ALIASES[normalized]

    if "gemini" in normalized:
        return "gemini"

    if "deepseek" in normalized:
        return "deepseek"

    if normalized in SUPPORTED_MODELS:
        return normalized
    return DEFAULT_MODEL


def _get_deepseek_response(prompt: str, chat_history: list[dict] | None = None) -> str:
    """Call OpenRouter DeepSeek endpoint and return assistant text."""
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    api_url = os.getenv("OPENROUTER_API_URL", "https://openrouter.ai/api/v1/chat/completions").strip()
    model = os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-chat-v3-0324").strip()

    if not api_key:
        return "AI service is not configured. Set OPENROUTER_API_KEY to enable chatbot responses."

    recent_history = (chat_history or [])[-5:]
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(recent_history)
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": 700,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": os.getenv("OPENROUTER_SITE_URL", "http://localhost:5000"),
        "X-Title": os.getenv("OPENROUTER_APP_NAME", "Healthcare Appointment System"),
    }

    try:
        response = requests.post(api_url, headers=headers, json=payload, timeout=25)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()
    except requests.exceptions.HTTPError as error:
        status_code = error.response.status_code if error.response is not None else None
        if status_code in (401, 403):
            return "DeepSeek authentication failed. Please verify OPENROUTER_API_KEY."
        return "DeepSeek returned an error. Please try again shortly."
    except requests.exceptions.RequestException:
        return "I could not reach DeepSeek right now. Please try again shortly."
    except (KeyError, IndexError, TypeError, ValueError):
        return "DeepSeek returned an unexpected response format."


def _get_gemini_response(
    prompt: str,
    chat_history: list[dict] | None = None,
    image_bytes: bytes | None = None,
    image_mime_type: str | None = None,
) -> str:
    """Call Gemini 1.5 Flash and optionally include an uploaded image."""
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    api_url = os.getenv(
        "GEMINI_API_URL",
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent",
    ).strip()
    preferred_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()

    if not api_key:
        return "Gemini is not configured. Set GEMINI_API_KEY to enable Gemini chat."

    contents: list[dict] = []
    for item in (chat_history or [])[-5:]:
        role = "user" if item.get("role") == "user" else "model"
        text = (item.get("content") or "").strip()
        if text:
            contents.append({"role": role, "parts": [{"text": text}]})

    current_parts: list[dict] = []
    if prompt:
        current_parts.append({"text": prompt})

    if image_bytes:
        current_parts.append(
            {
                "inlineData": {
                    "mimeType": image_mime_type or "image/png",
                    "data": base64.b64encode(image_bytes).decode("utf-8"),
                }
            }
        )

    if not current_parts:
        current_parts.append({"text": "Please share general guidance based on this context."})

    contents.append({"role": "user", "parts": current_parts})

    payload = {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": contents,
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 700,
        },
    }

    def _extract_error_message(response: requests.Response) -> str:
        try:
            data = response.json()
            details = data.get("error", {}).get("message")
            if details:
                return str(details)
        except ValueError:
            pass
        return (response.text or "").strip()[:300] or "Unknown Gemini API error"

    def _normalize_model_name(model_name: str) -> str:
        return model_name.replace("models/", "").strip()

    def _resolve_api_root() -> str:
        marker = "/models/"
        if marker in api_url:
            return api_url.split(marker, 1)[0]
        return "https://generativelanguage.googleapis.com/v1beta"

    def _select_available_model(api_root: str, preferred: str) -> str:
        preferred_clean = _normalize_model_name(preferred)
        try:
            list_response = requests.get(
                f"{api_root}/models?key={api_key}",
                timeout=20,
            )
            list_response.raise_for_status()
            model_entries = list_response.json().get("models", [])
        except requests.exceptions.RequestException:
            return preferred_clean

        eligible_models: list[str] = []
        for entry in model_entries:
            methods = entry.get("supportedGenerationMethods") or []
            if "generateContent" not in methods:
                continue
            name = _normalize_model_name(entry.get("name", ""))
            if name:
                eligible_models.append(name)

        if preferred_clean in eligible_models:
            return preferred_clean

        priority_contains = ["gemini-1.5-flash", "gemini-2.0-flash", "flash"]
        for token in priority_contains:
            for name in eligible_models:
                if token in name:
                    return name

        return eligible_models[0] if eligible_models else preferred_clean

    try:
        api_root = _resolve_api_root()
        resolved_model = _select_available_model(api_root, preferred_model)
        endpoint = f"{api_root}/models/{resolved_model}:generateContent"
        response = requests.post(
            f"{endpoint}?key={api_key}",
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=30,
        )

        response.raise_for_status()
        data = response.json()
        parts = data["candidates"][0]["content"]["parts"]
        reply = "\n".join(part.get("text", "").strip() for part in parts if part.get("text"))
        return reply.strip() or "Gemini did not return text. Please try again."
    except requests.exceptions.HTTPError as error:
        status_code = error.response.status_code if error.response is not None else None
        details = _extract_error_message(error.response) if error.response is not None else ""
        if status_code in (401, 403):
            return f"Gemini authentication failed. {details}".strip()
        return f"Gemini returned an error: {details}".strip()
    except requests.exceptions.RequestException:
        return "I could not reach Gemini right now. Please try again shortly."
    except (KeyError, IndexError, TypeError, ValueError):
        return "Gemini returned an unexpected response format."


def get_bot_response(
    user_message: str,
    chat_history: list[dict] | None = None,
    model_choice: str = DEFAULT_MODEL,
    image_bytes: bytes | None = None,
    image_mime_type: str | None = None,
    include_model: bool = False,
) -> str | tuple[str, str]:
    """Call selected AI model and return a safe response for patient chat."""
    prompt = (user_message or "").strip()
    safe_model = normalize_model_choice(model_choice)
    used_model = safe_model

    if not prompt and not image_bytes:
        quick_reply = _with_disclaimer(
            _with_doctor_suggestion("Please type your health question.", prompt)
        )
        return (quick_reply, used_model) if include_model else quick_reply

    if not prompt and image_bytes:
        prompt = "Please review this medical image and provide general health guidance."

    if _is_emergency_query(prompt):
        emergency_reply = _with_disclaimer(
            _with_doctor_suggestion(
                "This may be serious. Please seek immediate medical attention.",
                prompt,
            )
        )
        return (emergency_reply, used_model) if include_model else emergency_reply

    if safe_model == "gemini":
        raw_reply = _get_gemini_response(
            prompt,
            chat_history=chat_history,
            image_bytes=image_bytes,
            image_mime_type=image_mime_type,
        )
        lowered_reply = raw_reply.lower()
        gemini_quota_issue = (
            "quota exceeded" in lowered_reply
            or "rate limit" in lowered_reply
            or "you exceeded your current quota" in lowered_reply
        )
        if gemini_quota_issue:
            deepseek_reply = _get_deepseek_response(prompt, chat_history=chat_history)
            raw_reply = (
                "Gemini is currently unavailable due to quota limits. "
                "Switched to DeepSeek for this response.\n\n"
                f"{deepseek_reply}"
            )
            used_model = "deepseek"
    else:
        raw_reply = _get_deepseek_response(prompt, chat_history=chat_history)
        used_model = "deepseek"

    final_reply = _with_disclaimer(_with_doctor_suggestion(raw_reply, prompt))
    return (final_reply, used_model) if include_model else final_reply
