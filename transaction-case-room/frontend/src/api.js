async function request(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...options.headers,
    },
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.error || payload.details || `Request failed (${response.status})`);
  }
  return payload;
}

export const api = {
  health: () => request("/api/health"),
  transactions: () => request("/api/transactions"),
  customers: () => request("/api/customers"),
  investigate: (transactionId) => request("/api/investigate", {
    method: "POST",
    body: JSON.stringify({ transaction_id: transactionId }),
  }),
  query: (message) => request("/api/query", {
    method: "POST",
    body: JSON.stringify({ message }),
  }),
};
