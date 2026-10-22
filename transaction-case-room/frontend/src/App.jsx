import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "./api.js";

const money = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });
const dateFormatter = new Intl.DateTimeFormat("en-US", {
  dateStyle: "medium",
  timeStyle: "short",
  timeZone: "UTC",
});
const routes = [
  { path: "/overview", label: "Overview", icon: "▦" },
  { path: "/investigations", label: "Investigations", icon: "⌕" },
  { path: "/transactions", label: "Transactions", icon: "⇄" },
  { path: "/customers", label: "Customers", icon: "♙" },
  { path: "/activity", label: "Activity", icon: "◷" },
];
const suggestions = [
  "Investigate T-1042",
  "Summarize account CUST-1001",
  "List suspicious transactions",
  "Explain why T-1042 was flagged",
];

function routeFromPath(pathname) {
  return routes.some((route) => route.path === pathname) ? pathname : "/overview";
}

function formatMoney(value) {
  return money.format(Number(value || 0));
}

function formatTimestamp(value) {
  if (!value) return "—";
  return `${dateFormatter.format(new Date(value))} UTC`;
}

function severity(score) {
  if (score >= 60) return "high";
  if (score >= 25) return "review";
  return "low";
}

function prettyRule(value = "") {
  return value.replaceAll("_", " ");
}

function StatusBadge({ review, children }) {
  return (
    <span className={`status-badge ${review ? "review" : "routine"}`}>
      <i />{children || (review ? "Review required" : "Below review threshold")}
    </span>
  );
}

function TraceList({ entries = [] }) {
  if (!entries.length) {
    return <p className="empty-copy">No execution steps were returned for this request.</p>;
  }
  return (
    <ol className="trace-list">
      {entries.map((entry, index) => (
        <li className="trace-item" key={`${entry.agent || entry.type}-${entry.tool || index}-${index}`}>
          <span className={`trace-dot ${entry.status || "success"}`} />
          <div className="trace-main">
            <div className="trace-heading">
              <strong>{entry.agent || entry.type || "Execution"}</strong>
              <span className={`trace-state ${entry.status || "success"}`}>{entry.status || "complete"}</span>
            </div>
            {entry.tool && <span className="trace-tool">{entry.tool}</span>}
            {entry.reason && <span className="trace-tool">{entry.reason}</span>}
            {entry.error && <span className="trace-error">{entry.error}</span>}
            {entry.output?.error && <span className="trace-error">{entry.output.error}</span>}
            {entry.output !== undefined && entry.output !== null && !entry.output?.error && (
              <details className="trace-output">
                <summary>View output</summary>
                <pre>{JSON.stringify(entry.output, null, 2)}</pre>
              </details>
            )}
          </div>
          {typeof entry.duration_ms === "number" && (
            <span className="trace-duration">{entry.duration_ms.toFixed(1)} ms</span>
          )}
        </li>
      ))}
    </ol>
  );
}

function EvidenceCard({ card }) {
  const details = card.details || {};
  return (
    <article className="evidence-card">
      <div className="evidence-card-title">
        <span className="evidence-mark" aria-hidden="true">+</span>
        <div><h4>{card.title || prettyRule(card.type)}</h4><p>{card.source}</p></div>
      </div>
      {card.type === "customer_profile" && (
        <dl className="evidence-dl">
          <dt>Customer</dt><dd>{details.full_name}</dd>
          <dt>Customer ID</dt><dd>{details.customer_id}</dd>
          <dt>Segment</dt><dd className="capitalize">{details.segment?.replaceAll("_", " ")}</dd>
          <dt>Occupation</dt><dd>{details.profile?.occupation || "—"}</dd>
        </dl>
      )}
      {card.type === "known_payees" && (
        <div className="payee-chips">
          {(details.payees || []).map((payee) => <span key={payee}>{payee}</span>)}
        </div>
      )}
      {card.type === "account_summary" && (
        <dl className="evidence-dl">
          <dt>Account</dt><dd>{details.account_id}</dd>
          <dt>Balance</dt><dd>{formatMoney(details.balance_cents / 100)}</dd>
          <dt>Transactions</dt><dd>{details.transaction_count}</dd>
          <dt>Status</dt><dd className="capitalize">{details.status}</dd>
        </dl>
      )}
      {card.type === "loan_information" && (
        <dl className="evidence-dl">
          <dt>Loans</dt><dd>{details.loans?.length || 0}</dd>
          <dt>Disbursals</dt><dd>{details.disbursals?.length || 0}</dd>
        </dl>
      )}
      {card.type === "loan_exposure" && (
        <>
          <dl className="evidence-dl">
            <dt>Loan count</dt><dd>{details.loan_count}</dd>
            <dt>Principal exposure</dt><dd>{formatMoney(details.total_principal_balance_cents / 100)}</dd>
          </dl>
          {(details.loans || []).map((loan) => (
            <p className="evidence-subline" key={loan.loan_id}>
              {loan.loan_type} · {loan.loan_id} · {formatMoney(loan.principal_balance_cents / 100)}
            </p>
          ))}
        </>
      )}
      {card.type === "recent_loan_disbursal" && (details.disbursals || []).map((item) => (
        <p className="evidence-subline" key={item.transaction_id}>
          {item.transaction_id} · {formatMoney(item.amount_cents / 100)} · {item.hours_before_transfer} hours before transfer
        </p>
      ))}
      {card.type === "transaction_history" && (
        <p className="evidence-description">{details.transaction_count} transactions in the customer history.</p>
      )}
      {card.type === "suspicious_transactions" && (
        <div className="evidence-results">
          {(details.transactions || []).map((item) => (
            <div key={item.transaction.transaction_id}>
              <span>{item.transaction.transaction_id} · {item.transaction.payee}</span>
              <strong>{item.risk_score}/100</strong>
            </div>
          ))}
          {!details.count && <p className="empty-copy">No transactions met the review threshold.</p>}
        </div>
      )}
    </article>
  );
}

function EvidenceGroups({ evidence = [] }) {
  if (!evidence.length) return <p className="empty-copy">No evidence cards were returned.</p>;
  const groups = [
    {
      title: "Customer profile",
      cards: evidence.filter((card) => card.type === "customer_profile"),
    },
    {
      title: "Transaction history",
      cards: evidence.filter((card) => card.type === "transaction_history"),
    },
    {
      title: "Other evidence",
      cards: evidence.filter((card) => !["customer_profile", "transaction_history"].includes(card.type)),
    },
  ].filter((group) => group.cards.length);
  return (
    <div className="evidence-groups">
      {groups.map((group, index) => (
        <details className="evidence-group" key={group.title} open={index === 0}>
          <summary>{group.title}<span>{group.cards.length}</span></summary>
          <div className="evidence-card-grid">
            {group.cards.map((card, cardIndex) => (
              <EvidenceCard card={card} key={`${card.type}-${cardIndex}`} />
            ))}
          </div>
        </details>
      ))}
    </div>
  );
}

function RiskIndicators({ risk }) {
  if (!risk) return null;
  return (
    <section className="content-panel risk-panel">
      <div className="panel-heading">
        <div><span className="eyebrow">RULE-BASED ASSESSMENT</span><h3>Risk indicators</h3></div>
        <span className="score-summary"><span className={`severity-chip ${severity(risk.score)}`}>{severity(risk.score)}</span>
          <span className={`score-number ${severity(risk.score)}`}>{risk.score}<small>/100</small></span></span>
      </div>
      <div className="score-track"><span className={severity(risk.score)} style={{ width: `${Math.max(0, Math.min(100, risk.score))}%` }} /></div>
      <div className="risk-disclaimer"><span>i</span> This risk indicator requires human review and is not a fraud determination.</div>
      {risk.triggered_rules?.length ? (
        <div className="indicator-grid">
          {risk.triggered_rules.map((rule) => (
            <article className={`indicator-card ${severity(risk.score)}`} key={rule.name}>
              <div><strong>{prettyRule(rule.name)}</strong><span>+{rule.weight}</span></div>
              <p>{rule.reason}</p>
            </article>
          ))}
        </div>
      ) : <p className="empty-copy">No weighted review rules were triggered.</p>}
    </section>
  );
}

function PageHeading({ eyebrow, title, description, action }) {
  return (
    <div className="page-heading">
      <div><span className="eyebrow">{eyebrow}</span><h1>{title}</h1>
        {description && <p>{description}</p>}</div>
      {action}
    </div>
  );
}

function TransactionTable({ transactions, customers, flaggedIds, onSelect, compact = false }) {
  if (!transactions.length) return <div className="empty-state"><strong>No matching transactions</strong><span>Try another search or adjust the filters.</span></div>;
  return (
    <div className="table-scroll">
      <table className={`data-table ${compact ? "compact-table" : ""}`}>
        <thead><tr><th>Transaction</th><th>Customer</th><th>Payee</th><th>Date (UTC)</th><th>Review status</th><th className="right">Amount</th><th /></tr></thead>
        <tbody>{transactions.map((transaction) => {
          const flagged = flaggedIds?.has(transaction.transaction_id);
          const customer = customers.find((item) => item.customer_id === transaction.customer_id);
          return (
            <tr key={transaction.transaction_id} tabIndex={0}
              aria-label={`Investigate ${transaction.transaction_id}, ${transaction.payee}`}
              onClick={() => onSelect(transaction)}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  onSelect(transaction);
                }
              }}>
              <td><strong className="txn-id">{transaction.transaction_id}</strong><span className={`txn-direction ${transaction.direction}`}>{transaction.direction}</span></td>
              <td><strong className="customer-name">{customer?.full_name || transaction.customer_id}</strong><span className="sub-cell">{transaction.customer_id}</span></td>
              <td className="payee-cell">{transaction.payee}</td>
              <td className="sub-cell">{formatTimestamp(transaction.timestamp)}</td>
              <td>{flaggedIds === null ? <span className="status-badge pending">Checking</span> :
                <StatusBadge review={flagged}>{flagged ? "Review required" : "Below threshold"}</StatusBadge>}</td>
              <td className="right amount-cell">{formatMoney(transaction.amount)}</td>
              <td className="row-arrow" aria-hidden="true">›</td>
            </tr>
          );
        })}</tbody>
      </table>
    </div>
  );
}

function InvestigationPanel({ transaction, result, loading, error, onClose }) {
  useEffect(() => {
    function onKeyDown(event) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  const txn = result?.transaction || transaction;
  return (
    <div className="drawer-backdrop" onMouseDown={(event) => {
      if (event.target === event.currentTarget) onClose();
    }}>
      <aside className="investigation-drawer" aria-label={`Investigation for ${transaction.transaction_id}`}>
        <header className="drawer-header">
          <div><span className="eyebrow">CASE INVESTIGATION</span><h2>{transaction.transaction_id}</h2></div>
          <button className="icon-button" type="button" onClick={onClose} aria-label="Close investigation">×</button>
        </header>
        {loading ? <div className="loading-state"><span className="spinner" />Loading investigation from the API…</div> :
          error ? <div className="request-error" role="alert"><strong>Investigation unavailable</strong><span>{error}</span></div> :
            result && (
              <div className="drawer-body">
                <div className="drawer-recommendation">
                  <StatusBadge review={result.recommendation === "Review required"}>{result.recommendation}</StatusBadge>
                  <span>Not a fraud determination</span>
                </div>
                <section className="content-panel">
                  <div className="panel-heading"><div><span className="eyebrow">TRANSACTION SUMMARY</span><h3>{txn.payee}</h3></div>
                    <strong className="drawer-amount">{formatMoney(txn.amount)}</strong></div>
                  <dl className="summary-details">
                    <dt>Customer</dt><dd>{result.customer?.full_name || txn.customer_id} · {txn.customer_id}</dd>
                    <dt>When</dt><dd>{formatTimestamp(txn.timestamp)}</dd>
                    <dt>Category</dt><dd className="capitalize">{txn.category?.replaceAll("_", " ")}</dd>
                    <dt>Direction</dt><dd className="capitalize">{txn.direction}</dd>
                  </dl>
                  {txn.memo && <p className="txn-memo">{txn.memo}</p>}
                </section>
                <RiskIndicators risk={{ score: result.risk_score, triggered_rules: result.triggered_rules }} />
                <section className="content-panel">
                  <div className="panel-heading"><div><span className="eyebrow">SOURCE-BACKED</span><h3>Evidence</h3></div>
                    <span className="panel-count">{result.evidence_cards?.length || 0} cards</span></div>
                  <EvidenceGroups evidence={result.evidence_cards || []} />
                </section>
                <details className="content-panel trace-accordion">
                  <summary><span><span className="eyebrow">AGENT AND TOOL ACTIVITY</span><strong>Execution trace</strong></span>
                    <span className="panel-count">{result.execution_trace?.length || 0} steps</span></summary>
                  <TraceList entries={result.execution_trace || []} />
                </details>
              </div>
            )}
      </aside>
    </div>
  );
}

function QueryResponse({ result, loading, error, onInvestigate }) {
  if (loading) return <div className="loading-state query-loading" role="status"><span className="spinner" />Interpreting request and gathering evidence…</div>;
  if (error) return <div className="request-error" role="alert"><strong>Request could not be completed</strong><span>{error}</span></div>;
  if (!result) return null;

  const transaction = result.data?.transaction;
  const risk = result.risk_explanation;
  return (
    <section className="query-response">
      <div className="response-meta"><span className="eyebrow">{prettyRule(result.intent)} · {result.interpreter || "interpreter unavailable"}</span>
        {transaction && <button className="text-button" type="button" onClick={() => onInvestigate(transaction)}>Open investigation →</button>}</div>
      <p className="response-answer">{result.answer}</p>
      {(result.errors || []).map((item, index) => <p className="inline-error" key={`${item.error_type}-${index}`}>{item.error}</p>)}
      {transaction && (
        <div className="result-summary">
          <div><span>Transaction</span><strong>{transaction.transaction_id} · {transaction.payee}</strong></div>
          <div><span>Amount</span><strong>{formatMoney(transaction.amount)}</strong></div>
          <div><span>Risk score</span><strong className={`score-inline ${severity(risk?.score || 0)}`}>{risk?.score ?? "—"}{risk && "/100"}</strong></div>
          <div><span>Severity</span><strong className={`severity-text ${severity(risk?.score || 0)}`}>{risk ? severity(risk.score) : "—"}</strong></div>
          <div><span>Recommendation</span><StatusBadge review={result.data.recommendation === "Review required"}>{result.data.recommendation}</StatusBadge></div>
        </div>
      )}
      {risk && <RiskIndicators risk={risk} />}
      {result.data?.customer && (
        <div className="query-customer-summary"><strong>{result.data.customer.full_name}</strong>
          <span>{result.data.account
            ? `${result.data.account.account_id} · Balance ${formatMoney(result.data.account.balance_cents / 100)}`
            : result.data.customer.customer_id}</span></div>
      )}
      {result.evidence?.length > 0 && <EvidenceGroups evidence={result.evidence} />}
      {result.trace?.length > 0 && (
        <details className="content-panel trace-accordion">
          <summary><span><span className="eyebrow">AGENT AND TOOL ACTIVITY</span><strong>Execution trace</strong></span>
            <span className="panel-count">{result.trace.length} steps</span></summary>
          <TraceList entries={result.trace} />
        </details>
      )}
    </section>
  );
}

function Overview({ transactions, flaggedTransactions, customers, casesCount, onNavigate, onSelect }) {
  const flaggedIds = new Set(flaggedTransactions.map((item) => item.transaction.transaction_id));
  const highRisk = flaggedTransactions.filter((item) => item.risk_score >= 60).length;
  const reviewCount = flaggedTransactions.length;
  const distribution = [
    { label: "High risk", value: highRisk, tone: "high" },
    { label: "Review", value: reviewCount - highRisk, tone: "review" },
  ];
  const totalFlagged = distribution.reduce((sum, item) => sum + item.value, 0);
  return (
    <>
      <PageHeading eyebrow="WORKSPACE OVERVIEW" title="Good day, reviewer"
        description="Monitor simulated customer activity and open a case when it needs a closer look."
        action={<button type="button" className="primary-button" onClick={() => onNavigate("/investigations")}>＋ Start investigation</button>} />
      <section className="kpi-grid" aria-label="Workspace metrics">
        <Kpi label="Total transactions" value={transactions.length} note="Fixture-backed activity" icon="⇄" />
        <Kpi label="Review required" value={flaggedTransactions.length} note={flaggedTransactions.length ? "Rule results from the API" : "No review results returned"} icon="!" tone="review" />
        <Kpi label="High risk" value={highRisk} note="Score 60 or above" icon="↗" tone="high" />
        <Kpi label="Investigations" value={casesCount} note="Completed this session" icon="⌕" />
      </section>
      <div className="overview-grid">
        <section className="content-panel distribution-panel">
          <div className="panel-heading"><div><span className="eyebrow">RULE-BASED REVIEW</span><h3>Risk distribution</h3></div>
            <button className="text-button" type="button" onClick={() => onNavigate("/transactions")}>View transactions →</button></div>
          {flaggedTransactions.length ? (
            <>
              <div className="distribution-bar" aria-label={`${totalFlagged} review results from the API`}>
                {distribution.map((item) => item.value > 0 && (
                  <span key={item.label} className={item.tone} style={{ width: `${item.value / totalFlagged * 100}%` }} />
                ))}
              </div>
              <div className="distribution-legend">{distribution.map((item) => (
                <div key={item.label}><i className={item.tone} /><span>{item.label}</span><strong>{item.value}</strong></div>
              ))}</div>
              <p className="panel-footnote">Based on current suspicious-list results. Review indicators do not confirm fraud.</p>
            </>
          ) : <div className="empty-state small-empty"><strong>Risk distribution unavailable</strong><span>Review results have not been returned by the API.</span></div>}
        </section>
        <section className="content-panel recent-panel">
          <div className="panel-heading"><div><span className="eyebrow">LATEST FIXTURE ACTIVITY</span><h3>Recent transactions</h3></div>
            <button className="text-button" type="button" onClick={() => onNavigate("/transactions")}>All transactions →</button></div>
          {[...transactions].sort((first, second) => Date.parse(second.timestamp) - Date.parse(first.timestamp)).slice(0, 5).map((transaction) => {
            const customer = customers.find((item) => item.customer_id === transaction.customer_id);
            return (
              <button className="recent-row" type="button" key={transaction.transaction_id} onClick={() => onSelect(transaction)}>
                <span className={`recent-mark ${flaggedIds.has(transaction.transaction_id) ? "review" : ""}`}>
                  {flaggedIds.has(transaction.transaction_id) ? "!" : transaction.direction === "credit" ? "↑" : "↓"}
                </span>
                <span className="recent-copy"><strong>{transaction.payee}</strong><small>{transaction.transaction_id} · {customer?.full_name || transaction.customer_id}</small></span>
                <span className="recent-amount">{formatMoney(transaction.amount)}</span>
              </button>
            );
          })}
          {!transactions.length && <p className="empty-copy">No transactions returned.</p>}
        </section>
      </div>
      <p className="global-disclaimer"><span>i</span> All people, accounts, and activity are fictional. A risk indicator is a review prompt, not a fraud determination.</p>
    </>
  );
}

function Kpi({ label, value, note, icon, tone = "" }) {
  return (
    <article className="kpi-card">
      <span className={`kpi-icon ${tone}`}>{icon}</span>
      <div className="kpi-data"><span>{label}</span><strong>{value}</strong><small>{note}</small></div>
    </article>
  );
}

function Investigations({ queryText, setQueryText, onSubmit, result, loading, error, onInvestigate }) {
  return (
    <>
      <PageHeading eyebrow="CASE WORKSPACE" title="Investigations"
        description="Ask a question in plain language. Intent routing and evidence are returned by the backend." />
      <section className="query-composer content-panel">
        <div className="composer-heading"><div className="composer-icon">✳</div><div><h2>Ask the case room</h2>
          <p>Try a transaction investigation, account summary, suspicious activity list, or flag explanation.</p></div></div>
        <form className="query-form" onSubmit={onSubmit}>
          <label className="sr-only" htmlFor="case-query">Your investigation request</label>
          <input id="case-query" value={queryText} onChange={(event) => setQueryText(event.target.value)}
            placeholder="For example: Investigate T-1042" disabled={loading} />
          <button className="primary-button" type="submit" disabled={loading || !queryText.trim()}>
            {loading ? <><span className="button-spinner" /> Working…</> : <>Submit request <span>→</span></>}
          </button>
        </form>
        <div className="prompt-list">{suggestions.map((item) => (
          <button type="button" key={item} onClick={() => setQueryText(item)} disabled={loading}>{item}</button>
        ))}</div>
      </section>
      {!result && !loading && !error && (
        <div className="empty-state investigation-empty"><span className="empty-symbol">⌕</span>
          <strong>Your investigation will appear here</strong><span>Submit a request above to get a live response from the backend.</span></div>
      )}
      <QueryResponse result={result} loading={loading} error={error} onInvestigate={onInvestigate} />
    </>
  );
}

function Transactions({ transactions, customers, flaggedIds, onSelect }) {
  const [search, setSearch] = useState("");
  const [customerId, setCustomerId] = useState("all");
  const [review, setReview] = useState("all");
  const [page, setPage] = useState(1);
  const pageSize = 15;
  const filtered = useMemo(() => {
    const query = search.trim().toLowerCase();
    return transactions.filter((transaction) => {
      const matchQuery = !query || [transaction.transaction_id, transaction.customer_id, transaction.payee]
        .some((value) => value?.toLowerCase().includes(query));
      const matchCustomer = customerId === "all" || transaction.customer_id === customerId;
      const isReview = flaggedIds?.has(transaction.transaction_id);
      const matchReview = review === "all" || (review === "review" && isReview) || (review === "below" && flaggedIds && !isReview);
      return matchQuery && matchCustomer && matchReview;
    });
  }, [transactions, search, customerId, review, flaggedIds]);
  useEffect(() => { setPage(1); }, [search, customerId, review]);
  const pageCount = Math.max(1, Math.ceil(filtered.length / pageSize));
  const pageRows = filtered.slice((page - 1) * pageSize, page * pageSize);
  return (
    <>
      <PageHeading eyebrow="CUSTOMER ACTIVITY" title="Transactions"
        description="Search and review fixture-backed transaction activity." />
      <section className="content-panel transaction-workspace">
        <div className="filter-row">
          <label className="search-box"><span aria-hidden="true">⌕</span><span className="sr-only">Search transaction records</span>
            <input type="search" placeholder="Search transaction ID, customer or payee" value={search} onChange={(event) => setSearch(event.target.value)} /></label>
          <label className="filter-control"><span>Customer</span><select value={customerId} onChange={(event) => setCustomerId(event.target.value)}>
            <option value="all">All customers</option>{customers.map((customer) => <option key={customer.customer_id} value={customer.customer_id}>{customer.full_name} · {customer.customer_id}</option>)}
          </select></label>
          <label className="filter-control"><span>Review status</span><select value={review} onChange={(event) => setReview(event.target.value)}>
            <option value="all">All activity</option><option value="review" disabled={flaggedIds === null}>Requires review</option><option value="below" disabled={flaggedIds === null}>Below threshold</option>
          </select></label>
        </div>
        {flaggedIds === null && <p className="inline-notice">Review classifications are unavailable; transaction search is still active.</p>}
        <div className="table-topline"><strong>{filtered.length} transactions</strong><span>Click a row to open its case details</span></div>
        <TransactionTable transactions={pageRows} customers={customers} flaggedIds={flaggedIds} onSelect={onSelect} />
        {filtered.length > pageSize && (
          <div className="pagination">
            <span>Page {page} of {pageCount}</span>
            <div><button type="button" onClick={() => setPage((value) => Math.max(1, value - 1))} disabled={page <= 1}>Previous</button>
              <button type="button" onClick={() => setPage((value) => Math.min(pageCount, value + 1))} disabled={page >= pageCount}>Next</button></div>
          </div>
        )}
      </section>
    </>
  );
}

function Customers({ customers, transactions, onSelectTransaction }) {
  const [search, setSearch] = useState("");
  const [selectedId, setSelectedId] = useState("");
  const filtered = useMemo(() => {
    const query = search.trim().toLowerCase();
    return customers.filter((customer) => !query || [
      customer.full_name, customer.customer_id, customer.account_id, customer.segment,
    ].some((value) => value?.toLowerCase().includes(query)));
  }, [customers, search]);
  useEffect(() => {
    if (selectedId && !filtered.some((customer) => customer.customer_id === selectedId)) setSelectedId("");
  }, [filtered, selectedId]);
  const selected = customers.find((customer) => customer.customer_id === selectedId);
  const history = selected
    ? transactions.filter((transaction) => transaction.customer_id === selected.customer_id)
    : [];
  return (
    <>
      <PageHeading eyebrow="CUSTOMER DIRECTORY" title="Customers" description="Customer profiles and transaction histories from the simulated-data API." />
      <div className="customers-layout">
        <section className="content-panel customer-directory">
          <label className="search-box"><span aria-hidden="true">⌕</span><span className="sr-only">Search customers</span>
            <input type="search" placeholder="Search name or customer ID" value={search} onChange={(event) => setSearch(event.target.value)} /></label>
          <div className="customer-list">
            {filtered.map((customer) => (
              <button type="button" className={`customer-list-item ${selectedId === customer.customer_id ? "active" : ""}`}
                onClick={() => setSelectedId(customer.customer_id)} key={customer.customer_id}>
                <span className="avatar">{customer.full_name.split(" ").map((part) => part[0]).join("")}</span>
                <span className="customer-list-copy"><strong>{customer.full_name}</strong><small>{customer.customer_id}</small></span>
                <span className="customer-chevron">›</span>
              </button>
            ))}
            {!filtered.length && <div className="empty-state small-empty"><strong>No customers found</strong><span>Try a different search.</span></div>}
          </div>
        </section>
        {selected ? (
          <div className="customer-profile-column">
            <section className="content-panel customer-profile">
              <div className="profile-header"><span className="avatar large">{selected.full_name.split(" ").map((part) => part[0]).join("")}</span>
                <div><span className="eyebrow">CUSTOMER PROFILE</span><h2>{selected.full_name}</h2><p>{selected.customer_id} · <span className="capitalize">{selected.segment?.replaceAll("_", " ")}</span></p></div></div>
              <dl className="profile-details">
                <dt>Occupation</dt><dd>{selected.profile?.occupation || "—"}</dd>
                <dt>Age</dt><dd>{selected.profile?.age ?? "—"}</dd>
                <dt>Account</dt><dd>{selected.account_id}</dd>
                <dt>History records</dt><dd>{history.length}</dd>
              </dl>
            </section>
            <section className="content-panel customer-history">
              <div className="panel-heading"><div><span className="eyebrow">FIXTURE-BACKED</span><h3>Transaction history</h3></div><span className="panel-count">{history.length} records</span></div>
              {history.length ? (
                <div className="customer-history-list">{history.map((transaction) => (
                  <button type="button" key={transaction.transaction_id} onClick={() => onSelectTransaction(transaction)}>
                    <span className={`history-direction ${transaction.direction}`}>{transaction.direction === "credit" ? "↑" : "↓"}</span>
                    <span className="history-copy"><strong>{transaction.payee}</strong><small>{transaction.transaction_id} · {formatTimestamp(transaction.timestamp)}</small></span>
                    <strong className="history-amount">{formatMoney(transaction.amount)}</strong>
                  </button>
                ))}</div>
              ) : <div className="empty-state small-empty"><strong>No history available</strong><span>No transaction history was returned for this customer.</span></div>}
            </section>
          </div>
        ) : (
          <div className="content-panel customer-placeholder"><span className="empty-symbol">♙</span><strong>Select a customer</strong><span>Choose a profile to see customer details and transaction history.</span></div>
        )}
      </div>
    </>
  );
}

function Activity({ entries, onNavigate }) {
  return (
    <>
      <PageHeading eyebrow="SESSION ACTIVITY" title="Activity" description="Execution details captured from requests made during this browser session." />
      {!entries.length ? (
        <div className="content-panel empty-state activity-empty"><span className="empty-symbol">◷</span>
          <strong>No session activity yet</strong><span>Submit a query or open a transaction investigation to see its real execution trace here.</span>
          <button className="primary-button" type="button" onClick={() => onNavigate("/investigations")}>Start an investigation →</button>
        </div>
      ) : (
        <div className="activity-feed">{[...entries].reverse().map((event) => (
          <section className="content-panel activity-event" key={event.id}>
            <div className="activity-event-heading"><div><span className="eyebrow">{event.source} · {event.interpreter || "API"}</span>
              <h3>{event.title}</h3><span>{event.timestamp.toLocaleString()}</span></div>
              {event.transactionId && <span className="event-id">{event.transactionId}</span>}</div>
            <TraceList entries={event.entries} />
          </section>
        ))}</div>
      )}
    </>
  );
}

export default function App() {
  const [route, setRoute] = useState(() => routeFromPath(window.location.pathname));
  const [connection, setConnection] = useState("checking");
  const [transactions, setTransactions] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [flaggedTransactions, setFlaggedTransactions] = useState([]);
  const [flaggedIds, setFlaggedIds] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [queryText, setQueryText] = useState("");
  const [queryResult, setQueryResult] = useState(null);
  const [queryLoading, setQueryLoading] = useState(false);
  const [queryError, setQueryError] = useState("");
  const [investigatedCount, setInvestigatedCount] = useState(0);
  const [selectedTransaction, setSelectedTransaction] = useState(null);
  const [investigation, setInvestigation] = useState(null);
  const [investigationLoading, setInvestigationLoading] = useState(false);
  const [investigationError, setInvestigationError] = useState("");
  const [activityEntries, setActivityEntries] = useState([]);

  const loadDashboard = useCallback(async () => {
    setLoading(true);
    setLoadError("");
    const healthTask = api.health()
      .then((data) => setConnection(data.status === "ok" ? "connected" : "offline"))
      .catch(() => setConnection("offline"));
    const transactionTask = api.transactions()
      .then((data) => {
        if (!Array.isArray(data)) throw new Error("Transaction response was not a list.");
        setTransactions(data);
      })
      .catch((error) => setLoadError(error.message));
    const customerTask = api.customers()
      .then((data) => {
        if (!Array.isArray(data)) throw new Error("Customer response was not a list.");
        setCustomers(data);
      })
      .catch((error) => setLoadError((current) => current || error.message));
    const reviewTask = api.query("List suspicious transactions")
      .then((data) => {
        const results = data.data?.transactions;
        if (!Array.isArray(results)) throw new Error("Review results were not returned.");
        setFlaggedTransactions(results);
        setFlaggedIds(new Set(results.map((item) => item.transaction.transaction_id)));
      })
      .catch(() => {
        setFlaggedTransactions([]);
        setFlaggedIds(null);
      });
    await Promise.all([healthTask, transactionTask, customerTask, reviewTask]);
    setLoading(false);
  }, []);

  useEffect(() => {
    loadDashboard();
    function onPopState() { setRoute(routeFromPath(window.location.pathname)); }
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, [loadDashboard]);

  function navigate(path) {
    const nextPath = routeFromPath(path);
    if (window.location.pathname !== nextPath) window.history.pushState({}, "", nextPath);
    setRoute(nextPath);
    window.scrollTo({ top: 0, behavior: "auto" });
  }

  const addActivity = useCallback((event) => {
    setActivityEntries((entries) => [...entries, {
      ...event,
      id: `${Date.now()}-${Math.random()}`,
      timestamp: new Date(),
    }]);
  }, []);

  async function runInvestigation(transaction) {
    setSelectedTransaction(transaction);
    setInvestigation(null);
    setInvestigationError("");
    setInvestigationLoading(true);
    try {
      const result = await api.investigate(transaction.transaction_id);
      setInvestigation(result);
      setInvestigatedCount((count) => count + 1);
      addActivity({
        source: "Transaction investigation",
        title: result.recommendation || `Investigation ${transaction.transaction_id}`,
        transactionId: transaction.transaction_id,
        entries: result.execution_trace || [],
      });
    } catch (error) {
      setInvestigationError(error.message);
    } finally {
      setInvestigationLoading(false);
    }
  }

  async function submitQuery(event) {
    event.preventDefault();
    const message = queryText.trim();
    if (!message) return;
    setQueryLoading(true);
    setQueryError("");
    setQueryResult(null);
    try {
      const result = await api.query(message);
      setQueryResult(result);
      addActivity({
        source: "Natural-language query",
        title: result.answer,
        transactionId: result.data?.transaction?.transaction_id || result.routing?.entities?.transaction_id,
        interpreter: result.interpreter,
        entries: result.trace || [],
      });
    } catch (error) {
      setQueryError(error.message);
    } finally {
      setQueryLoading(false);
    }
  }

  function openFromResponse(transaction) {
    const matched = transactions.find((item) => item.transaction_id === transaction.transaction_id) || transaction;
    runInvestigation(matched);
  }

  function closeInvestigation() {
    setSelectedTransaction(null);
    setInvestigation(null);
    setInvestigationError("");
  }

  const currentTitle = routes.find((item) => item.path === route)?.label || "Overview";
  const content = (() => {
    if (route === "/investigations") {
      return <Investigations queryText={queryText} setQueryText={setQueryText} onSubmit={submitQuery}
        result={queryResult} loading={queryLoading} error={queryError} onInvestigate={openFromResponse} />;
    }
    if (route === "/transactions") {
      return <Transactions transactions={transactions} customers={customers} flaggedIds={flaggedIds} onSelect={runInvestigation} />;
    }
    if (route === "/customers") {
      return <Customers customers={customers} transactions={transactions} onSelectTransaction={runInvestigation} />;
    }
    if (route === "/activity") return <Activity entries={activityEntries} onNavigate={navigate} />;
    return <Overview transactions={transactions} flaggedTransactions={flaggedTransactions} customers={customers}
      casesCount={investigatedCount} onNavigate={navigate} onSelect={runInvestigation} />;
  })();

  return (
    <div className="application">
      <aside className="sidebar">
        <a className="sidebar-brand" href="/overview" onClick={(event) => { event.preventDefault(); navigate("/overview"); }}>
          <span className="brand-mark">CR</span><span><strong>CASE ROOM</strong><small>FINANCIAL INTELLIGENCE</small></span>
        </a>
        <div className="sidebar-label">WORKSPACE</div>
        <nav className="side-navigation" aria-label="Main navigation">
          {routes.map((item) => (
            <a href={item.path} key={item.path} className={route === item.path ? "active" : ""}
              aria-current={route === item.path ? "page" : undefined}
              onClick={(event) => { event.preventDefault(); navigate(item.path); }}>
              <span className="nav-icon" aria-hidden="true">{item.icon}</span><span>{item.label}</span>
              {item.path === "/transactions" && <small>{transactions.length || "—"}</small>}
            </a>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="sidebar-simulated"><span className="simulated-dot" /><span><strong>SIMULATED DATA</strong><small>Fictional banking records</small></span></div>
          <div className="sidebar-user"><span className="avatar user-avatar">CR</span><span><strong>Case reviewer</strong><small>Local workspace</small></span></div>
        </div>
      </aside>

      <div className="main-column">
        <header className="topbar">
          <div><span className="topbar-context">Transaction Case Room</span><span className="topbar-divider">/</span><strong>{currentTitle}</strong></div>
          <div className="topbar-status">
            <span className={`connection-indicator ${connection}`}><i /></span>
            <span className="connection-label">{connection === "connected" ? "Backend connected" : connection === "checking" ? "Connecting…" : "Backend offline"}</span>
            <span className="environment-label"><i /> SIMULATED DATA</span>
            <button type="button" className="refresh-control" onClick={loadDashboard} disabled={loading} aria-label="Refresh data">↻</button>
          </div>
        </header>
        <main className="main-content">
          {loadError && (
            <div className="global-error" role="alert"><span>{loadError} Check that Flask is running.</span>
              <button type="button" onClick={loadDashboard}>Retry</button></div>
          )}
          {loading && !transactions.length ? <div className="loading-state page-loading"><span className="spinner" />Loading live data…</div> : content}
        </main>
        <footer className="app-footer"><span>TRANSACTION CASE ROOM</span><span>Local review workspace · all data is fictional</span></footer>
      </div>

      {selectedTransaction && <InvestigationPanel transaction={selectedTransaction} result={investigation}
        loading={investigationLoading} error={investigationError} onClose={closeInvestigation} />}
    </div>
  );
}
