import type { ETFPosition } from "../../types";
import RiskBar from "./RiskBar";

interface Props {
  position: ETFPosition;
  onClick: (ticker: string) => void;
  totalValue: number;
  maxPositionPct: number | null;
  minPositionPct: number | null;
}

function getRecommendationColor(rec: string): string {
  switch (rec) {
    case "Buy": return "text-green-400";
    case "Sell": return "text-red-400";
    case "Hold": return "text-yellow-400";
    case "Stay": return "text-blue-400";
    default: return "text-gray-400";
  }
}

function getSentimentColor(sentiment: string): string {
  switch (sentiment) {
    case "Bullish": return "text-green-400";
    case "Bearish": return "text-red-400";
    case "Neutral": return "text-yellow-400";
    default: return "text-gray-400";
  }
}

function formatResearchAge(researched_at: string): string {
  const diffMs = Date.now() - new Date(researched_at).getTime();
  const hours = Math.floor(diffMs / (1000 * 60 * 60));
  if (hours < 1) return "just now";
  if (hours === 1) return "1h ago";
  return `${hours}h ago`;
}

export default function ETFRow({ position, onClick, totalValue, maxPositionPct, minPositionPct }: Props) {
  const {
    ticker,
    name,
    current_price,
    open_price,
    risk_range_low,
    risk_range_high,
    recommendation,
    research,
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

  const positionValue =
    current_price != null ? position.shares * current_price : null;

  const positionWeight =
    positionValue != null && totalValue > 0
      ? (positionValue / totalValue) * 100
      : null;

  const isMaxSize =
    positionWeight != null &&
    maxPositionPct != null &&
    positionWeight >= maxPositionPct;

  const isMinSize =
    positionWeight != null &&
    minPositionPct != null &&
    minPositionPct > 0 &&
    positionWeight < minPositionPct;

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
          <div>
            <div className="text-xs text-gray-500 uppercase">Shares</div>
            <div className="font-mono text-gray-300">
              {position.shares}
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500 uppercase">Value</div>
            <div className="font-mono text-gray-300">
              {positionValue != null ? fmt(positionValue) : "—"}
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500 uppercase">Weight</div>
            <div className={`font-mono ${isMaxSize ? "text-yellow-400" : isMinSize ? "text-orange-400" : "text-gray-300"}`}>
              {positionWeight != null ? `${positionWeight.toFixed(1)}%` : "—"}
            </div>
          </div>
        </div>

        {/* Risk Bar */}
        <div className="md:w-48 shrink-0">
          <div className="text-xs uppercase mb-1">
            <span className="text-gray-500">Penetration</span>
            {recommendation && (
              <span className={`${getRecommendationColor(recommendation.signal)} font-bold`}>
                {" · "}{recommendation.signal}
                {recommendation.shares_to_trade > 0 && ` ${recommendation.shares_to_trade.toFixed(1)}`}
              </span>
            )}
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
      {research && (
        <div className="mt-2 pt-2 border-t border-gray-800 text-xs">
          <span className={`${getSentimentColor(research.sentiment)} font-bold`}>
            {research.sentiment}
          </span>
          <span className="text-gray-400">
            {" · "}{research.summary}
          </span>
          <span className="text-gray-600 ml-2">
            {formatResearchAge(research.researched_at)}
          </span>
        </div>
      )}
    </button>
  );
}
