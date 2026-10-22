from datetime import datetime

from ..data.fixtures import Transaction
from ..tools.banking_tools import BankingTools
from ..tools.execution import execute_tool


class RiskAgent:
    LARGE_AMOUNT_THRESHOLD_CENTS = 100_000
    VELOCITY_WINDOW_SECONDS = 15 * 60
    VELOCITY_TRANSACTION_THRESHOLD = 4

    def __init__(self, tools: BankingTools | None = None) -> None:
        self.tools = tools or BankingTools()

    def assess(self, transaction: Transaction, trace: list[dict]) -> dict:
        agent = type(self).__name__
        history = execute_tool(
            trace, agent, "get_transaction_history",
            {"customer_id": transaction.customer_id},
            lambda: self.tools.get_transaction_history(transaction.customer_id),
        )
        known_payees = execute_tool(
            trace, agent, "get_known_payees",
            {
                "customer_id": transaction.customer_id,
                "before": transaction.timestamp.isoformat(),
            },
            lambda: self.tools.get_known_payees(
                transaction.customer_id,
                transaction.timestamp,
            ),
        )
        return self.calculate(transaction, history, known_payees)

    def calculate(
        self,
        transaction: Transaction,
        transaction_history: list[dict],
        known_payees: list[str],
    ) -> dict:
        triggered_rules = []

        if transaction.direction == "debit" and transaction.amount_cents >= self.LARGE_AMOUNT_THRESHOLD_CENTS:
            triggered_rules.append({
                "name": "unusually_large_amount",
                "weight": 35,
                "reason": (
                    f"Debit amount ${transaction.amount_cents / 100:,.2f} meets or exceeds "
                    f"the ${self.LARGE_AMOUNT_THRESHOLD_CENTS / 100:,.2f} review threshold."
                ),
            })

        if transaction.payee not in known_payees:
            triggered_rules.append({
                "name": "new_payee",
                "weight": 25,
                "reason": f"{transaction.payee} does not appear in this customer's known payees.",
            })

        if transaction.timestamp.hour < 5:
            triggered_rules.append({
                "name": "unusual_hour",
                "weight": 15,
                "reason": f"Transaction occurred at {transaction.timestamp:%H:%M} UTC, between 00:00 and 04:59 UTC.",
            })

        transaction_time = transaction.timestamp.timestamp()
        transactions_in_window = [
            item for item in transaction_history
            if item["customer_id"] == transaction.customer_id
            and abs(
                datetime.fromisoformat(item["timestamp"].replace("Z", "+00:00")).timestamp()
                - transaction_time
            ) <= self.VELOCITY_WINDOW_SECONDS
        ]
        if len(transactions_in_window) >= self.VELOCITY_TRANSACTION_THRESHOLD:
            triggered_rules.append({
                "name": "transaction_velocity",
                "weight": 25,
                "reason": (
                    f"{len(transactions_in_window)} customer transactions occurred within "
                    "15 minutes of this transaction."
                ),
            })

        score = min(100, sum(rule["weight"] for rule in triggered_rules))
        return {"score": score, "triggered_rules": triggered_rules}
