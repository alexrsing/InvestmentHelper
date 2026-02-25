# Frontend Rebuild Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a dark terminal-style stock analysis dashboard with Clerk authentication, portfolio summary, ETF position list with risk range penetration bars, and sparkline detail modals.

**Architecture:** Vite + React + TypeScript + Tailwind CSS frontend. Clerk's `<SignIn />` pre-built component for auth. `useAuth().getToken()` provides JWTs sent to the FastAPI backend. Recharts for sparkline charts in the detail modal.

**Tech Stack:** Vite, React 18, TypeScript, Tailwind CSS v4, @clerk/clerk-react, Recharts, React Router v7

---

### Task 1: Scaffold Vite + React + TypeScript project

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/index.html`
- Create: `frontend/tsconfig.json`
- Create: `frontend/tsconfig.app.json`
- Create: `frontend/tsconfig.node.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/vite-env.d.ts`

**Step 1: Create the Vite project**

```bash
cd /home/alex/InvestmentHelper
npm create vite@latest frontend -- --template react-ts
```

**Step 2: Install dependencies**

```bash
cd /home/alex/InvestmentHelper/frontend
npm install @clerk/clerk-react react-router-dom recharts
npm install -D tailwindcss @tailwindcss/vite
```

**Step 3: Configure Vite with Tailwind and API proxy**

Replace `frontend/vite.config.ts` with:

```ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 3000,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
```

**Step 4: Set up Tailwind CSS v4**

Replace `frontend/src/index.css` with:

```css
@import "tailwindcss";
```

**Step 5: Create `.env` file for Clerk publishable key**

Create `frontend/.env`:

```
VITE_CLERK_PUBLISHABLE_KEY=pk_test_PLACEHOLDER
```

Create `frontend/.env.example`:

```
VITE_CLERK_PUBLISHABLE_KEY=pk_test_YOUR_KEY_HERE
```

**Step 6: Set up minimal App.tsx to verify it works**

Replace `frontend/src/App.tsx` with:

```tsx
function App() {
  return <div className="bg-[#0d1117] text-green-400 min-h-screen flex items-center justify-center font-mono text-2xl">Investment Helper</div>;
}

export default App;
```

Ensure `frontend/src/main.tsx` imports `./index.css`.

**Step 7: Verify the dev server starts**

```bash
cd /home/alex/InvestmentHelper/frontend && npm run dev
```

Expected: Dev server starts on port 3000, dark page with green "Investment Helper" text.

**Step 8: Commit**

```bash
git add frontend/
git commit -m "feat: scaffold Vite + React + TS + Tailwind frontend"
```

---

### Task 2: TypeScript types

**Files:**
- Create: `frontend/src/types/index.ts`

**Step 1: Create type definitions**

```ts
export interface ETFPosition {
  ticker: string;
  name: string | null;
  current_price: number | null;
  open_price: number | null;
  risk_range_low: number | null;
  risk_range_high: number | null;
  shares: number;
}

export interface PortfolioSummary {
  total_value: number;
  initial_value: number;
  percent_change: number;
  positions: ETFPosition[];
}

export interface ETFHistoryItem {
  date: string;
  open_price: number;
  high_price: number;
  low_price: number;
  close_price: number;
  adjusted_close: number | null;
  volume: number;
  risk_range_low?: number;
  risk_range_high?: number;
}

export interface ETFHistoryResponse {
  ticker: string;
  history: ETFHistoryItem[];
  total_records: number;
}
```

**Step 2: Commit**

```bash
git add frontend/src/types/
git commit -m "feat: add TypeScript type definitions"
```

---

### Task 3: API client with Clerk token injection

**Files:**
- Create: `frontend/src/api/client.ts`

**Step 1: Create the fetch wrapper**

```ts
export async function apiFetch<T>(
  path: string,
  getToken: () => Promise<string | null>,
  options?: RequestInit
): Promise<T> {
  const token = await getToken();
  const res = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options?.headers,
    },
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || `Request failed: ${res.status}`);
  }

  return res.json();
}
```

**Step 2: Commit**

```bash
git add frontend/src/api/
git commit -m "feat: add API client with Clerk token injection"
```

---

### Task 4: Data hooks (usePortfolio, useETFPositions, useETFHistory)

**Files:**
- Create: `frontend/src/hooks/usePortfolio.ts`
- Create: `frontend/src/hooks/useETFPositions.ts`
- Create: `frontend/src/hooks/useETFHistory.ts`

**Step 1: Create usePortfolio hook**

```ts
import { useState, useEffect } from "react";
import { useAuth } from "@clerk/clerk-react";
import { apiFetch } from "../api/client";
import type { PortfolioSummary } from "../types";

export function usePortfolio() {
  const { getToken } = useAuth();
  const [data, setData] = useState<PortfolioSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    apiFetch<PortfolioSummary>("/api/v1/portfolio", getToken)
      .then((d) => { if (!cancelled) setData(d); })
      .catch((e) => { if (!cancelled) setError(e.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [getToken]);

  return { data, loading, error };
}
```

**Step 2: Create useETFPositions hook**

This hook does NOT call a separate endpoint — it reads positions from the portfolio data. The `Dashboard` component will pass positions from `usePortfolio` down to the ETF list. So we don't need a separate `useETFPositions` hook. Skip this file.

**Step 3: Create useETFHistory hook**

```ts
import { useState, useCallback } from "react";
import { useAuth } from "@clerk/clerk-react";
import { apiFetch } from "../api/client";
import type { ETFHistoryResponse } from "../types";

export function useETFHistory() {
  const { getToken } = useAuth();
  const [data, setData] = useState<ETFHistoryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchHistory = useCallback(
    (ticker: string) => {
      setLoading(true);
      setError(null);
      setData(null);
      apiFetch<ETFHistoryResponse>(
        `/api/v1/etfs/${ticker}/history?limit=10`,
        getToken
      )
        .then(setData)
        .catch((e) => setError(e.message))
        .finally(() => setLoading(false));
    },
    [getToken]
  );

  return { data, loading, error, fetchHistory };
}
```

**Step 4: Commit**

```bash
git add frontend/src/hooks/
git commit -m "feat: add usePortfolio and useETFHistory data hooks"
```

---

### Task 5: Clerk auth setup and routing

**Files:**
- Modify: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx` (replace)
- Create: `frontend/src/pages/SignInPage.tsx`

**Step 1: Set up ClerkProvider in main.tsx**

```tsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { ClerkProvider } from "@clerk/clerk-react";
import { dark } from "@clerk/themes";
import App from "./App";
import "./index.css";

const clerkPubKey = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY;
if (!clerkPubKey) throw new Error("Missing VITE_CLERK_PUBLISHABLE_KEY");

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ClerkProvider publishableKey={clerkPubKey} appearance={{ baseTheme: dark }}>
      <App />
    </ClerkProvider>
  </StrictMode>
);
```

**Step 2: Create SignInPage**

```tsx
import { SignIn } from "@clerk/clerk-react";

export default function SignInPage() {
  return (
    <div className="min-h-screen bg-[#0d1117] flex items-center justify-center">
      <SignIn routing="path" path="/sign-in" afterSignInUrl="/" />
    </div>
  );
}
```

**Step 3: Create App with routing**

```tsx
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import {
  SignedIn,
  SignedOut,
  RedirectToSignIn,
} from "@clerk/clerk-react";
import SignInPage from "./pages/SignInPage";
import Dashboard from "./pages/Dashboard";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/sign-in/*" element={<SignInPage />} />
        <Route
          path="/"
          element={
            <>
              <SignedIn>
                <Dashboard />
              </SignedIn>
              <SignedOut>
                <RedirectToSignIn />
              </SignedOut>
            </>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
```

**Step 4: Create placeholder Dashboard page**

Create `frontend/src/pages/Dashboard.tsx`:

```tsx
export default function Dashboard() {
  return (
    <div className="min-h-screen bg-[#0d1117] text-green-400 font-mono p-4">
      Dashboard placeholder
    </div>
  );
}
```

**Step 5: Commit**

```bash
git add frontend/src/
git commit -m "feat: add Clerk auth, routing, and sign-in page"
```

---

### Task 6: Navbar component

**Files:**
- Create: `frontend/src/components/layout/Navbar.tsx`

**Step 1: Create the Navbar**

```tsx
import { UserButton } from "@clerk/clerk-react";

export default function Navbar() {
  return (
    <nav className="flex items-center justify-between px-6 py-3 border-b border-gray-800 bg-[#0d1117]">
      <div className="flex items-center gap-2">
        <span className="text-green-400 font-mono font-bold text-lg tracking-wider">
          INVESTMENT HELPER
        </span>
      </div>
      <UserButton
        appearance={{
          elements: { avatarBox: "w-8 h-8" },
        }}
      />
    </nav>
  );
}
```

**Step 2: Commit**

```bash
git add frontend/src/components/
git commit -m "feat: add Navbar with Clerk UserButton"
```

---

### Task 7: PortfolioSummary component

**Files:**
- Create: `frontend/src/components/portfolio/PortfolioSummary.tsx`

**Step 1: Create the component**

```tsx
import type { PortfolioSummary as PortfolioSummaryType } from "../../types";

interface Props {
  data: PortfolioSummaryType;
}

export default function PortfolioSummary({ data }: Props) {
  const isPositive = data.percent_change >= 0;
  const changeColor = isPositive ? "text-green-400" : "text-red-400";
  const sign = isPositive ? "+" : "";

  const fmt = (v: number) =>
    v.toLocaleString("en-US", { style: "currency", currency: "USD" });

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
      <div className="border border-gray-800 rounded p-4 bg-[#161b22]">
        <div className="text-xs text-gray-500 uppercase tracking-wider mb-1">
          Total Value
        </div>
        <div className="text-xl font-mono text-gray-100">{fmt(data.total_value)}</div>
      </div>
      <div className="border border-gray-800 rounded p-4 bg-[#161b22]">
        <div className="text-xs text-gray-500 uppercase tracking-wider mb-1">
          Initial Value
        </div>
        <div className="text-xl font-mono text-gray-100">{fmt(data.initial_value)}</div>
      </div>
      <div className="border border-gray-800 rounded p-4 bg-[#161b22]">
        <div className="text-xs text-gray-500 uppercase tracking-wider mb-1">
          Change
        </div>
        <div className={`text-xl font-mono ${changeColor}`}>
          {sign}{data.percent_change.toFixed(2)}%
        </div>
      </div>
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add frontend/src/components/portfolio/
git commit -m "feat: add PortfolioSummary component"
```

---

### Task 8: RiskBar component

**Files:**
- Create: `frontend/src/components/etf/RiskBar.tsx`

**Step 1: Create the component**

```tsx
interface Props {
  low: number;
  high: number;
  current: number;
}

export default function RiskBar({ low, high, current }: Props) {
  const range = high - low;
  const penetration = range > 0 ? ((current - low) / range) * 100 : 0;
  const clamped = Math.max(0, Math.min(100, penetration));

  let barColor = "bg-green-500";
  if (clamped > 70) barColor = "bg-red-500";
  else if (clamped > 40) barColor = "bg-yellow-500";

  return (
    <div className="flex items-center gap-2 min-w-[180px]">
      <div className="relative w-full h-2 bg-gray-800 rounded overflow-hidden">
        <div
          className={`absolute top-0 left-0 h-full rounded ${barColor}`}
          style={{ width: `${clamped}%` }}
        />
      </div>
      <span className="text-xs font-mono text-gray-400 w-10 text-right">
        {clamped.toFixed(0)}%
      </span>
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add frontend/src/components/etf/RiskBar.tsx
git commit -m "feat: add RiskBar penetration component"
```

---

### Task 9: ETFRow component

**Files:**
- Create: `frontend/src/components/etf/ETFRow.tsx`

**Step 1: Create the component**

```tsx
import type { ETFPosition } from "../../types";
import RiskBar from "./RiskBar";

interface Props {
  position: ETFPosition;
  onClick: (ticker: string) => void;
}

export default function ETFRow({ position, onClick }: Props) {
  const {
    ticker,
    name,
    current_price,
    open_price,
    risk_range_low,
    risk_range_high,
  } = position;

  const fmt = (v: number | null) =>
    v != null
      ? v.toLocaleString("en-US", { style: "currency", currency: "USD" })
      : "—";

  const priceChange =
    current_price != null && open_price != null
      ? current_price - open_price
      : null;
  const changeColor =
    priceChange != null && priceChange >= 0 ? "text-green-400" : "text-red-400";

  return (
    <button
      type="button"
      onClick={() => onClick(ticker)}
      className="w-full text-left border border-gray-800 rounded bg-[#161b22] hover:bg-[#1c2333] transition-colors p-4 cursor-pointer"
    >
      <div className="flex flex-col md:flex-row md:items-center gap-3">
        {/* Ticker + Name */}
        <div className="md:w-32 shrink-0">
          <span className="text-green-400 font-mono font-bold text-lg">
            {ticker}
          </span>
          {name && (
            <div className="text-xs text-gray-500 truncate">{name}</div>
          )}
        </div>

        {/* Prices */}
        <div className="flex gap-6 md:gap-8 flex-wrap md:flex-nowrap flex-1">
          <div>
            <div className="text-xs text-gray-500 uppercase">Current</div>
            <div className={`font-mono ${changeColor}`}>
              {fmt(current_price)}
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500 uppercase">Open</div>
            <div className="font-mono text-gray-300">{fmt(open_price)}</div>
          </div>
          <div>
            <div className="text-xs text-gray-500 uppercase">Risk Low</div>
            <div className="font-mono text-gray-300">
              {fmt(risk_range_low)}
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500 uppercase">Risk High</div>
            <div className="font-mono text-gray-300">
              {fmt(risk_range_high)}
            </div>
          </div>
        </div>

        {/* Risk Bar */}
        <div className="md:w-48 shrink-0">
          <div className="text-xs text-gray-500 uppercase mb-1">
            Penetration
          </div>
          {risk_range_low != null &&
          risk_range_high != null &&
          current_price != null ? (
            <RiskBar
              low={risk_range_low}
              high={risk_range_high}
              current={current_price}
            />
          ) : (
            <span className="text-xs text-gray-600">—</span>
          )}
        </div>
      </div>
    </button>
  );
}
```

**Step 2: Commit**

```bash
git add frontend/src/components/etf/ETFRow.tsx
git commit -m "feat: add ETFRow component with price and risk display"
```

---

### Task 10: ETFList component

**Files:**
- Create: `frontend/src/components/etf/ETFList.tsx`

**Step 1: Create the component**

```tsx
import type { ETFPosition } from "../../types";
import ETFRow from "./ETFRow";

interface Props {
  positions: ETFPosition[];
  onSelectETF: (ticker: string) => void;
}

export default function ETFList({ positions, onSelectETF }: Props) {
  if (positions.length === 0) {
    return (
      <div className="text-gray-500 font-mono text-center py-8">
        No positions found
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      {positions.map((pos) => (
        <ETFRow key={pos.ticker} position={pos} onClick={onSelectETF} />
      ))}
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add frontend/src/components/etf/ETFList.tsx
git commit -m "feat: add ETFList container component"
```

---

### Task 11: ETFDetailModal with sparkline chart

**Files:**
- Create: `frontend/src/components/etf/ETFDetailModal.tsx`

**Step 1: Create the modal with Recharts sparkline**

```tsx
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import type { ETFHistoryResponse } from "../../types";

interface Props {
  ticker: string;
  data: ETFHistoryResponse | null;
  loading: boolean;
  error: string | null;
  onClose: () => void;
}

export default function ETFDetailModal({
  ticker,
  data,
  loading,
  error,
  onClose,
}: Props) {
  const history = data?.history ?? [];
  // Sort chronologically for the chart (oldest first)
  const sorted = [...history].sort((a, b) => a.date.localeCompare(b.date));
  const hasEnoughData = sorted.length >= 2;

  // Extract risk range values from the most recent data point if available
  const latestWithRisk = sorted.findLast(
    (h) => h.risk_range_low != null && h.risk_range_high != null
  );
  const riskLow = latestWithRisk?.risk_range_low;
  const riskHigh = latestWithRisk?.risk_range_high;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70"
      onClick={onClose}
    >
      <div
        className="bg-[#161b22] border border-gray-700 rounded-lg w-full max-w-2xl mx-4 p-6"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-green-400 font-mono font-bold text-xl">
            {ticker}
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="text-gray-500 hover:text-gray-300 font-mono text-lg cursor-pointer"
          >
            [CLOSE]
          </button>
        </div>

        {/* Content */}
        {loading && (
          <div className="text-gray-500 font-mono text-center py-12">
            Loading...
          </div>
        )}

        {error && (
          <div className="text-red-400 font-mono text-center py-12">
            {error}
          </div>
        )}

        {!loading && !error && !hasEnoughData && (
          <div className="text-yellow-400 font-mono text-center py-12">
            ETF does not have required history data
          </div>
        )}

        {!loading && !error && hasEnoughData && (
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={sorted}>
                <XAxis
                  dataKey="date"
                  tick={{ fill: "#6b7280", fontSize: 10, fontFamily: "monospace" }}
                  axisLine={{ stroke: "#374151" }}
                  tickLine={false}
                />
                <YAxis
                  domain={["auto", "auto"]}
                  tick={{ fill: "#6b7280", fontSize: 10, fontFamily: "monospace" }}
                  axisLine={{ stroke: "#374151" }}
                  tickLine={false}
                  tickFormatter={(v: number) => `$${v}`}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#0d1117",
                    border: "1px solid #374151",
                    borderRadius: "4px",
                    fontFamily: "monospace",
                    fontSize: "12px",
                  }}
                  labelStyle={{ color: "#9ca3af" }}
                  itemStyle={{ color: "#34d399" }}
                  formatter={(value: number) => [
                    `$${value.toFixed(2)}`,
                    "Price",
                  ]}
                />
                {/* Current price line */}
                <Line
                  type="monotone"
                  dataKey="close_price"
                  stroke="#34d399"
                  strokeWidth={2}
                  dot={false}
                  name="Price"
                />
                {/* Risk range reference lines */}
                {riskLow != null && (
                  <ReferenceLine
                    y={riskLow}
                    stroke="#f87171"
                    strokeDasharray="4 4"
                    label={{
                      value: `Low $${riskLow}`,
                      fill: "#f87171",
                      fontSize: 10,
                      fontFamily: "monospace",
                      position: "left",
                    }}
                  />
                )}
                {riskHigh != null && (
                  <ReferenceLine
                    y={riskHigh}
                    stroke="#f87171"
                    strokeDasharray="4 4"
                    label={{
                      value: `High $${riskHigh}`,
                      fill: "#f87171",
                      fontSize: 10,
                      fontFamily: "monospace",
                      position: "left",
                    }}
                  />
                )}
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add frontend/src/components/etf/ETFDetailModal.tsx
git commit -m "feat: add ETFDetailModal with sparkline and risk range lines"
```

---

### Task 12: Dashboard page — wire everything together

**Files:**
- Modify: `frontend/src/pages/Dashboard.tsx`

**Step 1: Build the full Dashboard**

```tsx
import { useState } from "react";
import Navbar from "../components/layout/Navbar";
import PortfolioSummary from "../components/portfolio/PortfolioSummary";
import ETFList from "../components/etf/ETFList";
import ETFDetailModal from "../components/etf/ETFDetailModal";
import { usePortfolio } from "../hooks/usePortfolio";
import { useETFHistory } from "../hooks/useETFHistory";

export default function Dashboard() {
  const { data: portfolio, loading, error } = usePortfolio();
  const {
    data: historyData,
    loading: historyLoading,
    error: historyError,
    fetchHistory,
  } = useETFHistory();
  const [selectedTicker, setSelectedTicker] = useState<string | null>(null);

  const handleSelectETF = (ticker: string) => {
    setSelectedTicker(ticker);
    fetchHistory(ticker);
  };

  const handleCloseModal = () => {
    setSelectedTicker(null);
  };

  return (
    <div className="min-h-screen bg-[#0d1117] text-gray-100">
      <Navbar />

      <main className="max-w-6xl mx-auto px-4 py-6">
        {loading && (
          <div className="text-gray-500 font-mono text-center py-12">
            Loading portfolio...
          </div>
        )}

        {error && (
          <div className="text-red-400 font-mono text-center py-12">
            {error}
          </div>
        )}

        {portfolio && (
          <>
            <PortfolioSummary data={portfolio} />
            <div className="mb-3">
              <h2 className="text-sm text-gray-500 uppercase tracking-wider font-mono">
                Positions
              </h2>
            </div>
            <ETFList
              positions={portfolio.positions}
              onSelectETF={handleSelectETF}
            />
          </>
        )}
      </main>

      {selectedTicker && (
        <ETFDetailModal
          ticker={selectedTicker}
          data={historyData}
          loading={historyLoading}
          error={historyError}
          onClose={handleCloseModal}
        />
      )}
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add frontend/src/pages/Dashboard.tsx
git commit -m "feat: wire Dashboard with portfolio summary, ETF list, and detail modal"
```

---

### Task 13: Backend — add risk range fields to ETF model and schema

**Files:**
- Modify: `backend/app/models/etf.py:21-29` — add `risk_range_low`, `risk_range_high`, `open_price` attributes
- Modify: `backend/app/schemas/etf.py:23-36` — add fields to ETFResponse

**Step 1: Add fields to the PynamoDB ETF model**

In `backend/app/models/etf.py`, add after `current_price` (line 29):

```python
    open_price = NumberAttribute(null=True)
    risk_range_low = NumberAttribute(null=True)
    risk_range_high = NumberAttribute(null=True)
```

**Step 2: Add fields to the ETFResponse schema**

In `backend/app/schemas/etf.py`, add after the `current_price` field (line 30):

```python
    open_price: Optional[float] = Field(None, gt=0, description="Opening price")
    risk_range_low: Optional[float] = Field(None, gt=0, description="Risk range lower bound")
    risk_range_high: Optional[float] = Field(None, gt=0, description="Risk range upper bound")
```

**Step 3: Update the ETF router to include new fields**

In `backend/app/routers/etfs.py`, update the `ETFResponse(...)` constructor (lines 73-83) to include:

```python
            open_price=etf.open_price,
            risk_range_low=etf.risk_range_low,
            risk_range_high=etf.risk_range_high,
```

**Step 4: Commit**

```bash
git add backend/app/models/etf.py backend/app/schemas/etf.py backend/app/routers/etfs.py
git commit -m "feat: add risk_range_low, risk_range_high, open_price to ETF model and schema"
```

---

### Task 14: Backend — add portfolio endpoint

**Files:**
- Create: `backend/app/models/portfolio.py`
- Create: `backend/app/schemas/portfolio.py`
- Create: `backend/app/routers/portfolio.py`
- Modify: `backend/app/main.py:44-47` — register the new router

**Step 1: Create the Portfolio model**

```python
from pynamodb.models import Model
from pynamodb.attributes import (
    UnicodeAttribute,
    NumberAttribute,
    UTCDateTimeAttribute,
    ListAttribute,
    MapAttribute,
)
from datetime import datetime, timezone


class HoldingMap(MapAttribute):
    ticker = UnicodeAttribute()
    shares = NumberAttribute()
    cost_basis = NumberAttribute()  # total cost paid


class Portfolio(Model):
    class Meta:
        table_name = "portfolios"
        region = "us-east-1"

    user_id = UnicodeAttribute(hash_key=True)
    initial_value = NumberAttribute(default=0)
    holdings = ListAttribute(of=HoldingMap, default=list)
    created_at = UTCDateTimeAttribute(default=lambda: datetime.now(timezone.utc))
    updated_at = UTCDateTimeAttribute(default=lambda: datetime.now(timezone.utc))
```

**Step 2: Create portfolio schemas**

```python
from pydantic import BaseModel, Field
from typing import List, Optional


class HoldingResponse(BaseModel):
    ticker: str
    shares: float
    cost_basis: float


class PositionResponse(BaseModel):
    ticker: str
    name: Optional[str] = None
    current_price: Optional[float] = None
    open_price: Optional[float] = None
    risk_range_low: Optional[float] = None
    risk_range_high: Optional[float] = None
    shares: float


class PortfolioResponse(BaseModel):
    total_value: float
    initial_value: float
    percent_change: float
    positions: List[PositionResponse]
```

**Step 3: Create portfolio router**

```python
from fastapi import APIRouter, Depends, HTTPException, status
from pynamodb.exceptions import DoesNotExist

from app.core.dependencies import get_current_active_user
from app.models.portfolio import Portfolio
from app.models.etf import ETF
from app.schemas.portfolio import PortfolioResponse, PositionResponse
from app.schemas.etf import ErrorResponse

router = APIRouter(
    prefix="/portfolio",
    tags=["Portfolio"],
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        404: {"model": ErrorResponse, "description": "Not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)


@router.get("", response_model=PortfolioResponse)
async def get_portfolio(current_user: dict = Depends(get_current_active_user)):
    user_id = current_user["user_id"]

    try:
        portfolio = Portfolio.get(user_id)
    except DoesNotExist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Portfolio not found",
        )
    except Exception as e:
        print(f"Error fetching portfolio for {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching portfolio",
        )

    positions = []
    total_value = 0.0

    for holding in portfolio.holdings:
        try:
            etf = ETF.get(holding.ticker)
            price = etf.current_price or 0
            position_value = price * holding.shares
            total_value += position_value
            positions.append(
                PositionResponse(
                    ticker=holding.ticker,
                    name=etf.name,
                    current_price=etf.current_price,
                    open_price=getattr(etf, "open_price", None),
                    risk_range_low=getattr(etf, "risk_range_low", None),
                    risk_range_high=getattr(etf, "risk_range_high", None),
                    shares=holding.shares,
                )
            )
        except DoesNotExist:
            positions.append(
                PositionResponse(
                    ticker=holding.ticker,
                    shares=holding.shares,
                )
            )
        except Exception as e:
            print(f"Error fetching ETF {holding.ticker}: {e}")
            positions.append(
                PositionResponse(
                    ticker=holding.ticker,
                    shares=holding.shares,
                )
            )

    initial_value = portfolio.initial_value or 0
    percent_change = (
        ((total_value - initial_value) / initial_value * 100)
        if initial_value > 0
        else 0.0
    )

    return PortfolioResponse(
        total_value=total_value,
        initial_value=initial_value,
        percent_change=percent_change,
        positions=positions,
    )
```

**Step 4: Register the router in main.py**

In `backend/app/main.py`, add after line 11:

```python
from app.routers import portfolio
```

Add after line 47 (after the etfs router registration):

```python
app.include_router(
    portfolio.router,
    prefix=settings.API_V1_STR,
)
```

**Step 5: Commit**

```bash
git add backend/app/models/portfolio.py backend/app/schemas/portfolio.py backend/app/routers/portfolio.py backend/app/main.py
git commit -m "feat: add portfolio endpoint with holdings and value calculation"
```

---

### Task 15: Backend — add list-all ETFs endpoint

**Files:**
- Modify: `backend/app/routers/etfs.py` — add a new `GET /` endpoint before the existing `GET /{ticker}`

**Step 1: Add the list endpoint**

Add before the `get_etf` function in `backend/app/routers/etfs.py`:

```python
@router.get(
    "",
    response_model=list[ETFResponse],
    summary="List all ETFs",
    description="Retrieve all ETFs in the system",
)
async def list_etfs(
    current_user: dict = Depends(get_current_active_user),
):
    try:
        etfs = ETF.scan()
        return [
            ETFResponse(
                ticker=etf.ticker,
                name=etf.name,
                description=etf.description,
                expense_ratio=etf.expense_ratio,
                aum=etf.aum,
                inception_date=etf.inception_date,
                current_price=etf.current_price,
                open_price=etf.open_price,
                risk_range_low=etf.risk_range_low,
                risk_range_high=etf.risk_range_high,
                created_at=etf.created_at,
                updated_at=etf.updated_at,
            )
            for etf in etfs
        ]
    except Exception as e:
        print(f"Error listing ETFs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while listing ETFs",
        )
```

**Step 2: Commit**

```bash
git add backend/app/routers/etfs.py
git commit -m "feat: add list-all ETFs endpoint"
```

---

### Task 16: Verify full frontend builds

**Step 1: Run the build**

```bash
cd /home/alex/InvestmentHelper/frontend && npm run build
```

Expected: Build succeeds with no TypeScript errors.

**Step 2: Fix any build errors**

If there are TS errors, fix them.

**Step 3: Commit any fixes**

```bash
git add frontend/
git commit -m "fix: resolve build errors"
```

---

### Task 17: Update CLAUDE.md

**Files:**
- Modify: `/home/alex/InvestmentHelper/CLAUDE.md`

**Step 1: Update the frontend section in CLAUDE.md**

Update the Frontend section to reflect the new structure:

- Clerk authentication with `@clerk/clerk-react`
- Dark terminal-style dashboard
- Routes: `/sign-in` (Clerk), `/` (Dashboard)
- Components: Navbar, PortfolioSummary, ETFList, ETFRow, RiskBar, ETFDetailModal
- Hooks: usePortfolio, useETFHistory
- API client with Clerk token injection
- Recharts for sparkline charts

Also update the backend section to mention the new portfolio endpoint and list-all ETFs endpoint.

**Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md for rebuilt frontend and new endpoints"
```
