from datetime import datetime, timedelta


class CreditAgent:
    RECENT_DISBURSAL_WINDOW = timedelta(days=30)
    LARGE_TRANSFER_THRESHOLD_CENTS = 100_000

    def assess(self, transaction: dict, loan_information: dict) -> list[dict]:
        evidence = []
        loans = loan_information["loans"]
        if loans:
            evidence.append({
                "type": "loan_exposure",
                "title": "Existing loan exposure",
                "details": {
                    "loan_count": len(loans),
                    "loans": loans,
                    "total_principal_balance_cents": sum(
                        loan["principal_balance_cents"] for loan in loans
                    ),
                },
                "source": "Loan fixtures",
            })

        transaction_time = datetime.fromisoformat(transaction["timestamp"].replace("Z", "+00:00"))
        related_disbursals = []
        if transaction["direction"] == "debit" and transaction["amount_cents"] >= self.LARGE_TRANSFER_THRESHOLD_CENTS:
            for disbursal in loan_information["disbursals"]:
                disbursal_time = datetime.fromisoformat(
                    disbursal["timestamp"].replace("Z", "+00:00")
                )
                elapsed = transaction_time - disbursal_time
                if timedelta(0) <= elapsed <= self.RECENT_DISBURSAL_WINDOW:
                    related_disbursals.append({
                        "transaction_id": disbursal["transaction_id"],
                        "timestamp": disbursal["timestamp"],
                        "amount_cents": disbursal["amount_cents"],
                        "payee": disbursal["payee"],
                        "hours_before_transfer": round(elapsed.total_seconds() / 3600, 2),
                    })

        if related_disbursals:
            evidence.append({
                "type": "recent_loan_disbursal",
                "title": "Large transfer after recent loan disbursal",
                "details": {
                    "transfer_transaction_id": transaction["transaction_id"],
                    "disbursals": related_disbursals,
                },
                "source": "Loan disbursal transaction history",
            })
        return evidence
