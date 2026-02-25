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
