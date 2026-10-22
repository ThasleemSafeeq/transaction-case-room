# Transaction Case Room

Transaction Case Room is a local-first internship MVP for reviewing fictional banking activity. A reviewer can inspect transactions, ask the case room to investigate or summarize an account, and see the fixture-backed evidence and deterministic rules used in the response.

> **SIMULATED DATA:** All people, accounts, loans, and transactions in this project are fictional. A risk rule or “Review required” recommendation is an investigation prompt, not a fraud determination.

## Features

- Responsive React + Vite dashboard with backend status, transaction search, customer and review filters, and API-backed summary cards.
- Flask JSON API for health, customers, transactions, individual transactions, investigations, and natural-language queries.
- BankingAgent retrieves fixture-backed profiles, account and loan details, payees, and history.
- RiskAgent calculates a deterministic weighted score from amount, payee, time, and velocity rules.
- CreditAgent provides loan exposure and recent-disbursal evidence when available.
- Python `ThreadPoolExecutor` supervisor routes only to relevant agents.
- Offline local intent interpreter is the default. Gemini routing is optional, disabled by default, and validated before it reaches the supervisor.
- Tool and agent execution traces contain inputs, outputs, status, and elapsed time. Provider credentials are not included in responses or traces.

Supported intents are `investigate_txn`, `account_summary`, `list_suspicious`, `explain_flag`, and `unknown`. Customer fixture IDs use the `CUST-1001` format (not `C-1001`).

## Architecture

```text
frontend/                       backend/
React dashboard                 Flask routes
       |                            |
       +--- /api/query ------------> local interpreter (default)
       |                              optional Gemini classifier
       |                            supervisor / ThreadPoolExecutor
       +--- /api/investigate -----> BankingAgent / RiskAgent / CreditAgent
                                      |
                                  fixture-backed tools and data
```

The interpreter classifies intent and extracts identifiers only. Financial facts and risk scores come from Python fixture tools and rules. See [docs/architecture.md](docs/architecture.md) for routing, validation, score weights, fallback behavior, and the trace schema.

## Prerequisites

- Windows 10/11 with Python 3.11 or later and `py` or `python` on `PATH`.
- Node.js 20 or later, including npm.
- Optional: a Gemini API key if you explicitly enable the hosted intent classifier. The core application and tests do not require it or an internet connection.

## Setup (Windows PowerShell)

From the project root:

```powershell
py -3 -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
Set-Location frontend
npm install
Set-Location ..
```

If the Python launcher is unavailable, replace `py -3` with `python`.

### Start the backend

In one PowerShell terminal, from the project root:

```powershell
Set-Location backend
.\.venv\Scripts\python.exe run.py
```

Flask listens on `http://127.0.0.1:5000`.

### Start the frontend

In a second PowerShell terminal:

```powershell
Set-Location frontend
npm run dev
```

Open the local Vite URL printed by npm (normally `http://localhost:5173`). Vite proxies `/api` requests to the local Flask server.

## API

All responses are JSON. The fixture set has three customers and 90 transactions. Some successful responses are abbreviated below.

### `GET /api/health`

```json
{"status": "ok"}
```

### `GET /api/customers`

Returns customer profiles, account IDs, and each customer's transaction history.

### `GET /api/transactions`

Returns the transaction fixture list. Each record includes a stable ID, customer/account IDs, UTC timestamp, amount, payee, category, direction, and status.

### `GET /api/transactions/<transaction_id>`

Returns one transaction or `404` with `{"error":"Transaction not found"}`.

### `POST /api/investigate`

Request:

```json
{"transaction_id": "T-1042"}
```

Success includes `transaction`, `customer`, `evidence_cards`, `risk_score`, `triggered_rules`, `recommendation`, and `execution_trace`. Unknown IDs return `404` before agents are run.

### `POST /api/query` (also `POST /api/chat`)

Request:

```json
{"message": "Explain why T-1042 was flagged"}
```

Abbreviated success response excerpt:

```json
{
  "answer": "Risk score for T-1042 is 75/100. Triggered rules explain the score.",
  "intent": "explain_flag",
  "interpreter": "local",
  "routing": {
    "intent": "explain_flag",
    "entities": {"transaction_id": "T-1042", "customer_id": null, "account_id": null},
    "confidence": 0.8,
    "missing_fields": [],
    "interpreter": "local",
    "fallback_reason": "gemini_disabled"
  },
  "data": {"transaction_id": "T-1042"},
  "evidence": [],
  "risk_explanation": {
    "score": 75,
    "triggered_rules": [
      {"name": "unusually_large_amount", "weight": 35, "reason": "Fixture-derived rule reason"},
      {"name": "new_payee", "weight": 25, "reason": "Fixture-derived rule reason"},
      {"name": "unusual_hour", "weight": 15, "reason": "Fixture-derived rule reason"}
    ]
  },
  "trace": [],
  "errors": []
}
```

The example illustrates the response shape; in a live response `triggered_rules` and `trace` contain the result of that request. Unsupported or unclear requests return a clarification answer without calling agents. Invalid IDs or ownership mismatches return an error and do not execute agents.

## Tests and build

From the project root:

```powershell
backend\.venv\Scripts\python.exe -m unittest discover -s backend\tests -v
backend\.venv\Scripts\python.exe -m compileall -q backend\app backend\tests backend\run.py
Set-Location frontend
npm run build
```

Tests use the deterministic fixtures and mocked Gemini HTTP calls; they do not need a live API key or network.

## Optional Gemini intent routing

Gemini is **disabled by default**. It is permitted to classify a user message and extract routing identifiers only; it does not receive banking tool results and cannot calculate risk, supply evidence, or make fraud decisions. The returned intent and ID formats are validated locally. Missing configuration, invalid output, request failures, quota errors, and timeouts fall back to the local pattern-based interpreter.

1. From the project root, create the private config file:

   ```powershell
   Copy-Item backend\.env.example backend\.env
   notepad backend\.env
   ```

2. Set `GEMINI_ENABLED=true` and put your own key in `GEMINI_API_KEY`. Keep the file private and do not commit or share it. The backend reads this file only; the key is never returned to the browser.
3. Optionally set `GEMINI_MODEL` to a model available to your account and `GEMINI_TIMEOUT_SECONDS` to a positive timeout.
4. Restart Flask. Set `GEMINI_ENABLED=false` to return to local routing.

The REST integration follows Google's [Gemini Interactions API](https://ai.google.dev/gemini-api/docs/interactions?lang=rest) and [structured output](https://ai.google.dev/gemini-api/docs/structured-output?lang=rest) documentation and requests stateless processing. Provider access, model availability, pricing, and quotas are subject to Google's current account terms; this project does not promise free access or a specific quota. Do not enter real financial, personal, or confidential data.

## Known limitations and future improvements

- Data is static, fictional, and held in Python memory; there is no database, persistence, authentication, or production banking connection.
- Rule thresholds are sample MVP heuristics, not a regulated or validated fraud model. Review decisions remain with a human.
- The local intent interpreter uses deterministic phrase patterns and supports the fixture ID formats; it is not a general-purpose language model.
- Gemini fallback reason is exposed as a non-sensitive routing field, but no live-provider availability is guaranteed.
- Investigation counters live only in the open browser session.
- Future work could add documented scenario fixtures, stronger input schemas, persistent case management, accessibility/usability evaluation, and operational monitoring.

No deployment or demo video is included with this project.
