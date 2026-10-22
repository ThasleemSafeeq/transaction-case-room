import json
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from .local_interpreter import LocalInterpreter


_ALLOWED_INTENTS = {
    "investigate_txn",
    "account_summary",
    "list_suspicious",
    "explain_flag",
    "unknown",
}
_ENTITY_PATTERNS = {
    "transaction_id": re.compile(r"(?:T-\d+|TX-\d+-\d{3})", re.IGNORECASE),
    "customer_id": re.compile(r"CUST-\d+", re.IGNORECASE),
    "account_id": re.compile(r"ACC-\d+", re.IGNORECASE),
}
_BACKEND_ENV = Path(__file__).resolve().parents[2] / ".env"
_INTERACTIONS_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"
_ROUTING_SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {
            "type": "string",
            "enum": sorted(_ALLOWED_INTENTS),
        },
        "entities": {
            "type": "object",
            "properties": {
                "transaction_id": {"type": "string"},
                "customer_id": {"type": "string"},
                "account_id": {"type": "string"},
            },
            "required": ["transaction_id", "customer_id", "account_id"],
        },
    },
    "required": ["intent", "entities"],
}


@dataclass(frozen=True)
class GeminiSettings:
    enabled: bool = False
    api_key: str = ""
    model: str = "gemini-3.8-flash"
    timeout_seconds: float = 5.0


def _read_backend_env(path: Path = _BACKEND_ENV) -> dict[str, str]:
    values = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return values

    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, separator, value = line.partition("=")
        if not separator:
            continue
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        else:
            value = re.split(r"\s+#", value, maxsplit=1)[0].strip()
        values[key] = value
    return values


def load_gemini_settings(path: Path = _BACKEND_ENV) -> GeminiSettings:
    values = _read_backend_env(path)
    try:
        timeout = float(values.get("GEMINI_TIMEOUT_SECONDS", "5"))
    except ValueError:
        timeout = 5.0
    if timeout <= 0:
        timeout = 5.0
    return GeminiSettings(
        enabled=values.get("GEMINI_ENABLED", "false").strip().lower() == "true",
        api_key=values.get("GEMINI_API_KEY", "").strip(),
        model=values.get("GEMINI_MODEL", "gemini-3.8-flash").strip() or "gemini-3.8-flash",
        timeout_seconds=timeout,
    )


class OptionalGeminiInterpreter:
    """Uses Gemini for intent/entity routing only and otherwise defers locally."""

    def __init__(
        self,
        local_interpreter: LocalInterpreter | None = None,
        settings: GeminiSettings | None = None,
    ) -> None:
        self.local_interpreter = local_interpreter or LocalInterpreter()
        self.settings = settings or load_gemini_settings()

    def interpret(self, text: str) -> dict:
        if not self.settings.enabled:
            return self._fallback(text, "gemini_disabled")
        if not self.settings.api_key:
            return self._fallback(text, "gemini_missing_api_key")

        try:
            response = self._request_routing(text)
            routing = self._validate_response(response)
        except HTTPError as error:
            error.close()
            return self._fallback(text, "gemini_request_or_output_failed")
        except Exception:
            return self._fallback(text, "gemini_request_or_output_failed")
        routing["interpreter"] = "gemini"
        return routing

    def _request_routing(self, text: str) -> dict:
        prompt = (
            "Classify the user's request for a fictional banking case-room application. "
            "Return only the requested routing JSON. Do not answer the request, calculate "
            "financial values or risk, produce evidence, or decide fraud. Extract only "
            "identifiers explicitly present in the user's text. Use empty strings for "
            "identifiers not provided.\n"
            "Allowed intents: investigate_txn, account_summary, list_suspicious, "
            "explain_flag, unknown.\n"
            "transaction_id formats: T-<digits> or TX-<digits>-<three digits>. "
            "customer_id format: CUST-<digits>. account_id format: ACC-<digits>.\n"
            f"User request: {text}"
        )
        payload = {
            "model": self.settings.model,
            "input": prompt,
            "store": False,
            "response_format": {
                "type": "text",
                "mime_type": "application/json",
                "schema": _ROUTING_SCHEMA,
            },
        }
        request = Request(
            _INTERACTIONS_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": self.settings.api_key,
            },
            method="POST",
        )
        with urlopen(request, timeout=self.settings.timeout_seconds) as response:
            api_response = json.loads(response.read().decode("utf-8"))
        output = self._extract_output_text(api_response)
        parsed = json.loads(output)
        if not isinstance(parsed, dict):
            raise ValueError("Routing output must be an object")
        return parsed

    @staticmethod
    def _extract_output_text(response: dict) -> str:
        output_text = response.get("output_text")
        if isinstance(output_text, str):
            return output_text
        steps = response.get("steps")
        if isinstance(steps, list):
            for step in reversed(steps):
                if not isinstance(step, dict) or step.get("type") != "model_output":
                    continue
                content = step.get("content")
                if isinstance(content, str):
                    return content
                if isinstance(content, list):
                    text = "".join(
                        item["text"]
                        for item in content
                        if isinstance(item, dict)
                        and item.get("type") == "text"
                        and isinstance(item.get("text"), str)
                    )
                    if text:
                        return text
        raise ValueError("Gemini response did not contain routing text")

    def _validate_response(self, response: dict) -> dict:
        if set(response) != {"intent", "entities"}:
            raise ValueError("Unexpected routing response fields")
        intent = response["intent"]
        entities = response["entities"]
        if intent not in _ALLOWED_INTENTS or not isinstance(entities, dict):
            raise ValueError("Unsupported intent or invalid entities")
        if set(entities) != set(_ENTITY_PATTERNS):
            raise ValueError("Routing entities do not match the expected schema")

        normalized_entities = {}
        for field, pattern in _ENTITY_PATTERNS.items():
            value = entities[field]
            if not isinstance(value, str):
                raise ValueError("Entity values must be strings")
            if not value:
                normalized_entities[field] = None
            elif pattern.fullmatch(value):
                normalized_entities[field] = value.upper()
            else:
                raise ValueError("Invalid entity identifier format")

        required_field = {
            "investigate_txn": "transaction_id",
            "explain_flag": "transaction_id",
        }.get(intent)
        if required_field and not normalized_entities[required_field]:
            raise ValueError("Required transaction identifier is missing")
        if intent == "account_summary" and not (
            normalized_entities["customer_id"] or normalized_entities["account_id"]
        ):
            raise ValueError("Required account or customer identifier is missing")

        return {
            "intent": intent,
            "entities": normalized_entities,
            "confidence": None,
            "missing_fields": [],
        }

    def _fallback(self, text: str, reason: str) -> dict:
        routing = self.local_interpreter.interpret(text)
        routing["fallback_reason"] = reason
        return routing
