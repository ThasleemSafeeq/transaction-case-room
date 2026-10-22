from flask import Blueprint, jsonify, request

from .agents import BankingAgent, CreditAgent, RiskAgent
from .data.fixtures import TRANSACTIONS, serialize_customers
from .interpreter import OptionalGeminiInterpreter
from .supervisor import Supervisor, SupervisorInputError
from .tools.execution import ToolExecutionError


api = Blueprint("api", __name__, url_prefix="/api")


@api.get("/health")
def health():
    return jsonify({"status": "ok"})


@api.get("/customers")
def customers():
    return jsonify(serialize_customers())


@api.get("/transactions")
def transactions():
    return jsonify([transaction.to_dict() for transaction in TRANSACTIONS])


@api.get("/transactions/<transaction_id>")
def transaction_detail(transaction_id: str):
    transaction = next(
        (item for item in TRANSACTIONS if item.transaction_id == transaction_id),
        None,
    )
    if transaction is None:
        return jsonify({"error": "Transaction not found"}), 404
    return jsonify(transaction.to_dict())


@api.post("/investigate")
def investigate():
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or not isinstance(body.get("transaction_id"), str):
        return jsonify({"error": "A transaction_id string is required"}), 400

    transaction_id = body["transaction_id"]
    transaction = next(
        (item for item in TRANSACTIONS if item.transaction_id == transaction_id),
        None,
    )
    if transaction is None:
        return jsonify({"error": "Transaction not found"}), 404

    trace: list[dict] = []
    try:
        banking_evidence = BankingAgent().collect_evidence(transaction, trace)
        risk_result = RiskAgent().calculate(
            transaction,
            banking_evidence["transaction_history"],
            banking_evidence["known_payees"],
        )
        credit_evidence = CreditAgent().assess(
            banking_evidence["transaction"],
            banking_evidence["loan_information"],
        )
        evidence_cards = banking_evidence["evidence"] + credit_evidence
        review_required = risk_result["score"] >= 25 or any(
            card["type"] == "recent_loan_disbursal" for card in credit_evidence
        )
        return jsonify({
            "transaction": banking_evidence["transaction"],
            "customer": banking_evidence["customer"],
            "evidence_cards": evidence_cards,
            "risk_score": risk_result["score"],
            "triggered_rules": risk_result["triggered_rules"],
            "recommendation": "Review required" if review_required else "Routine monitoring",
            "execution_trace": trace,
        })
    except ToolExecutionError as error:
        return jsonify({
            "error": "Investigation failed",
            "details": error.detail,
            "error_type": error.original_error_type,
            "execution_trace": trace,
        }), 500


@api.post("/query")
@api.post("/chat")
def query():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({"error": "A JSON object with a message is required"}), 400
    message = body.get("message", body.get("query"))
    if not isinstance(message, str) or not message.strip():
        return jsonify({"error": "A non-empty message string is required"}), 400

    routing = OptionalGeminiInterpreter().interpret(message)
    try:
        result = Supervisor().execute(routing)
    except SupervisorInputError as error:
        return jsonify({
            "error": str(error),
            "error_type": type(error).__name__,
            "intent": routing["intent"],
            "interpreter": routing["interpreter"],
            "routing": routing,
            "trace": [
                {
                    "type": "routing",
                    "intent": routing["intent"],
                    "agents": [],
                    "reason": "Input validation failed before any agent execution.",
                    "duration_ms": 0.0,
                    "status": "skipped",
                },
                {
                    "type": "validation",
                    "status": "failed",
                    "error": str(error),
                    "duration_ms": 0.0,
                },
            ],
        }), error.status_code
    return jsonify(result)
