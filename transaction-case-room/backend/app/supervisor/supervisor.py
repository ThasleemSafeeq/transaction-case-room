from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from time import perf_counter

from ..agents import BankingAgent, CreditAgent, RiskAgent
from ..data.fixtures import ACCOUNTS, CUSTOMERS, REGISTERED_PAYEES, TRANSACTIONS


class SupervisorInputError(ValueError):
    def __init__(self, message: str, status_code: int = 400) -> None:
        self.status_code = status_code
        super().__init__(message)


class Supervisor:
    def __init__(
        self,
        banking_agent: BankingAgent | None = None,
        risk_agent: RiskAgent | None = None,
        credit_agent: CreditAgent | None = None,
        max_workers: int = 8,
    ) -> None:
        self._agents = {
            "BankingAgent": banking_agent,
            "RiskAgent": risk_agent,
            "CreditAgent": credit_agent,
        }
        self.max_workers = max_workers
        self._trace_lock = Lock()

    def _agent(self, name: str):
        with self._trace_lock:
            if self._agents[name] is None:
                factory = {
                    "BankingAgent": BankingAgent,
                    "RiskAgent": RiskAgent,
                    "CreditAgent": CreditAgent,
                }[name]
                self._agents[name] = factory()
            return self._agents[name]

    def _record(self, trace: list[dict], entry: dict) -> None:
        with self._trace_lock:
            trace.append(entry)

    def _run_agent(self, trace: list[dict], name: str, operation, inputs: dict | None = None):
        started = perf_counter()
        entry = {
            "type": "agent",
            "agent": name,
            "input": inputs or {},
            "output": None,
            "duration_ms": 0.0,
            "status": "running",
        }
        self._record(trace, entry)
        try:
            output = operation()
        except Exception as error:
            entry.update({
                "output": {"error": str(error), "error_type": type(error).__name__},
                "duration_ms": round((perf_counter() - started) * 1000, 3),
                "status": "failed",
            })
            raise
        entry.update({
            "output": output,
            "duration_ms": round((perf_counter() - started) * 1000, 3),
            "status": "success",
        })
        return output

    def _customer_for(self, customer_id: str | None, account_id: str | None = None):
        if account_id:
            account = next((item for item in ACCOUNTS if item.account_id == account_id), None)
            if account is None:
                raise SupervisorInputError(f"Unknown account ID: {account_id}", 404)
            if customer_id and account.customer_id != customer_id:
                raise SupervisorInputError(
                    f"Account {account_id} does not belong to customer {customer_id}"
                )
            customer_id = account.customer_id
        customer = next((item for item in CUSTOMERS if item.customer_id == customer_id), None)
        if customer is None:
            raise SupervisorInputError(f"Unknown customer ID: {customer_id}", 404)
        return customer

    def _transaction_for(self, transaction_id: str | None, customer_id: str | None = None):
        if not transaction_id:
            raise SupervisorInputError("A transaction ID is required")
        transaction = next(
            (item for item in TRANSACTIONS if item.transaction_id == transaction_id),
            None,
        )
        if transaction is None:
            raise SupervisorInputError(f"Unknown transaction ID: {transaction_id}", 404)
        if customer_id and transaction.customer_id != customer_id:
            raise SupervisorInputError(
                f"Transaction {transaction_id} does not belong to customer {customer_id}"
            )
        return transaction

    def _route(self, trace: list[dict], intent: str, agents: list[str], reason: str) -> None:
        self._record(trace, {
            "type": "routing",
            "intent": intent,
            "agents": agents,
            "reason": reason,
            "duration_ms": 0.0,
            "status": "success",
        })

    def execute(self, routing: dict) -> dict:
        trace: list[dict] = []
        intent = routing["intent"]
        entities = routing["entities"]
        answer = ""
        evidence = []
        risk_explanation = None
        data = {}
        errors = []

        if intent == "unknown" or routing["missing_fields"]:
            self._route(trace, intent, [], "Intent or required identifiers need clarification.")
            if intent == "unknown":
                answer = "What would you like to review? You can ask to investigate a transaction, summarize an account, list suspicious activity, or explain a flag."
            else:
                answer = f"Please provide the required identifier: {', '.join(routing['missing_fields'])}."
            return self._result(routing, answer, evidence, risk_explanation, trace, data, errors)

        customer_id = entities.get("customer_id")
        transaction_id = entities.get("transaction_id")
        if intent == "account_summary":
            customer = self._customer_for(customer_id, entities.get("account_id"))
            customer_id = customer.customer_id
        elif intent in ("investigate_txn", "explain_flag"):
            transaction = self._transaction_for(transaction_id, customer_id)
            customer_id = transaction.customer_id
        elif intent == "list_suspicious" and customer_id:
            self._customer_for(customer_id)

        try:
            if intent == "account_summary":
                self._route(trace, intent, ["BankingAgent"], "Account summary requires fixture-backed banking data.")
                banking_result = self._run_agent(
                    trace,
                    "BankingAgent",
                    lambda: self._agent("BankingAgent").collect_evidence(
                        transaction=None,
                        trace=trace,
                        customer_id=customer_id,
                    ),
                    {"customer_id": customer_id},
                )
                evidence = banking_result["evidence"]
                data = {"customer": banking_result["customer"], "account": banking_result["account"]}
                answer = f"Account summary for {banking_result['customer']['full_name']}."

            elif intent == "investigate_txn":
                transaction = self._transaction_for(transaction_id, customer_id)
                self._route(
                    trace, intent, ["BankingAgent", "RiskAgent", "CreditAgent (conditional)"],
                    "Banking evidence and risk analysis run concurrently; credit analysis follows for large debits.",
                )

                def banking_work():
                    return self._agent("BankingAgent").collect_evidence(transaction, trace)

                def risk_work():
                    return self._agent("RiskAgent").assess(transaction, trace)

                with ThreadPoolExecutor(max_workers=2) as executor:
                    banking_future = executor.submit(
                        self._run_agent, trace, "BankingAgent", banking_work,
                        {"transaction_id": transaction_id},
                    )
                    risk_future = executor.submit(
                        self._run_agent, trace, "RiskAgent", risk_work,
                        {"transaction_id": transaction_id},
                    )
                    banking_result = banking_future.result()
                    risk_data = risk_future.result()

                credit_evidence = []
                if transaction.direction == "debit" and transaction.amount_cents >= CreditAgent.LARGE_TRANSFER_THRESHOLD_CENTS:
                    credit_evidence = self._run_agent(
                        trace, "CreditAgent",
                        lambda: self._agent("CreditAgent").assess(
                            banking_result["transaction"],
                            banking_result["loan_information"],
                        ),
                        {"transaction_id": transaction_id},
                    )
                evidence = banking_result["evidence"] + credit_evidence
                risk_explanation = risk_data
                data = {
                    "transaction": banking_result["transaction"],
                    "customer": banking_result["customer"],
                    "recommendation": "Review required" if risk_data["score"] >= 25 or any(
                        card["type"] == "recent_loan_disbursal" for card in credit_evidence
                    ) else "Routine monitoring",
                }
                answer = f"Investigation completed for {transaction_id}: {data['recommendation']}."

            elif intent == "explain_flag":
                transaction = self._transaction_for(transaction_id, customer_id)
                self._route(trace, intent, ["RiskAgent"], "No cached risk result is available; calculate from the local fixtures.")
                risk_explanation = self._run_agent(
                    trace, "RiskAgent",
                    lambda: self._agent("RiskAgent").assess(transaction, trace),
                    {"transaction_id": transaction_id},
                )
                answer = (
                    f"Risk score for {transaction_id} is {risk_explanation['score']}/100. "
                    + ("Triggered rules explain the score." if risk_explanation["triggered_rules"] else "No risk rules were triggered.")
                )
                data = {"transaction_id": transaction_id}

            elif intent == "list_suspicious":
                self._route(trace, intent, ["BankingAgent", "RiskAgent"], "Banking gathers customer history; Risk scores transactions in parallel.")
                customers = [self._customer_for(customer_id)] if customer_id else list(CUSTOMERS)
                banking_by_customer = {}
                for customer in customers:
                    banking_by_customer[customer.customer_id] = self._run_agent(
                        trace, "BankingAgent",
                        lambda customer=customer: self._agent("BankingAgent").collect_customer_history(
                            customer.customer_id, trace
                        ),
                        {"customer_id": customer.customer_id},
                    )

                candidates = [
                    transaction for transaction in TRANSACTIONS
                    if transaction.customer_id in banking_by_customer
                ]
                results = []

                def score_transaction(transaction):
                    source = banking_by_customer[transaction.customer_id]
                    known_payees = set(REGISTERED_PAYEES.get(transaction.customer_id, ()))
                    known_payees.update(
                        item["payee"]
                        for item in source["transaction_history"]
                        if item["timestamp"] < transaction.timestamp.isoformat().replace("+00:00", "Z")
                    )
                    return self._run_agent(
                        trace, "RiskAgent",
                        lambda: self._agent("RiskAgent").calculate(
                            transaction,
                            source["transaction_history"],
                            sorted(known_payees),
                        ),
                        {"transaction_id": transaction.transaction_id},
                    )

                with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                    futures = {
                        executor.submit(score_transaction, transaction): transaction
                        for transaction in candidates
                    }
                    for future in as_completed(futures):
                        transaction = futures[future]
                        score = future.result()
                        if score["score"] >= 25:
                            results.append({
                                "transaction": transaction.to_dict(),
                                "risk_score": score["score"],
                                "triggered_rules": score["triggered_rules"],
                            })
                results.sort(key=lambda item: (-item["risk_score"], item["transaction"]["transaction_id"]))
                evidence = [{
                    "type": "suspicious_transactions",
                    "title": "Transactions requiring review",
                    "details": {"transactions": results, "count": len(results)},
                    "source": "Local weighted risk rules",
                }]
                data = {"transactions": results, "count": len(results)}
                answer = f"Found {len(results)} transaction(s) meeting the review threshold."

            else:
                self._route(trace, intent, [], "Unsupported intent.")
                answer = "I could not determine the requested action. Please rephrase your request."

        except Exception as error:
            errors.append({"error": str(error), "error_type": type(error).__name__})
            answer = "The request could not be completed because an agent or tool failed."
            self._record(trace, {
                "type": "error",
                "error": str(error),
                "error_type": type(error).__name__,
                "duration_ms": 0.0,
                "status": "failed",
            })

        return self._result(routing, answer, evidence, risk_explanation, trace, data, errors)

    def _result(self, routing, answer, evidence, risk_explanation, trace, data, errors):
        return {
            "answer": answer,
            "intent": routing["intent"],
            "interpreter": routing["interpreter"],
            "routing": routing,
            "data": data,
            "evidence": evidence,
            "risk_explanation": risk_explanation,
            "trace": trace,
            "errors": errors,
        }
