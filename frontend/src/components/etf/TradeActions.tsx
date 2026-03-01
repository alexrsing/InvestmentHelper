import { useState } from "react";
import type { ETFPosition, TradeRequest } from "../../types";

interface Props {
  position: ETFPosition;
  cashBalance: number;
  onTrade: (request: TradeRequest) => Promise<void>;
  submitting: boolean;
}

export default function TradeActions({ position, cashBalance, onTrade, submitting }: Props) {
  const { recommendation, decision_status, ticker, shares: currentShares, current_price } = position;

  if (!recommendation || (recommendation.signal !== "Buy" && recommendation.signal !== "Sell")) {
    return null;
  }

  const signal = recommendation.signal as "Buy" | "Sell";

  if (decision_status) {
    const badgeColor = decision_status.action === "accepted"
      ? "border-green-500 text-green-400"
      : "border-gray-600 text-gray-400";
    const label = decision_status.action === "accepted"
      ? `ACCEPTED ${decision_status.shares} shares`
      : "DECLINED";
    return (
      <div className="mt-2 pt-2 border-t border-gray-800">
        <span className={`inline-block px-2 py-0.5 border rounded text-xs font-mono ${badgeColor}`}>
          {label}
        </span>
      </div>
    );
  }

  return <TradeForm
    signal={signal}
    ticker={ticker}
    defaultShares={recommendation.shares_to_trade}
    currentShares={currentShares}
    currentPrice={current_price ?? 0}
    cashBalance={cashBalance}
    onTrade={onTrade}
    submitting={submitting}
  />;
}

interface FormProps {
  signal: "Buy" | "Sell";
  ticker: string;
  defaultShares: number;
  currentShares: number;
  currentPrice: number;
  cashBalance: number;
  onTrade: (request: TradeRequest) => Promise<void>;
  submitting: boolean;
}

function TradeForm({ signal, ticker, defaultShares, currentShares, currentPrice, cashBalance, onTrade, submitting }: FormProps) {
  const [shares, setShares] = useState(defaultShares);
  const [validationError, setValidationError] = useState<string | null>(null);

  const cost = shares * currentPrice;
  const isInvalid = signal === "Buy"
    ? cost > cashBalance
    : shares > currentShares;

  const handleAccept = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (isInvalid) {
      setValidationError(
        signal === "Buy"
          ? `Cost $${cost.toFixed(2)} exceeds cash $${cashBalance.toFixed(2)}`
          : `Cannot sell ${shares} shares, only hold ${currentShares}`
      );
      return;
    }
    setValidationError(null);
    onTrade({ ticker, action: "accepted", shares, signal });
  };

  const handleDecline = (e: React.MouseEvent) => {
    e.stopPropagation();
    setValidationError(null);
    onTrade({ ticker, action: "declined", shares, signal });
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    e.stopPropagation();
    const val = parseFloat(e.target.value);
    if (!isNaN(val) && val > 0) {
      setShares(val);
      setValidationError(null);
    }
  };

  const signalColor = signal === "Buy" ? "text-green-400" : "text-red-400";
  const acceptBorder = signal === "Buy" ? "border-green-600 hover:border-green-400 hover:text-green-300" : "border-red-600 hover:border-red-400 hover:text-red-300";
  const acceptText = signal === "Buy" ? "text-green-400" : "text-red-400";

  return (
    <div className="mt-2 pt-2 border-t border-gray-800" onClick={(e) => e.stopPropagation()}>
      <div className="flex items-center gap-3 flex-wrap">
        <span className={`text-xs font-mono font-bold ${signalColor}`}>
          {signal.toUpperCase()}
        </span>
        <div className="flex items-center gap-1">
          <input
            type="number"
            value={shares}
            onChange={handleInputChange}
            onClick={(e) => e.stopPropagation()}
            step="0.1"
            min="0.1"
            className="w-20 bg-[#0d1117] border border-gray-700 rounded px-2 py-0.5 text-xs font-mono text-gray-200 focus:border-blue-500 focus:outline-none"
          />
          <span className="text-xs text-gray-500 font-mono">shares</span>
          {currentPrice > 0 && (
            <span className="text-xs text-gray-600 font-mono ml-1">
              (${cost.toFixed(2)})
            </span>
          )}
        </div>
        <button
          type="button"
          onClick={handleAccept}
          disabled={submitting}
          className={`px-2 py-0.5 border rounded text-xs font-mono ${acceptText} ${acceptBorder} transition-colors disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer`}
        >
          {submitting ? "..." : "ACCEPT"}
        </button>
        <button
          type="button"
          onClick={handleDecline}
          disabled={submitting}
          className="px-2 py-0.5 border border-gray-700 rounded text-xs font-mono text-gray-400 hover:border-gray-500 hover:text-gray-300 transition-colors disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
        >
          DECLINE
        </button>
      </div>
      {validationError && (
        <div className="text-red-400 text-xs font-mono mt-1">{validationError}</div>
      )}
    </div>
  );
}
