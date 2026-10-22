import re


_INTENT_EXAMPLES = {
    "investigate_txn": (
        "investigate transaction",
        "look into transaction",
        "review transfer",
        "investigate txn",
        "what happened with transaction",
    ),
    "account_summary": (
        "account summary",
        "show balance",
        "summarize account",
        "account details",
        "how much money in account",
    ),
    "list_suspicious": (
        "list suspicious transactions",
        "show transactions that need review",
        "find unusual activity",
        "show flagged transactions",
        "suspicious payments",
    ),
    "explain_flag": (
        "explain flag",
        "why was transaction flagged",
        "explain risk score",
        "why is this transaction suspicious",
        "explain alert",
    ),
}

_INTENT_PATTERNS = (
    ("explain_flag", re.compile(r"\b(explain|why|reason|flagged|flag|alert|risk score)\b", re.I)),
    ("list_suspicious", re.compile(r"\b(list|show|find|any|all)\b.*\b(suspicious|flagged|unusual|review|alerts?)\b", re.I)),
    ("account_summary", re.compile(r"\b(account|balance|account summary|account details)\b", re.I)),
    ("investigate_txn", re.compile(r"\b(investigate|investigation|look into|review|details|what happened)\b", re.I)),
)

_TRANSACTION_ID = re.compile(r"\b(?:T-\d+|TX-\d+-\d{3})\b", re.I)
_CUSTOMER_ID = re.compile(r"\bCUST-\d+\b", re.I)
_ACCOUNT_ID = re.compile(r"\bACC-\d+\b", re.I)
_EXAMPLES = tuple(
    (example, intent)
    for intent, examples in _INTENT_EXAMPLES.items()
    for example in examples
)


class LocalInterpreter:
    def interpret(self, text: str) -> dict:
        normalized = re.sub(r"\s+", " ", text.strip().lower())
        intent = "unknown"
        confidence = 0.0

        for example, example_intent in _EXAMPLES:
            if example in normalized:
                intent, confidence = example_intent, 1.0
                break

        if intent == "unknown":
            for candidate, pattern in _INTENT_PATTERNS:
                if pattern.search(normalized):
                    intent, confidence = candidate, 0.8
                    break

        transaction_match = _TRANSACTION_ID.search(text)
        customer_match = _CUSTOMER_ID.search(text)
        account_match = _ACCOUNT_ID.search(text)
        entities = {
            "transaction_id": transaction_match.group(0).upper() if transaction_match else None,
            "customer_id": customer_match.group(0).upper() if customer_match else None,
            "account_id": account_match.group(0).upper() if account_match else None,
        }
        missing_fields = []
        if intent in ("investigate_txn", "explain_flag") and not entities["transaction_id"]:
            missing_fields.append("transaction_id")
        elif intent == "account_summary" and not entities["customer_id"] and not entities["account_id"]:
            missing_fields.append("customer_id")

        return {
            "intent": intent,
            "entities": entities,
            "confidence": confidence,
            "missing_fields": missing_fields,
            "interpreter": "local",
        }
