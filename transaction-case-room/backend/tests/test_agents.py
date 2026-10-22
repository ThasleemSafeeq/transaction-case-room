import unittest

from backend.app.agents import BankingAgent, CreditAgent, RiskAgent
from backend.app.data.fixtures import TRANSACTIONS
from backend.app.tools.banking_tools import BankingTools


class AgentTests(unittest.TestCase):
    def setUp(self):
        self.transactions = {item.transaction_id: item for item in TRANSACTIONS}
        self.trace = []

    def test_banking_agent_returns_fixture_backed_evidence(self):
        transaction = self.transactions["T-1042"]

        result = BankingAgent().collect_evidence(transaction, self.trace)

        self.assertEqual(result["transaction"]["transaction_id"], "T-1042")
        self.assertEqual(result["customer"]["customer_id"], "CUST-1001")
        self.assertEqual(len(result["transaction_history"]), 30)
        self.assertIn("Green Market", result["known_payees"])
        self.assertEqual(result["account"]["account_id"], "ACC-1001")
        self.assertEqual(result["loan_information"]["loans"][0]["loan_id"], "LOAN-2001")
        self.assertEqual(len(self.trace), 6)
        self.assertTrue(all(step["status"] == "success" for step in self.trace))

    def test_banking_tools_reject_unknown_transaction(self):
        with self.assertRaisesRegex(LookupError, "was not found"):
            BankingTools().get_transaction_details("T-MISSING")

    def test_risk_agent_calculates_weighted_score_from_triggered_rules(self):
        transaction = self.transactions["T-1042"]
        banking = BankingAgent().collect_evidence(transaction, self.trace)

        result = RiskAgent().calculate(
            transaction,
            banking["transaction_history"],
            banking["known_payees"],
        )

        self.assertEqual(result["score"], 75)
        self.assertEqual(
            [(rule["name"], rule["weight"]) for rule in result["triggered_rules"]],
            [
                ("unusually_large_amount", 35),
                ("new_payee", 25),
                ("unusual_hour", 15),
            ],
        )
        self.assertEqual(
            result["score"],
            sum(rule["weight"] for rule in result["triggered_rules"]),
        )
        self.assertTrue(all(rule["reason"] for rule in result["triggered_rules"]))

    def test_credit_agent_returns_recent_disbursal_evidence_when_available(self):
        transaction = self.transactions["T-1060"]
        banking = BankingAgent().collect_evidence(transaction, self.trace)

        evidence = CreditAgent().assess(
            banking["transaction"],
            banking["loan_information"],
        )

        self.assertEqual(
            {item["type"] for item in evidence},
            {"loan_exposure", "recent_loan_disbursal"},
        )
        self.assertEqual(
            evidence[1]["details"]["disbursals"][0]["transaction_id"],
            "T-1059",
        )

    def test_credit_agent_does_not_claim_a_recent_disbursal_for_old_loans(self):
        transaction = self.transactions["T-1042"]
        banking = BankingAgent().collect_evidence(transaction, self.trace)

        evidence = CreditAgent().assess(
            banking["transaction"],
            banking["loan_information"],
        )

        self.assertEqual([item["type"] for item in evidence], ["loan_exposure"])


if __name__ == "__main__":
    unittest.main()
