import unittest

from backend.app.interpreter import LocalInterpreter


class LocalInterpreterTests(unittest.TestCase):
    def setUp(self):
        self.interpreter = LocalInterpreter()

    def test_recognizes_every_supported_intent_and_unknown(self):
        examples = {
            "investigate_txn": "Please investigate T-1042",
            "account_summary": "Show account summary for CUST-1001",
            "list_suspicious": "List suspicious transactions",
            "explain_flag": "Explain flag on T-1042",
            "unknown": "Hello, what is the weather?",
        }
        for intent, message in examples.items():
            with self.subTest(intent=intent):
                result = self.interpreter.interpret(message)
                self.assertEqual(result["intent"], intent)
                self.assertEqual(result["interpreter"], "local")
                self.assertIn("entities", result)
                self.assertIn("missing_fields", result)

    def test_extracts_transaction_customer_and_account_ids(self):
        result = self.interpreter.interpret(
            "Show account summary CUST-1002 ACC-1002 and investigate T-1051"
        )

        self.assertEqual(result["entities"], {
            "transaction_id": "T-1051",
            "customer_id": "CUST-1002",
            "account_id": "ACC-1002",
        })

    def test_missing_identifier_is_reported_for_clarification(self):
        result = self.interpreter.interpret("Investigate a transaction")

        self.assertEqual(result["intent"], "investigate_txn")
        self.assertEqual(result["missing_fields"], ["transaction_id"])


if __name__ == "__main__":
    unittest.main()
