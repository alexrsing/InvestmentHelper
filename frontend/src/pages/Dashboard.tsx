import { useState, useRef } from "react";
import { useAuth } from "@clerk/clerk-react";
import Navbar from "../components/layout/Navbar";
import PortfolioSummary from "../components/portfolio/PortfolioSummary";
import CashManager from "../components/portfolio/CashManager";
import ETFList from "../components/etf/ETFList";
import ETFDetailModal from "../components/etf/ETFDetailModal";
import { usePortfolio } from "../hooks/usePortfolio";
import { useETFHistory } from "../hooks/useETFHistory";
import { useTradingRules } from "../hooks/useTradingRules";
import { useResearch } from "../hooks/useResearch";
import { useTrades } from "../hooks/useTrades";
import { apiUpload } from "../api/client";
import type { TradeRequest } from "../types";

export default function Dashboard() {
  const { getToken } = useAuth();
  const { data: portfolio, loading, error, refetch } = usePortfolio();
  const {
    data: historyData,
    loading: historyLoading,
    error: historyError,
    fetchHistory,
  } = useETFHistory();
  const { rules: tradingRules } = useTradingRules();
  const { researching, error: researchError, triggerResearch } = useResearch();
  const { submitTrade, submitting: submittingTicker } = useTrades();
  const [selectedTicker, setSelectedTicker] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleSelectETF = (ticker: string) => {
    setSelectedTicker(ticker);
    fetchHistory(ticker);
  };

  const handleCloseModal = () => {
    setSelectedTicker(null);
  };

  const handleUploadClick = () => {
    fileInputRef.current?.click();
  };

  const handleResearch = async () => {
    await triggerResearch();
    refetch();
  };

  const handleTrade = async (request: TradeRequest) => {
    await submitTrade(request);
    refetch();
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    setUploadError(null);
    try {
      await apiUpload("/api/v1/portfolio/upload", getToken, file);
      refetch();
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  return (
    <div className="min-h-screen bg-[#0d1117] text-gray-100">
      <Navbar />

      <main className="max-w-6xl mx-auto px-4 py-6">
        <div className="flex items-center justify-between mb-4">
          <h1 className="text-sm text-gray-500 uppercase tracking-wider font-mono">
            Portfolio
          </h1>
          <div className="flex items-center gap-3">
            {researchError && (
              <span className="text-red-400 text-xs font-mono">
                {researchError}
              </span>
            )}
            <button
              type="button"
              onClick={handleResearch}
              disabled={researching || loading}
              className="px-3 py-1.5 border border-gray-700 rounded text-xs font-mono text-gray-300 hover:text-blue-400 hover:border-blue-400 transition-colors disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
            >
              {researching ? "SEARCHING..." : "SEARCH FOR DATA"}
            </button>
            {uploadError && (
              <span className="text-red-400 text-xs font-mono">
                {uploadError}
              </span>
            )}
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv"
              onChange={handleFileChange}
              className="hidden"
            />
            <button
              type="button"
              onClick={handleUploadClick}
              disabled={uploading}
              className="px-3 py-1.5 border border-gray-700 rounded text-xs font-mono text-gray-300 hover:text-green-400 hover:border-green-400 transition-colors disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
            >
              {uploading ? "UPLOADING..." : "UPLOAD CSV"}
            </button>
          </div>
        </div>

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
            <CashManager onUpdate={refetch} />
            <div className="mb-3">
              <h2 className="text-sm text-gray-500 uppercase tracking-wider font-mono">
                Positions
              </h2>
            </div>
            <ETFList
              positions={portfolio.positions}
              onSelectETF={handleSelectETF}
              totalValue={portfolio.total_value}
              maxPositionPct={tradingRules?.max_position_pct ?? null}
              minPositionPct={tradingRules?.min_position_pct ?? null}
              cashBalance={portfolio.cash_balance}
              onTrade={handleTrade}
              submittingTicker={submittingTicker}
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
