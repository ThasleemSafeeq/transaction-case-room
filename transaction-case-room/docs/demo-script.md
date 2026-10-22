# Demo script (5–7 minutes)

## Before the walkthrough

- Start the Flask API and Vite frontend in separate terminals using the root README instructions.
- Open the local dashboard and confirm the backend status reads **Connected**.
- Keep Gemini disabled for a deterministic offline walkthrough.
- State up front: **“This is fictional simulated data. Review flags are rule-based prompts for a person to investigate; none means confirmed fraud.”**

## 0:00–0:45 — Introduce the room

Show the `Transaction Case Room` title, **SIMULATED DATA** label, backend connection, and the summary cards. Explain that transaction and review counts come from API responses. The investigated-cases count is scoped to the current browser session.

## 0:45–1:30 — Search and filter

Search for `CUST-1002`, then use the customer filter and review-status filter. Point out that filtering narrows the API-loaded transactions and that review status comes from the suspicious-list rules result. Clear the filters to restore the list.

## 1:30–2:30 — Normal payment

Select transaction `T-1072` (Green Market). Wait for the investigation panel to load from `/api/investigate`. Show the customer, payee, timestamp, amount, evidence, and the rule-derived score. Explain that a known-payee routine payment can have no triggered rules, based on the provided fixture history—not on a fraud classifier.

## 2:30–3:45 — Flagged transaction

Select `T-1042` (Summit Devices). Review the score and the triggered amount, new-payee, and unusual-hour rules. Show the `Review required` recommendation and the execution timeline. Point out the explicit “not a fraud determination” note. Expand the actual agent/tool steps and show their statuses and durations.

## 3:45–4:30 — Explain a flag

Use the query suggestion **“Explain why T-1042 was flagged”**. Run it and inspect the `local` interpreter indicator, answer, risk explanation, and trace. Contrast this path with the direct investigation panel: the query supervisor chooses the RiskAgent route for an explanation request.

## 4:30–5:15 — Suspicious activity list

Run **“List suspicious transactions”**. Show the actual transactions returned by the backend weighted rules and their scores. Explain that the API calls BankingAgent and RiskAgent for this operation, and uses no CreditAgent for the list route.

## 5:15–5:50 — Account summary

Run **“Summarize account CUST-1001”**. Show the account evidence and explain that account-summary intent routes to BankingAgent only; it does not calculate or display a risk score.

## 5:50–6:20 — Unknown request

Enter an unrelated request such as “Tell me a joke”. Show the backend clarification response and `local` interpreter. Note that an unknown intent does not call any agents.

## 6:20–6:45 — Close with boundaries

Reiterate that fixtures are fictional, risk weights are simple MVP heuristics, and human review is required. Gemini is optional, disabled unless configured in backend `.env`, limited to intent/ID routing, and not needed for the demo.

No video recording or hosted deployment is part of this walkthrough.
