import {
  Activity,
  ArrowDownUp,
  BriefcaseBusiness,
  KeyRound,
  LogOut,
  Plus,
  RefreshCw,
  Search,
  ShieldCheck
} from "lucide-react";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import { ApiError, Asset, Portfolio, Position, Transaction, api } from "./api";

const storedToken = localStorage.getItem("portfolio_access_token");
const storedRefreshToken = localStorage.getItem("portfolio_refresh_token");

type Notice = { tone: "success" | "error"; text: string } | null;

function toLocalDatetimeInput(date: Date) {
  const offsetMs = date.getTimezoneOffset() * 60_000;
  return new Date(date.getTime() - offsetMs).toISOString().slice(0, 16);
}

function normalizeError(error: unknown) {
  if (error instanceof ApiError) {
    return `${error.status}: ${error.message}`;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Unexpected error";
}

export function App() {
  const [token, setToken] = useState(storedToken ?? "");
  const [refreshToken, setRefreshToken] = useState(storedRefreshToken ?? "");
  const [notice, setNotice] = useState<Notice>(null);
  const [loading, setLoading] = useState(false);

  const [email, setEmail] = useState("teste@example.com");
  const [password, setPassword] = useState("password123");
  const [fullName, setFullName] = useState("Teste Local");

  const [portfolios, setPortfolios] = useState<Portfolio[]>([]);
  const [selectedPortfolioId, setSelectedPortfolioId] = useState("");
  const [portfolioName, setPortfolioName] = useState("Carteira Teste");
  const [baseCurrency, setBaseCurrency] = useState("USD");

  const [assetSymbol, setAssetSymbol] = useState("AAPL");
  const [lastAsset, setLastAsset] = useState<Asset | null>(null);

  const [transactionType, setTransactionType] = useState<"buy" | "sell">("buy");
  const [transactionSymbol, setTransactionSymbol] = useState("AAPL");
  const [quantity, setQuantity] = useState("10");
  const [unitPrice, setUnitPrice] = useState("150.25");
  const [fees, setFees] = useState("1.50");
  const [taxes, setTaxes] = useState("0");
  const [currency, setCurrency] = useState("USD");
  const [tradeDate, setTradeDate] = useState(toLocalDatetimeInput(new Date()));
  const [notes, setNotes] = useState("Compra teste");

  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [positions, setPositions] = useState<Position[]>([]);

  const selectedPortfolio = useMemo(
    () => portfolios.find((portfolio) => portfolio.id === selectedPortfolioId) ?? null,
    [portfolios, selectedPortfolioId]
  );

  const setTokens = (access: string, refresh: string) => {
    setToken(access);
    setRefreshToken(refresh);
    localStorage.setItem("portfolio_access_token", access);
    localStorage.setItem("portfolio_refresh_token", refresh);
  };

  const clearSession = () => {
    setToken("");
    setRefreshToken("");
    setPortfolios([]);
    setSelectedPortfolioId("");
    setTransactions([]);
    setPositions([]);
    localStorage.removeItem("portfolio_access_token");
    localStorage.removeItem("portfolio_refresh_token");
  };

  const run = async (action: () => Promise<void>, success?: string) => {
    setLoading(true);
    setNotice(null);
    try {
      await action();
      if (success) {
        setNotice({ tone: "success", text: success });
      }
    } catch (error) {
      setNotice({ tone: "error", text: normalizeError(error) });
    } finally {
      setLoading(false);
    }
  };

  const loadPortfolios = useCallback(async () => {
    if (!token) return;
    const data = await api.listPortfolios(token);
    setPortfolios(data);
    setSelectedPortfolioId((current) => current || data[0]?.id || "");
  }, [token]);

  const loadPortfolioData = useCallback(async () => {
    if (!token || !selectedPortfolioId) return;
    const [transactionData, positionData] = await Promise.all([
      api.listTransactions(token, selectedPortfolioId),
      api.listPositions(token, selectedPortfolioId)
    ]);
    setTransactions(transactionData);
    setPositions(positionData);
  }, [selectedPortfolioId, token]);

  useEffect(() => {
    void loadPortfolios();
  }, [loadPortfolios]);

  useEffect(() => {
    void loadPortfolioData();
  }, [loadPortfolioData]);

  const handleRegister = (event: FormEvent) => {
    event.preventDefault();
    void run(
      async () => {
        await api.register({ email, password, full_name: fullName || undefined });
        const session = await api.login({ email, password });
        setTokens(session.access_token, session.refresh_token);
      },
      "Account ready"
    );
  };

  const handleLogin = (event: FormEvent) => {
    event.preventDefault();
    void run(
      async () => {
        const session = await api.login({ email, password });
        setTokens(session.access_token, session.refresh_token);
      },
      "Session started"
    );
  };

  const handleCreatePortfolio = (event: FormEvent) => {
    event.preventDefault();
    void run(
      async () => {
        const portfolio = await api.createPortfolio(token, {
          name: portfolioName,
          base_currency: baseCurrency,
          description: "Created from the local dashboard"
        });
        await loadPortfolios();
        setSelectedPortfolioId(portfolio.id);
      },
      "Portfolio created"
    );
  };

  const handleLookupAsset = (event: FormEvent) => {
    event.preventDefault();
    void run(
      async () => {
        const asset = await api.lookupAsset(token, assetSymbol);
        setLastAsset(asset);
        setTransactionSymbol(asset.symbol);
        setCurrency(asset.currency);
      },
      "Asset resolved"
    );
  };

  const handleCreateTransaction = (event: FormEvent) => {
    event.preventDefault();
    void run(
      async () => {
        if (!selectedPortfolioId) {
          throw new Error("Create or select a portfolio first");
        }
        const idempotencyKey = crypto.randomUUID();
        await api.createTransaction(token, selectedPortfolioId, idempotencyKey, {
          symbol: transactionSymbol,
          transaction_type: transactionType,
          quantity,
          unit_price: unitPrice,
          fees,
          taxes,
          currency,
          trade_date: new Date(tradeDate).toISOString(),
          notes: notes || null
        });
        await loadPortfolioData();
      },
      "Transaction recorded"
    );
  };

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">
            <Activity size={22} />
          </span>
          <div>
            <strong>Portfolio Tracker</strong>
            <span>Local dashboard</span>
          </div>
        </div>

        <form className="panel auth-panel" onSubmit={handleLogin}>
          <div className="panel-heading">
            <KeyRound size={18} />
            <h2>Access</h2>
          </div>
          <label>
            Email
            <input value={email} onChange={(event) => setEmail(event.target.value)} />
          </label>
          <label>
            Password
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </label>
          <label>
            Name
            <input value={fullName} onChange={(event) => setFullName(event.target.value)} />
          </label>
          <div className="button-row">
            <button type="submit" disabled={loading}>
              <ShieldCheck size={16} />
              Login
            </button>
            <button type="button" className="secondary" disabled={loading} onClick={handleRegister}>
              <Plus size={16} />
              Register
            </button>
          </div>
        </form>

        <button className="ghost full-width" type="button" onClick={clearSession}>
          <LogOut size={16} />
          Clear session
        </button>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <p className="eyebrow">API workflow</p>
            <h1>{selectedPortfolio?.name ?? "Portfolio Console"}</h1>
          </div>
          <button type="button" className="secondary" onClick={() => void run(loadPortfolioData)}>
            <RefreshCw size={16} />
            Refresh
          </button>
        </header>

        {notice && <div className={`notice ${notice.tone}`}>{notice.text}</div>}

        <div className="grid two">
          <form className="panel" onSubmit={handleCreatePortfolio}>
            <div className="panel-heading">
              <BriefcaseBusiness size={18} />
              <h2>Portfolios</h2>
            </div>
            <label>
              Selected
              <select
                value={selectedPortfolioId}
                onChange={(event) => setSelectedPortfolioId(event.target.value)}
              >
                <option value="">None</option>
                {portfolios.map((portfolio) => (
                  <option key={portfolio.id} value={portfolio.id}>
                    {portfolio.name}
                  </option>
                ))}
              </select>
            </label>
            <div className="inline-fields">
              <label>
                Name
                <input
                  value={portfolioName}
                  onChange={(event) => setPortfolioName(event.target.value)}
                />
              </label>
              <label>
                Currency
                <input
                  value={baseCurrency}
                  maxLength={3}
                  onChange={(event) => setBaseCurrency(event.target.value.toUpperCase())}
                />
              </label>
            </div>
            <button type="submit" disabled={!token || loading}>
              <Plus size={16} />
              Create portfolio
            </button>
          </form>

          <form className="panel" onSubmit={handleLookupAsset}>
            <div className="panel-heading">
              <Search size={18} />
              <h2>Asset Lookup</h2>
            </div>
            <label>
              Symbol
              <input
                value={assetSymbol}
                onChange={(event) => setAssetSymbol(event.target.value.toUpperCase())}
              />
            </label>
            <button type="submit" disabled={!token || loading}>
              <Search size={16} />
              Resolve asset
            </button>
            {lastAsset && (
              <dl className="asset-result">
                <div>
                  <dt>Symbol</dt>
                  <dd>{lastAsset.symbol}</dd>
                </div>
                <div>
                  <dt>Name</dt>
                  <dd>{lastAsset.name}</dd>
                </div>
                <div>
                  <dt>Currency</dt>
                  <dd>{lastAsset.currency}</dd>
                </div>
              </dl>
            )}
          </form>
        </div>

        <form className="panel transaction-form" onSubmit={handleCreateTransaction}>
          <div className="panel-heading">
            <ArrowDownUp size={18} />
            <h2>New Transaction</h2>
          </div>
          <div className="transaction-grid">
            <label>
              Type
              <select
                value={transactionType}
                onChange={(event) => setTransactionType(event.target.value as "buy" | "sell")}
              >
                <option value="buy">Buy</option>
                <option value="sell">Sell</option>
              </select>
            </label>
            <label>
              Symbol
              <input
                value={transactionSymbol}
                onChange={(event) => setTransactionSymbol(event.target.value.toUpperCase())}
              />
            </label>
            <label>
              Quantity
              <input value={quantity} onChange={(event) => setQuantity(event.target.value)} />
            </label>
            <label>
              Unit price
              <input value={unitPrice} onChange={(event) => setUnitPrice(event.target.value)} />
            </label>
            <label>
              Fees
              <input value={fees} onChange={(event) => setFees(event.target.value)} />
            </label>
            <label>
              Taxes
              <input value={taxes} onChange={(event) => setTaxes(event.target.value)} />
            </label>
            <label>
              Currency
              <input
                value={currency}
                maxLength={3}
                onChange={(event) => setCurrency(event.target.value.toUpperCase())}
              />
            </label>
            <label>
              Trade date
              <input
                type="datetime-local"
                value={tradeDate}
                onChange={(event) => setTradeDate(event.target.value)}
              />
            </label>
          </div>
          <label>
            Notes
            <input value={notes} onChange={(event) => setNotes(event.target.value)} />
          </label>
          <button type="submit" disabled={!token || !selectedPortfolioId || loading}>
            <Plus size={16} />
            Record transaction
          </button>
        </form>

        <div className="grid two">
          <section className="panel table-panel">
            <div className="panel-heading">
              <ArrowDownUp size={18} />
              <h2>Transactions</h2>
            </div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Type</th>
                    <th>Qty</th>
                    <th>Price</th>
                    <th>P&L</th>
                    <th>Date</th>
                  </tr>
                </thead>
                <tbody>
                  {transactions.map((transaction) => (
                    <tr key={transaction.id}>
                      <td>{transaction.transaction_type}</td>
                      <td>{transaction.quantity}</td>
                      <td>
                        {transaction.currency} {transaction.unit_price}
                      </td>
                      <td>{transaction.realized_pnl}</td>
                      <td>{new Date(transaction.trade_date).toLocaleDateString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="panel table-panel">
            <div className="panel-heading">
              <Activity size={18} />
              <h2>Positions</h2>
            </div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Asset</th>
                    <th>Quantity</th>
                    <th>Avg cost</th>
                    <th>Realized</th>
                  </tr>
                </thead>
                <tbody>
                  {positions.map((position) => (
                    <tr key={position.id}>
                      <td>{position.asset_id.slice(0, 8)}</td>
                      <td>{position.quantity}</td>
                      <td>{position.average_cost}</td>
                      <td>{position.realized_pnl}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </div>
      </section>
    </main>
  );
}
