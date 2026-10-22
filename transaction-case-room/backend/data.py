"""Deterministic fictional banking data for local development and tests."""

from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from typing import Sequence, TypeVar


@dataclass(frozen=True)
class Customer:
    customer_id: str
    full_name: str
    segment: str


@dataclass(frozen=True)
class Account:
    account_id: str
    customer_id: str
    account_type: str
    balance_cents: int
    currency: str = "USD"
    status: str = "active"


@dataclass(frozen=True)
class Transaction:
    transaction_id: str
    account_id: str
    customer_id: str
    timestamp: datetime
    amount_cents: int
    currency: str
    direction: str
    payee: str
    category: str
    channel: str
    status: str = "posted"


@dataclass(frozen=True)
class Loan:
    loan_id: str
    customer_id: str
    loan_type: str
    principal_balance_cents: int
    annual_interest_rate: float
    status: str = "active"


CUSTOMERS = (
    Customer("CUST-1001", "Avery Quinn", "personal"),
    Customer("CUST-1002", "Jordan Lee", "small_business"),
    Customer("CUST-1003", "Morgan Reed", "personal"),
)

ACCOUNTS = (
    Account("ACC-1001", "CUST-1001", "checking", 1_245_068),
    Account("ACC-1002", "CUST-1002", "checking", 840_012),
    Account("ACC-1003", "CUST-1003", "checking", 2_267_591),
)

LOANS = (
    Loan("LOAN-2001", "CUST-1001", "auto", 1_120_000, 0.049),
    Loan("LOAN-2002", "CUST-1002", "small_business", 3_850_000, 0.0725),
)

_RECURRENT_PAYEES = (
    ("Green Market", "groceries"),
    ("Metro Transit", "transport"),
    ("Harbor Utilities", "utilities"),
    ("Juniper Cafe", "dining"),
    ("Pinecone Payroll", "income"),
)
_CUSTOMER_ACCOUNT = {
    "CUST-1001": "ACC-1001",
    "CUST-1002": "ACC-1002",
    "CUST-1003": "ACC-1003",
}
_BASE_DATE = datetime(2026, 10, 1, tzinfo=timezone.utc)


def build_transactions() -> tuple[Transaction, ...]:
    """Build 30 stable daily transactions for each fictional customer."""
    transactions = []
    for customer_index, customer in enumerate(CUSTOMERS):
        for day in range(1, 31):
            payee, category = _RECURRENT_PAYEES[(day + customer_index) % len(_RECURRENT_PAYEES)]
            direction = "credit" if day in (1, 15) else "debit"
            amount_cents = (
                210_000 + customer_index * 12_500
                if direction == "credit"
                else 1_200 + ((day * 791 + customer_index * 1_201) % 38_000)
            )
            if direction == "credit":
                payee, category = "Pinecone Payroll", "income"
            transaction_time = time(hour=9 + (day + customer_index) % 9, minute=(day * 7) % 60)

            if customer.customer_id == "CUST-1001" and day == 25:
                payee, category = "Summit Devices", "electronics"
                amount_cents, transaction_time = 245_000, time(2, 14)
            elif customer.customer_id == "CUST-1002" and day in (22, 23, 24):
                payee, category = "Green Market", "groceries"
                amount_cents = (10_500, 11_200, 8_500)[day - 22]
                transaction_time = time(11, (5, 12, 21)[day - 22])
            elif customer.customer_id == "CUST-1003" and day == 27:
                payee, category = "Cedar Ridge Travel", "travel"
                amount_cents, transaction_time = 178_000, time(23, 48)

            timestamp = _BASE_DATE + timedelta(days=day - 1)
            timestamp = timestamp.replace(
                hour=transaction_time.hour,
                minute=transaction_time.minute,
            )
            transactions.append(
                Transaction(
                    transaction_id=f"TXN-{1000 + customer_index + 1}-{day:03d}",
                    account_id=_CUSTOMER_ACCOUNT[customer.customer_id],
                    customer_id=customer.customer_id,
                    timestamp=timestamp,
                    amount_cents=amount_cents,
                    currency="USD",
                    direction=direction,
                    payee=payee,
                    category=category,
                    channel="online" if day % 3 else "card",
                )
            )
    return tuple(transactions)


TRANSACTIONS = build_transactions()

_Record = TypeVar("_Record")


def _require_unique(records: Sequence[_Record], key: str, entity: str) -> None:
    values = [getattr(record, key) for record in records]
    if len(values) != len(set(values)):
        raise ValueError(f"{entity} identifiers must be unique")


def validate_dataset(
    customers: Sequence[Customer],
    accounts: Sequence[Account],
    transactions: Sequence[Transaction],
    loans: Sequence[Loan],
) -> None:
    """Reject duplicate identifiers and records with broken customer/account links."""
    _require_unique(customers, "customer_id", "Customer")
    _require_unique(accounts, "account_id", "Account")
    _require_unique(transactions, "transaction_id", "Transaction")
    _require_unique(loans, "loan_id", "Loan")

    customer_ids = {customer.customer_id for customer in customers}
    account_by_id = {account.account_id: account for account in accounts}
    for account in accounts:
        if account.customer_id not in customer_ids:
            raise ValueError(f"Account {account.account_id} references an unknown customer")

    for transaction in transactions:
        account = account_by_id.get(transaction.account_id)
        if transaction.customer_id not in customer_ids or account is None:
            raise ValueError(f"Transaction {transaction.transaction_id} has an unknown customer or account")
        if account.customer_id != transaction.customer_id:
            raise ValueError(f"Transaction {transaction.transaction_id} account owner does not match")
        if transaction.amount_cents <= 0:
            raise ValueError(f"Transaction {transaction.transaction_id} amount must be positive")

    for loan in loans:
        if loan.customer_id not in customer_ids:
            raise ValueError(f"Loan {loan.loan_id} references an unknown customer")
        if loan.principal_balance_cents < 0:
            raise ValueError(f"Loan {loan.loan_id} balance cannot be negative")


validate_dataset(CUSTOMERS, ACCOUNTS, TRANSACTIONS, LOANS)
