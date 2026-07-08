export type TokenPair = {
  access_token: string;
  refresh_token: string;
  token_type: string;
};

export type Portfolio = {
  id: string;
  name: string;
  description: string | null;
  base_currency: string;
};

export type Asset = {
  id: string;
  symbol: string;
  name: string;
  asset_type: string;
  currency: string;
  exchange: string | null;
};

export type Transaction = {
  id: string;
  asset_id: string;
  transaction_type: "buy" | "sell";
  quantity: string;
  unit_price: string;
  fees: string;
  taxes: string;
  realized_pnl: string;
  currency: string;
  trade_date: string;
  settlement_date: string | null;
  notes: string | null;
  idempotency_key: string | null;
};

export type Position = {
  id: string;
  asset_id: string;
  quantity: string;
  average_cost: string;
  realized_pnl: string;
};

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

const API_BASE = import.meta.env.VITE_API_URL ?? "";

async function request<T>(
  path: string,
  options: RequestInit = {},
  token?: string | null
): Promise<T> {
  const headers = new Headers(options.headers);
  if (!headers.has("Content-Type") && options.body) {
    headers.set("Content-Type", "application/json");
  }
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const payload = (await response.json()) as { detail?: string };
      detail = payload.detail ?? detail;
    } catch {
      // Keep the HTTP status text when the response is not JSON.
    }
    throw new ApiError(response.status, detail);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export const api = {
  register: (payload: { email: string; password: string; full_name?: string }) =>
    request("/api/v1/auth/register", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  login: (payload: { email: string; password: string }) =>
    request<TokenPair>("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  listPortfolios: (token: string) => request<Portfolio[]>("/api/v1/portfolios", {}, token),
  createPortfolio: (
    token: string,
    payload: { name: string; description?: string; base_currency: string }
  ) =>
    request<Portfolio>(
      "/api/v1/portfolios",
      { method: "POST", body: JSON.stringify(payload) },
      token
    ),
  lookupAsset: (token: string, symbol: string) =>
    request<Asset>(
      "/api/v1/assets/lookup",
      { method: "POST", body: JSON.stringify({ symbol }) },
      token
    ),
  listTransactions: (token: string, portfolioId: string) =>
    request<Transaction[]>(`/api/v1/portfolios/${portfolioId}/transactions`, {}, token),
  listPositions: (token: string, portfolioId: string) =>
    request<Position[]>(`/api/v1/portfolios/${portfolioId}/positions`, {}, token),
  createTransaction: (
    token: string,
    portfolioId: string,
    idempotencyKey: string,
    payload: Record<string, unknown>
  ) =>
    request<Transaction>(
      `/api/v1/portfolios/${portfolioId}/transactions`,
      {
        method: "POST",
        headers: { "Idempotency-Key": idempotencyKey },
        body: JSON.stringify(payload)
      },
      token
    )
};
