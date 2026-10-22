import unittest
from dataclasses import replace
from datetime import datetime, timezone

from backend.data import (
    ACCOUNTS,
    CUSTOMERS,
    LOANS,
    TRANSACTIONS,
    build_transactions,
    validate_dataset,
)


class MockDatasetTests(unittest.TestCase):
    def test_dataset_has_three_customers_and_ninety_transactions(self):
        self.assertEqual(len(CUSTOMERS), 3)
        self.assertEqual(len(TRANSACTIONS), 90)

    def test_identifiers_are_unique_and_records_have_valid_relationships(self):
        validate_dataset(CUSTOMERS, ACCOUNTS, TRANSACTIONS, LOANS)

        self.assertEqual(len({customer.customer_id for customer in CUSTOMERS}), 3)
        self.assertEqual(len({transaction.transaction_id for transaction in TRANSACTIONS}), 90)
        for customer in CUSTOMERS:
            customer_transactions = [
                transaction for transaction in TRANSACTIONS
                if transaction.customer_id == customer.customer_id
            ]
            self.assertEqual(len(customer_transactions), 30)

    def test_transactions_are_reproducible_and_use_timezone_aware_timestamps(self):
        self.assertEqual(build_transactions(), TRANSACTIONS)
        self.assertTrue(all(
            transaction.timestamp.tzinfo == timezone.utc
            for transaction in TRANSACTIONS
        ))
        self.assertEqual(
            TRANSACTIONS[0].timestamp,
            datetime(2026, 10, 1, 10, 7, tzinfo=timezone.utc),
        )

    def test_salary_credits_have_consistent_payee_and_category(self):
        credits = [transaction for transaction in TRANSACTIONS if transaction.direction == "credit"]

        self.assertEqual(len(credits), 6)
        self.assertTrue(all(
            transaction.payee == "Pinecone Payroll" and transaction.category == "income"
            for transaction in credits
        ))

    def test_validator_rejects_duplicate_customer_ids(self):
        duplicate_customers = CUSTOMERS + (CUSTOMERS[0],)

        with self.assertRaisesRegex(ValueError, "Customer identifiers must be unique"):
            validate_dataset(duplicate_customers, ACCOUNTS, TRANSACTIONS, LOANS)

    def test_validator_rejects_accounts_owned_by_unknown_customers(self):
        bad_accounts = (replace(ACCOUNTS[0], customer_id="CUST-MISSING"),) + ACCOUNTS[1:]

        with self.assertRaisesRegex(ValueError, "references an unknown customer"):
            validate_dataset(CUSTOMERS, bad_accounts, TRANSACTIONS, LOANS)

    def test_validator_rejects_transaction_account_owner_mismatch(self):
        bad_transactions = (
            replace(TRANSACTIONS[0], customer_id="CUST-1002"),
        ) + TRANSACTIONS[1:]

        with self.assertRaisesRegex(ValueError, "account owner does not match"):
            validate_dataset(CUSTOMERS, ACCOUNTS, bad_transactions, LOANS)

    def test_validator_rejects_nonpositive_transaction_amounts(self):
        bad_transactions = (
            replace(TRANSACTIONS[0], amount_cents=0),
        ) + TRANSACTIONS[1:]

        with self.assertRaisesRegex(ValueError, "amount must be positive"):
            validate_dataset(CUSTOMERS, ACCOUNTS, bad_transactions, LOANS)


if __name__ == "__main__":
    unittest.main()
