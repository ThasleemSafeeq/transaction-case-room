from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone


@dataclass(frozen=True)
class Customer:
    customer_id: str
    full_name: str
    segment: str
    age: int
    occupation: str
    account_id: str


@dataclass(frozen=True)
class Transaction:
    transaction_id: str
    customer_id: str
    account_id: str
    timestamp: datetime
    amount_cents: int
    currency: str
    direction: str
    payee: str
    category: str
    status: str = "posted"
    memo: str = ""

    def to_dict(self) -> dict:
        transaction = asdict(self)
        transaction["timestamp"] = self.timestamp.isoformat().replace("+00:00", "Z")
        transaction["amount"] = self.amount_cents / 100
        return transaction


@dataclass(frozen=True)
class Account:
    account_id: str
    customer_id: str
    account_type: str
    balance_cents: int
    currency: str = "USD"
    status: str = "active"


@dataclass(frozen=True)
class Loan:
    loan_id: str
    customer_id: str
    loan_type: str
    principal_balance_cents: int
    annual_interest_rate: float
    disbursed_at: datetime
    disbursed_amount_cents: int
    status: str = "active"


CUSTOMERS = (
    Customer("CUST-1001", "Avery Quinn", "personal", 34, "architect", "ACC-1001"),
    Customer("CUST-1002", "Jordan Lee", "small_business", 42, "restaurant owner", "ACC-1002"),
    Customer("CUST-1003", "Morgan Reed", "personal", 29, "teacher", "ACC-1003"),
)

ACCOUNTS = (
    Account("ACC-1001", "CUST-1001", "checking", 1_245_068),
    Account("ACC-1002", "CUST-1002", "business_checking", 840_012),
    Account("ACC-1003", "CUST-1003", "checking", 2_267_591),
)

LOANS = (
    Loan(
        "LOAN-2001", "CUST-1001", "auto", 1_120_000, 0.049,
        datetime(2026, 3, 1, tzinfo=timezone.utc), 1_500_000,
    ),
    Loan(
        "LOAN-2002", "CUST-1002", "small_business", 3_850_000, 0.0725,
        datetime(2026, 1, 15, tzinfo=timezone.utc), 4_000_000,
    ),
    Loan(
        "LOAN-2003", "CUST-1003", "personal", 1_450_000, 0.061,
        datetime(2026, 10, 16, 15, 0, tzinfo=timezone.utc), 1_500_000,
    ),
)

REGISTERED_PAYEES = {
    "CUST-1001": ("Green Market", "Metro Transit", "Harbor Utilities", "Juniper Cafe", "Pinecone Payroll"),
    "CUST-1002": ("Green Market", "Metro Transit", "Harbor Utilities", "Juniper Cafe", "Pinecone Payroll", "Harbor Foods", "Cedar Restaurant Supply"),
    "CUST-1003": ("Green Market", "Metro Transit", "Harbor Utilities", "Juniper Cafe", "Pinecone Payroll", "Pinecone Lending"),
}

_FEATURED_TRANSACTIONS = (
    Transaction(
        "T-1042", "CUST-1001", "ACC-1001",
        datetime(2026, 10, 16, 2, 14, tzinfo=timezone.utc),
        245_000, "USD", "debit", "Summit Devices", "electronics",
        memo="First payment to this recipient",
    ),
    Transaction(
        "T-1051", "CUST-1002", "ACC-1002",
        datetime(2026, 10, 17, 10, 15, tzinfo=timezone.utc),
        48_500, "USD", "debit", "Harbor Foods", "inventory",
        memo="Part of a cluster of same-day payments",
    ),
    Transaction(
        "T-1060", "CUST-1003", "ACC-1003",
        datetime(2026, 10, 17, 9, 0, tzinfo=timezone.utc),
        850_000, "USD", "debit", "Northstar Auto", "vehicle",
        memo="Large transfer following recent loan disbursal",
    ),
    Transaction(
        "T-1072", "CUST-1001", "ACC-1001",
        datetime(2026, 10, 16, 18, 30, tzinfo=timezone.utc),
        4_995, "USD", "debit", "Green Market", "groceries",
        memo="Recurring payment to a known payee",
    ),
    Transaction(
        "T-1084", "CUST-1002", "ACC-1002",
        datetime(2026, 10, 15, 14, 20, tzinfo=timezone.utc),
        1_250_000, "USD", "debit", "Cedar Restaurant Supply", "inventory",
        memo="Large established supplier payment",
    ),
    Transaction(
        "T-1091", "CUST-1003", "ACC-1003",
        datetime(2026, 10, 17, 3, 12, tzinfo=timezone.utc),
        725, "USD", "debit", "Metro Transit", "transport",
        memo="Small payment at an unusual hour",
    ),
)


def _build_generated_transactions() -> tuple[Transaction, ...]:
    transactions = []
    recurring_payees = (
        ("Green Market", "groceries"),
        ("Metro Transit", "transport"),
        ("Harbor Utilities", "utilities"),
        ("Juniper Cafe", "dining"),
        ("Pinecone Payroll", "income"),
    )

    for customer_index, customer in enumerate(CUSTOMERS):
        for day in range(1, 29):
            if customer.customer_id == "CUST-1003" and day == 16:
                transactions.append(
                    Transaction(
                        "T-1059", customer.customer_id, customer.account_id,
                        datetime(2026, 10, 16, 15, 0, tzinfo=timezone.utc),
                        1_500_000, "USD", "credit", "Pinecone Lending",
                        "loan_disbursal", memo="Personal loan disbursal",
                    )
                )
                continue

            if customer.customer_id == "CUST-1002" and day in (26, 27, 28):
                velocity_times = {26: (10, 2), 27: (10, 7), 28: (10, 11)}
                hour, minute = velocity_times[day]
                timestamp = datetime(2026, 10, 17, hour, minute, tzinfo=timezone.utc)
                payee, category = "Harbor Foods", "inventory"
            else:
                timestamp = datetime(2026, 10, day, 12, 0, tzinfo=timezone.utc) + timedelta(
                    minutes=customer_index * 17 + day
                )
                payee, category = recurring_payees[(day + customer_index) % len(recurring_payees)]

            direction = "credit" if day in (1, 15) else "debit"
            if direction == "credit":
                payee, category = "Pinecone Payroll", "income"
            amount_cents = (
                210_000 + customer_index * 12_500
                if direction == "credit"
                else 1_200 + ((day * 791 + customer_index * 1_201) % 38_000)
            )
            transactions.append(
                Transaction(
                    f"TX-{customer_index + 1}-{day:03d}",
                    customer.customer_id,
                    customer.account_id,
                    timestamp,
                    amount_cents,
                    "USD",
                    direction,
                    payee,
                    category,
                )
            )

    return tuple(transactions)


TRANSACTIONS = tuple(sorted(
    _FEATURED_TRANSACTIONS + _build_generated_transactions(),
    key=lambda transaction: (transaction.timestamp, transaction.transaction_id),
    reverse=True,
))


def serialize_customers() -> list[dict]:
    serialized = []
    for customer in CUSTOMERS:
        customer_transactions = [
            transaction.to_dict()
            for transaction in TRANSACTIONS
            if transaction.customer_id == customer.customer_id
        ]
        serialized.append({
            "customer_id": customer.customer_id,
            "full_name": customer.full_name,
            "segment": customer.segment,
            "profile": {"age": customer.age, "occupation": customer.occupation},
            "account_id": customer.account_id,
            "transaction_history": customer_transactions,
        })
    return serialized
