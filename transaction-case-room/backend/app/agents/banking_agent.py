from ..data.fixtures import TRANSACTIONS, Transaction
from ..tools.banking_tools import BankingTools
from ..tools.execution import execute_tool


class BankingAgent:
    def __init__(self, tools: BankingTools | None = None) -> None:
        self.tools = tools or BankingTools()

    def collect_customer_history(self, customer_id: str, trace: list[dict]) -> dict:
        agent = type(self).__name__
        latest = max(
            item.timestamp for item in TRANSACTIONS if item.customer_id == customer_id
        )
        history = execute_tool(
            trace, agent, "get_transaction_history",
            {"customer_id": customer_id},
            lambda: self.tools.get_transaction_history(customer_id),
        )
        customer = execute_tool(
            trace, agent, "get_customer_profile",
            {"customer_id": customer_id},
            lambda: self.tools.get_customer_profile(customer_id),
        )
        known_payees = execute_tool(
            trace, agent, "get_known_payees",
            {"customer_id": customer_id, "before": "latest"},
            lambda: self.tools.get_known_payees(
                customer_id,
                latest.replace(year=latest.year + 1),
            ),
        )
        return {
            "customer": customer,
            "transaction_history": history,
            "known_payees": known_payees,
        }

    def collect_evidence(
        self,
        transaction: Transaction | None,
        trace: list[dict],
        customer_id: str | None = None,
    ) -> dict:
        agent = type(self).__name__
        if transaction is not None:
            details = execute_tool(
                trace, agent, "get_transaction_details",
                {"transaction_id": transaction.transaction_id},
                lambda: self.tools.get_transaction_details(transaction.transaction_id),
            )
            customer_id = transaction.customer_id
        else:
            details = None
        if customer_id is None:
            raise ValueError("A customer ID or transaction is required")
        customer = execute_tool(
            trace, agent, "get_customer_profile",
            {"customer_id": customer_id},
            lambda: self.tools.get_customer_profile(customer_id),
        )
        history = execute_tool(
            trace, agent, "get_transaction_history",
            {"customer_id": customer_id},
            lambda: self.tools.get_transaction_history(customer_id),
        )
        if transaction is not None:
            known_payees = execute_tool(
                trace, agent, "get_known_payees",
                {"customer_id": customer_id, "before": transaction.timestamp.isoformat()},
                lambda: self.tools.get_known_payees(customer_id, transaction.timestamp),
            )
        else:
            from ..data.fixtures import TRANSACTIONS

            latest = max(
                item.timestamp for item in TRANSACTIONS if item.customer_id == customer_id
            )
            known_payees = execute_tool(
                trace, agent, "get_known_payees",
                {"customer_id": customer_id, "before": "latest"},
                lambda: self.tools.get_known_payees(customer_id, latest.replace(year=latest.year + 1)),
            )
        account = execute_tool(
            trace, agent, "get_account_summary",
            {"customer_id": customer_id},
            lambda: self.tools.get_account_summary(customer_id),
        )
        loan_information = execute_tool(
            trace, agent, "get_loan_information",
            {"customer_id": customer_id},
            lambda: self.tools.get_loan_information(customer_id),
        )

        evidence = [
            {
                "type": "customer_profile",
                "title": "Customer profile",
                "details": customer,
                "source": "Customer fixture",
            },
            {
                "type": "transaction_history",
                "title": "Customer transaction history",
                "details": {"transaction_count": len(history), "transactions": history},
                "source": "Transaction fixtures",
            },
            {
                "type": "known_payees",
                "title": "Known payees",
                "details": {"payees": known_payees},
                "source": "Registered payees and prior transaction history",
            },
            {
                "type": "account_summary",
                "title": "Account summary",
                "details": account,
                "source": "Account fixture and transaction history",
            },
            {
                "type": "loan_information",
                "title": "Loan information",
                "details": loan_information,
                "source": "Loan and transaction fixtures",
            },
        ]
        return {
            "transaction": details,
            "customer": customer,
            "transaction_history": history,
            "known_payees": known_payees,
            "account": account,
            "loan_information": loan_information,
            "evidence": evidence,
        }
