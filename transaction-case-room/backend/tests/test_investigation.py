import unittest
from unittest.mock import patch

from backend.app import create_app
from backend.app.data.fixtures import TRANSACTIONS


class InvestigationApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = create_app().test_client()

    def investigate(self, transaction_id):
        return self.client.post("/api/investigate", json={"transaction_id": transaction_id})

    def test_unknown_id_returns_404_before_any_agent_runs(self):
        with (
            patch("backend.app.routes.BankingAgent") as banking_agent,
            patch("backend.app.routes.RiskAgent") as risk_agent,
            patch("backend.app.routes.CreditAgent") as credit_agent,
        ):
            response = self.investigate("T-UNKNOWN")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json(), {"error": "Transaction not found"})
        banking_agent.assert_not_called()
        risk_agent.assert_not_called()
        credit_agent.assert_not_called()

    def test_transaction_id_is_required(self):
        response = self.client.post("/api/investigate", json={})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "A transaction_id string is required")

    def test_valid_investigation_returns_evidence_score_and_tool_trace(self):
        response = self.investigate("T-1042")

        self.assertEqual(response.status_code, 200)
        result = response.get_json()
        self.assertEqual(result["transaction"]["transaction_id"], "T-1042")
        self.assertEqual(result["customer"]["customer_id"], "CUST-1001")
        self.assertEqual(result["risk_score"], 75)
        self.assertEqual(result["recommendation"], "Review required")
        self.assertTrue(result["evidence_cards"])
        self.assertEqual(len(result["execution_trace"]), 6)
        for entry in result["execution_trace"]:
            self.assertEqual(
                set(entry),
                {"agent", "tool", "input", "output", "duration_ms", "status"},
            )
            self.assertEqual(entry["status"], "success")
            self.assertIsInstance(entry["duration_ms"], (int, float))
            self.assertGreaterEqual(entry["duration_ms"], 0)

    def test_tool_failure_is_visible_in_response_and_trace(self):
        with patch(
            "backend.app.agents.banking_agent.BankingTools.get_customer_profile",
            side_effect=LookupError("Fixture customer lookup failed"),
        ):
            response = self.investigate("T-1042")

        self.assertEqual(response.status_code, 500)
        result = response.get_json()
        self.assertEqual(result["details"], "Fixture customer lookup failed")
        failed_entries = [
            entry for entry in result["execution_trace"]
            if entry["status"] == "failed"
        ]
        self.assertEqual(len(failed_entries), 1)
        self.assertEqual(failed_entries[0]["tool"], "get_customer_profile")
        self.assertEqual(
            failed_entries[0]["output"]["error_type"],
            "LookupError",
        )

    def test_all_six_fixture_scenarios_get_scores_from_the_rules(self):
        expected = {
            "T-1042": (75, {"unusually_large_amount", "new_payee", "unusual_hour"}),
            "T-1051": (25, {"transaction_velocity"}),
            "T-1060": (60, {"unusually_large_amount", "new_payee"}),
            "T-1072": (0, set()),
            "T-1084": (35, {"unusually_large_amount"}),
            "T-1091": (15, {"unusual_hour"}),
        }
        self.assertTrue(expected.keys() <= {item.transaction_id for item in TRANSACTIONS})

        for transaction_id, (score, rule_names) in expected.items():
            with self.subTest(transaction_id=transaction_id):
                response = self.investigate(transaction_id)
                self.assertEqual(response.status_code, 200)
                result = response.get_json()
                self.assertEqual(result["risk_score"], score)
                self.assertEqual(
                    {rule["name"] for rule in result["triggered_rules"]},
                    rule_names,
                )

    def test_large_transfer_after_recent_loan_has_credit_evidence(self):
        response = self.investigate("T-1060")

        self.assertEqual(response.status_code, 200)
        result = response.get_json()
        evidence_types = {card["type"] for card in result["evidence_cards"]}
        self.assertIn("loan_exposure", evidence_types)
        self.assertIn("recent_loan_disbursal", evidence_types)
        self.assertEqual(result["recommendation"], "Review required")

    def test_large_legitimate_supplier_payment_remains_identified_as_known_payee(self):
        response = self.investigate("T-1084")

        self.assertEqual(response.status_code, 200)
        result = response.get_json()
        self.assertEqual(result["risk_score"], 35)
        self.assertEqual(
            {rule["name"] for rule in result["triggered_rules"]},
            {"unusually_large_amount"},
        )
        payee_card = next(card for card in result["evidence_cards"] if card["type"] == "known_payees")
        self.assertIn("Cedar Restaurant Supply", payee_card["details"]["payees"])


if __name__ == "__main__":
    unittest.main()
