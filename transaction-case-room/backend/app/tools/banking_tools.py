from dataclasses import asdict
from datetime import datetime

from ..data.fixtures import (
    ACCOUNTS,
    CUSTOMERS,
    LOANS,
    REGISTERED_PAYEES,
    TRANSACTIONS,
)


def _isoformat(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


class BankingTools:
    def get_transaction_details(self, transaction_id: str) -> dict:
        transaction = next(
            (item for item in TRANSACTIONS if item.transaction_id == transaction_id),
            None,
        )
        if transaction is None:
            raise LookupError(f"Transaction {transaction_id} was not found")
        return transaction.to_dict()

    def get_customer_profile(self, customer_id: str) -> dict:
        customer = next((item for item in CUSTOMERS if item.customer_id == customer_id), None)
        if customer is None:
            raise LookupError(f"Customer {customer_id} was not found")
        return {
            "customer_id": customer.customer_id,
            "full_name": customer.full_name,
            "segment": customer.segment,
            "profile": {"age": customer.age, "occupation": customer.occupation},
            "account_id": customer.account_id,
        }

    def get_transaction_history(self, customer_id: str) -> list[dict]:
        if not any(customer.customer_id == customer_id for customer in CUSTOMERS):
            raise LookupError(f"Customer {customer_id} was not found")
        return [
            item.to_dict()
            for item in TRANSACTIONS
            if item.customer_id == customer_id
        ]

    def get_known_payees(self, customer_id: str, before: datetime) -> list[str]:
        if not any(customer.customer_id == customer_id for customer in CUSTOMERS):
            raise LookupError(f"Customer {customer_id} was not found")
        observed = {
            item.payee
            for item in TRANSACTIONS
            if item.customer_id == customer_id and item.timestamp < before
        }
        registered = set(REGISTERED_PAYEES.get(customer_id, ()))
        return sorted(observed | registered)

    def get_account_summary(self, customer_id: str) -> dict:
        account = next((item for item in ACCOUNTS if item.customer_id == customer_id), None)
        if account is None:
            raise LookupError(f"Account for customer {customer_id} was not found")
        account_transactions = [
            item for item in TRANSACTIONS if item.account_id == account.account_id
        ]
        return {
            "account_id": account.account_id,
            "customer_id": account.customer_id,
            "account_type": account.account_type,
            "balance_cents": account.balance_cents,
            "currency": account.currency,
            "status": account.status,
            "transaction_count": len(account_transactions),
            "debit_total_cents": sum(
                item.amount_cents for item in account_transactions if item.direction == "debit"
            ),
            "credit_total_cents": sum(
                item.amount_cents for item in account_transactions if item.direction == "credit"
            ),
        }

    def get_loan_information(self, customer_id: str) -> dict:
        if not any(customer.customer_id == customer_id for customer in CUSTOMERS):
            raise LookupError(f"Customer {customer_id} was not found")
        loans = [
            {
                **asdict(loan),
                "disbursed_at": _isoformat(loan.disbursed_at),
            }
            for loan in LOANS
            if loan.customer_id == customer_id
        ]
        disbursals = [
            item.to_dict()
            for item in TRANSACTIONS
            if item.customer_id == customer_id and item.category == "loan_disbursal"
        ]
        return {"loans": loans, "disbursals": disbursals}
