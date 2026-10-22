import unittest
import io
import json
from unittest.mock import patch

from backend.app import create_app
from backend.app.interpreter import GeminiSettings


class SupervisorApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = create_app().test_client()

    def query(self, message):
        return self.client.post("/api/query", json={"message": message})

    def test_unknown_query_asks_for_clarification_without_agents(self):
        with (
            patch("backend.app.supervisor.supervisor.BankingAgent") as banking,
            patch("backend.app.supervisor.supervisor.RiskAgent") as risk,
            patch("backend.app.supervisor.supervisor.CreditAgent") as credit,
        ):
            response = self.query("Hello there")

        self.assertEqual(response.status_code, 200)
        result = response.get_json()
        self.assertEqual(result["intent"], "unknown")
        self.assertEqual(result["interpreter"], "local")
        self.assertIn("What would you like to review?", result["answer"])
        self.assertEqual(result["trace"][0]["agents"], [])
        banking.assert_not_called()
        risk.assert_not_called()
        credit.assert_not_called()

    def test_investigate_routes_banking_risk_and_conditional_credit(self):
        response = self.query("Investigate T-1042")

        self.assertEqual(response.status_code, 200)
        result = response.get_json()
        self.assertEqual(result["intent"], "investigate_txn")
        agent_names = {entry["agent"] for entry in result["trace"] if entry.get("type") == "agent"}
        self.assertEqual(agent_names, {"BankingAgent", "RiskAgent", "CreditAgent"})
        self.assertEqual(result["risk_explanation"]["score"], 75)
        self.assertEqual(result["data"]["recommendation"], "Review required")

    def test_account_summary_runs_banking_only(self):
        response = self.query("Show account summary for CUST-1001")

        self.assertEqual(response.status_code, 200)
        result = response.get_json()
        agent_names = {entry["agent"] for entry in result["trace"] if entry.get("type") == "agent"}
        self.assertEqual(agent_names, {"BankingAgent"})
        self.assertEqual(result["data"]["account"]["account_id"], "ACC-1001")
        self.assertIsNone(result["risk_explanation"])

    def test_explain_flag_runs_risk_without_banking_or_credit(self):
        response = self.query("Explain flag for T-1042")

        self.assertEqual(response.status_code, 200)
        result = response.get_json()
        agent_names = {entry["agent"] for entry in result["trace"] if entry.get("type") == "agent"}
        self.assertEqual(agent_names, {"RiskAgent"})
        self.assertEqual(result["risk_explanation"]["score"], 75)

    def test_list_suspicious_routes_banking_and_risk(self):
        response = self.query("List suspicious transactions")

        self.assertEqual(response.status_code, 200)
        result = response.get_json()
        agent_names = {entry["agent"] for entry in result["trace"] if entry.get("type") == "agent"}
        self.assertEqual(agent_names, {"BankingAgent", "RiskAgent"})
        found_ids = {
            item["transaction"]["transaction_id"]
            for item in result["data"]["transactions"]
        }
        self.assertIn("T-1042", found_ids)
        self.assertIn("T-1051", found_ids)
        self.assertIn("T-1060", found_ids)
        self.assertIn("T-1084", found_ids)

    def test_invalid_transaction_id_runs_zero_agents(self):
        with (
            patch("backend.app.supervisor.supervisor.BankingAgent") as banking,
            patch("backend.app.supervisor.supervisor.RiskAgent") as risk,
            patch("backend.app.supervisor.supervisor.CreditAgent") as credit,
        ):
            response = self.query("Investigate T-9999")

        self.assertEqual(response.status_code, 404)
        self.assertIn("Unknown transaction ID", response.get_json()["error"])
        banking.assert_not_called()
        risk.assert_not_called()
        credit.assert_not_called()

    def test_invalid_customer_id_runs_zero_agents(self):
        with (
            patch("backend.app.supervisor.supervisor.BankingAgent") as banking,
            patch("backend.app.supervisor.supervisor.RiskAgent") as risk,
            patch("backend.app.supervisor.supervisor.CreditAgent") as credit,
        ):
            response = self.query("Show account summary for CUST-9999")

        self.assertEqual(response.status_code, 404)
        self.assertIn("Unknown customer ID", response.get_json()["error"])
        banking.assert_not_called()
        risk.assert_not_called()
        credit.assert_not_called()

    def test_customer_transaction_ownership_mismatch_runs_zero_agents(self):
        with (
            patch("backend.app.supervisor.supervisor.BankingAgent") as banking,
            patch("backend.app.supervisor.supervisor.RiskAgent") as risk,
            patch("backend.app.supervisor.supervisor.CreditAgent") as credit,
        ):
            response = self.query("Investigate T-1042 for CUST-1002")

        self.assertEqual(response.status_code, 400)
        self.assertIn("does not belong", response.get_json()["error"])
        banking.assert_not_called()
        risk.assert_not_called()
        credit.assert_not_called()

    def test_account_customer_ownership_mismatch_runs_zero_agents(self):
        with (
            patch("backend.app.supervisor.supervisor.BankingAgent") as banking,
            patch("backend.app.supervisor.supervisor.RiskAgent") as risk,
            patch("backend.app.supervisor.supervisor.CreditAgent") as credit,
        ):
            response = self.query("Show account summary CUST-1001 ACC-1002")

        self.assertEqual(response.status_code, 400)
        self.assertIn("does not belong", response.get_json()["error"])
        banking.assert_not_called()
        risk.assert_not_called()
        credit.assert_not_called()

    def test_missing_identifier_requests_clarification_without_agents(self):
        with (
            patch("backend.app.supervisor.supervisor.BankingAgent") as banking,
            patch("backend.app.supervisor.supervisor.RiskAgent") as risk,
            patch("backend.app.supervisor.supervisor.CreditAgent") as credit,
        ):
            response = self.query("Investigate a transaction")

        self.assertEqual(response.status_code, 200)
        self.assertIn("transaction_id", response.get_json()["answer"])
        self.assertEqual(response.get_json()["trace"][0]["agents"], [])
        banking.assert_not_called()
        risk.assert_not_called()
        credit.assert_not_called()

    def test_optional_gemini_routes_only_validated_intent_and_ids(self):
        response_body = io.BytesIO(json.dumps({
            "output_text": json.dumps({
                "intent": "investigate_txn",
                "entities": {
                    "transaction_id": "T-1042",
                    "customer_id": "",
                    "account_id": "",
                },
            }),
        }).encode())
        with (
            patch(
                "backend.app.interpreter.gemini_interpreter.load_gemini_settings",
                return_value=GeminiSettings(enabled=True, api_key="mock-key"),
            ),
            patch(
                "backend.app.interpreter.gemini_interpreter.urlopen",
                return_value=response_body,
            ) as urlopen,
        ):
            response = self.query("Please investigate T-1042")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["interpreter"], "gemini")
        self.assertEqual(response.get_json()["intent"], "investigate_txn")
        request_payload = json.loads(urlopen.call_args.args[0].data)
        self.assertNotIn("risk_score", request_payload)
        self.assertNotIn("account balance", request_payload["input"].lower())


if __name__ == "__main__":
    unittest.main()
