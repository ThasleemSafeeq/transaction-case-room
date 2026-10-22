import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from backend.app.interpreter import (
    GeminiSettings,
    LocalInterpreter,
    OptionalGeminiInterpreter,
    load_gemini_settings,
)


def routing_response(intent="investigate_txn", transaction_id="T-1042"):
    return {
        "intent": intent,
        "entities": {
            "transaction_id": transaction_id,
            "customer_id": "",
            "account_id": "",
        },
    }


class GeminiInterpreterTests(unittest.TestCase):
    def test_disabled_or_missing_key_uses_local_without_network(self):
        settings = GeminiSettings(enabled=True, api_key="")
        interpreter = OptionalGeminiInterpreter(settings=settings)

        with patch("backend.app.interpreter.gemini_interpreter.urlopen") as urlopen:
            result = interpreter.interpret("Investigate T-1042")

        self.assertEqual(result["intent"], "investigate_txn")
        self.assertEqual(result["interpreter"], "local")
        self.assertEqual(result["fallback_reason"], "gemini_missing_api_key")
        urlopen.assert_not_called()

    def test_disabled_switch_uses_local_even_with_a_key(self):
        interpreter = OptionalGeminiInterpreter(
            settings=GeminiSettings(enabled=False, api_key="not-a-real-key")
        )

        with patch("backend.app.interpreter.gemini_interpreter.urlopen") as urlopen:
            result = interpreter.interpret("Investigate T-1042")

        self.assertEqual(result["interpreter"], "local")
        self.assertEqual(result["fallback_reason"], "gemini_disabled")
        urlopen.assert_not_called()

    def test_valid_gemini_routing_is_normalized_and_has_no_financial_output(self):
        response = io.BytesIO(json.dumps({
            "output_text": json.dumps(routing_response()),
        }).encode())
        interpreter = OptionalGeminiInterpreter(
            settings=GeminiSettings(enabled=True, api_key="test-key")
        )

        with patch(
            "backend.app.interpreter.gemini_interpreter.urlopen",
            return_value=response,
        ) as urlopen:
            result = interpreter.interpret("Please investigate T-1042")

        self.assertEqual(result, {
            "intent": "investigate_txn",
            "entities": {
                "transaction_id": "T-1042",
                "customer_id": None,
                "account_id": None,
            },
            "confidence": None,
            "missing_fields": [],
            "interpreter": "gemini",
        })
        request = urlopen.call_args.args[0]
        self.assertEqual(request.get_header("X-goog-api-key"), "test-key")
        payload = json.loads(request.data)
        self.assertEqual(payload["store"], False)
        self.assertIn("Do not answer", payload["input"])
        self.assertNotIn("risk_score", payload)
        self.assertNotIn("evidence", payload)

    def test_rejects_unknown_intent_and_falls_back(self):
        self.assert_local_fallback(routing_response(intent="approve_fraud"))

    def test_rejects_missing_required_identifier_and_falls_back(self):
        self.assert_local_fallback(routing_response(transaction_id=""))

    def test_rejects_unexpected_and_malformed_identifier_fields(self):
        unexpected = routing_response()
        unexpected["risk_score"] = 100
        self.assert_local_fallback(unexpected)

        malformed = routing_response()
        malformed["entities"]["transaction_id"] = "T-1042 and CUST-1001"
        self.assert_local_fallback(malformed)

    def test_quota_api_and_timeout_errors_fall_back(self):
        quota_body = io.BytesIO(b"quota response")
        quota_error = HTTPError(
            "https://example.invalid", 429, "quota", {}, quota_body
        )
        quota_interpreter = OptionalGeminiInterpreter(
            settings=GeminiSettings(enabled=True, api_key="test-key")
        )
        with patch(
            "backend.app.interpreter.gemini_interpreter.urlopen",
            side_effect=quota_error,
        ):
            quota_result = quota_interpreter.interpret("Investigate T-1042")
        self.assertTrue(quota_body.closed)
        self.assertEqual(quota_result["interpreter"], "local")

        for error in (
            TimeoutError("timed out"),
            OSError("service unavailable"),
        ):
            with self.subTest(error=type(error).__name__):
                interpreter = OptionalGeminiInterpreter(
                    settings=GeminiSettings(enabled=True, api_key="test-key")
                )
                with patch(
                    "backend.app.interpreter.gemini_interpreter.urlopen",
                    side_effect=error,
                ):
                    result = interpreter.interpret("Investigate T-1042")
                self.assertEqual(result["interpreter"], "local")
                self.assertEqual(
                    result["fallback_reason"],
                    "gemini_request_or_output_failed",
                )

    def test_environment_settings_are_read_from_requested_env_file(self):
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / ".env"
            env_file.write_text(
                "GEMINI_ENABLED=true\n"
                "GEMINI_API_KEY='file-only-key'\n"
                "GEMINI_MODEL=gemini-test\n"
                "GEMINI_TIMEOUT_SECONDS=2.5\n",
                encoding="utf-8",
            )

            settings = load_gemini_settings(env_file)

        self.assertTrue(settings.enabled)
        self.assertEqual(settings.api_key, "file-only-key")
        self.assertEqual(settings.model, "gemini-test")
        self.assertEqual(settings.timeout_seconds, 2.5)

    def test_environment_variables_are_not_used_as_gemini_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            missing_env_file = Path(directory) / "missing.env"
            with patch.dict(os.environ, {
                "GEMINI_ENABLED": "true",
                "GEMINI_API_KEY": "process-environment-key",
            }):
                settings = load_gemini_settings(missing_env_file)

        self.assertFalse(settings.enabled)
        self.assertEqual(settings.api_key, "")

    def assert_local_fallback(self, response):
        response_file = io.BytesIO(json.dumps({"output_text": json.dumps(response)}).encode())
        interpreter = OptionalGeminiInterpreter(
            settings=GeminiSettings(enabled=True, api_key="test-key")
        )
        with patch(
            "backend.app.interpreter.gemini_interpreter.urlopen",
            return_value=response_file,
        ):
            result = interpreter.interpret("Investigate T-1042")
        self.assertEqual(result["interpreter"], "local")
        self.assertEqual(result["fallback_reason"], "gemini_request_or_output_failed")


if __name__ == "__main__":
    unittest.main()
