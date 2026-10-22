# Interview preparation

## Design decisions

### Why keep the interpreter separate from the supervisor?

The interpreter converts natural language into a small routing contract: one allowed intent and optional explicit IDs. The supervisor validates those entities against fixture data and chooses agents. This separation keeps language parsing from having authority to retrieve or infer financial facts.

### Why is the local interpreter the default?

Pattern/example matching is deterministic, offline, easy to test, and has no credential or service dependency. Gemini is a configuration-gated enhancement; schema validation and local fallback preserve the core path if the provider is unavailable or produces invalid output.

### Why can Gemini not return financial answers?

The Gemini prompt requests only an intent and IDs, and the structured response schema accepts only those fields. No banking fixtures or agent outputs are sent. Locally validated routing is not treated as trusted identity data: the supervisor checks IDs and ownership before agent execution. Scores, account figures, and evidence remain Python fixture/tool outputs.

### Why use conditional supervisor routing?

Each intent needs different data. An account summary needs banking evidence, not a risk model. Explaining a flag needs the risk rules. Transaction investigations use banking context and risk in parallel, then use CreditAgent only when the transfer is sufficiently large. Conditional routing avoids unrelated calls and makes traces easier to explain.

### Why deterministic risk scoring?

For this internship MVP, explicit weighted rules make every score reproducible and explainable. Each returned rule includes its weight and reason. It is not a calibrated production fraud model and it does not establish fraud.

### How do traces support auditability?

Tool entries record agent, tool, input, output, elapsed milliseconds, and status. Supervisor entries show routing, agent execution, and errors. This makes it possible to inspect what was called and why without relying on an opaque generated explanation. Credentials are not traced.

### What is the testing strategy?

Python standard-library tests cover fixture integrity, agent behavior, weighted scores, every intent, routing selection, invalid IDs and ownership, no-agent guarantees, tool errors, and the six scenario fixtures. Gemini integration tests mock its HTTP call, so they neither need API credentials nor network access. Frontend validation uses the Vite production build; endpoints are also smoke-tested against Flask.

## Current limitations

- Data is fictional and static; no persistence, real bank connection, authentication, or case workflow exists.
- Risk weights and thresholds are educational heuristics. They are not validated against real labels, and must not be used to make consequential decisions.
- Local intent classification uses a finite phrase-pattern list rather than a general NLP model.
- Gemini availability, account eligibility, model availability, pricing, and quotas are provider-controlled. Keep it disabled if the outbound service is not acceptable.
- The UI's investigation counter is browser-session-only; no case records are persisted.

## Likely interview questions

**Q: What happens when someone asks about an unknown transaction?**
A: The supervisor validates the ID against fixtures before constructing agents. The API returns a clear error and no agent/tool execution entries.

**Q: What if the user asks an unclear question?**
A: The interpreter returns `unknown`; the supervisor returns a clarification prompt without calling agents.

**Q: Can the LLM change a risk score?**
A: No. Gemini only supplies a validated intent and explicit identifier strings. RiskAgent calculates the score locally from the transaction, customer history, and deterministic rule weights.

**Q: Why run BankingAgent and RiskAgent concurrently?**
A: They are independent reads/calculations for an investigation. They can execute in a `ThreadPoolExecutor`; CreditAgent waits until transaction details establish whether the large-debit condition applies.

**Q: Why use score weights rather than a trained classifier?**
A: Weights are transparent and auditable for this small simulated MVP. There is no representative labelled dataset for responsible model training.

**Q: How do you prevent an LLM hallucination from becoming a bank lookup?**
A: Output is schema/format-validated, and the supervisor checks the referenced fixture IDs and ownership before agent calls. The model has no access to the tools or evidence.

**Q: How do you test the external integration offline?**
A: Mock `urlopen` responses and failures, then assert valid routing normalization and fallback for malformed, unavailable, timed-out, or quota responses.

**Q: What would you change before real deployment?**
A: Replace fixtures with access-controlled, audited data services; use established identity/authorization controls, privacy and regulatory review, validated monitoring policies, persistent case records, operational observability, and a formally evaluated risk model. The current code is not production-ready.

**Q: Does “Review required” mean fraud?**
A: No. It means a deterministic heuristic crossed a sample review threshold. A human must inspect the evidence; the app does not confirm fraud.
