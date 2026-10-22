import unittest
from datetime import timedelta

from backend.app import create_app
from backend.app.data.fixtures import TRANSACTIONS


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = create_app().test_client()

    def test_health_endpoint(self):
        response = self.client.get("/api/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"status": "ok"})

    def test_transaction_list_includes_expected_count_and_stable_ids(self):
        response = self.client.get("/api/transactions")

        self.assertEqual(response.status_code, 200)
        transactions = response.get_json()
        self.assertEqual(len(transactions), 90)
        transaction_ids = {transaction["transaction_id"] for transaction in transactions}
        self.assertTrue({
            "T-1042", "T-1051", "T-1060", "T-1072", "T-1084", "T-1091",
        }.issubset(transaction_ids))
        self.assertEqual(
            self.client.get("/api/transactions/T-1042").get_json()["transaction_id"],
            "T-1042",
        )

    def test_customer_list_includes_profiles_and_transaction_history(self):
        response = self.client.get("/api/customers")

        self.assertEqual(response.status_code, 200)
        customers = response.get_json()
        self.assertEqual(len(customers), 3)
        self.assertTrue(all(customer["profile"] for customer in customers))
        self.assertTrue(all(customer["transaction_history"] for customer in customers))

    def test_unknown_transaction_returns_not_found(self):
        response = self.client.get("/api/transactions/does-not-exist")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json(), {"error": "Transaction not found"})

    def test_featured_transactions_represent_the_requested_scenarios(self):
        by_id = {transaction.transaction_id: transaction for transaction in TRANSACTIONS}
        new_payee = by_id["T-1042"]
        velocity_target = by_id["T-1051"]
        loan_transfer = by_id["T-1060"]
        known_payee = by_id["T-1072"]
        supplier_payment = by_id["T-1084"]
        small_odd_hour = by_id["T-1091"]
        velocity_window = [
            transaction for transaction in TRANSACTIONS
            if transaction.customer_id == velocity_target.customer_id
            and abs(transaction.timestamp - velocity_target.timestamp) <= timedelta(minutes=15)
        ]

        self.assertEqual(new_payee.timestamp.hour, 2)
        self.assertEqual(
            sum(transaction.payee == new_payee.payee for transaction in TRANSACTIONS),
            1,
        )
        self.assertGreaterEqual(len(velocity_window), 4)
        self.assertEqual(by_id["T-1059"].category, "loan_disbursal")
        self.assertLess(loan_transfer.timestamp - by_id["T-1059"].timestamp, timedelta(days=1))
        self.assertEqual(known_payee.payee, "Green Market")
        self.assertGreater(
            sum(
                transaction.payee == known_payee.payee
                for transaction in TRANSACTIONS
                if transaction.customer_id == known_payee.customer_id
            ),
            1,
        )
        self.assertGreater(supplier_payment.amount_cents, 1_000_000)
        self.assertLess(small_odd_hour.amount_cents, 1_000)
        self.assertEqual(small_odd_hour.timestamp.hour, 3)


if __name__ == "__main__":
    unittest.main()
