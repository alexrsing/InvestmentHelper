import PageContainer from '../components/layout/PageContainer';
import ETFSearchBar from '../components/trading/ETFSearchBar';
import ETFDetailCard from '../components/trading/ETFDetailCard';
import RiskRangeSparkline from '../components/trading/RiskRangeSparkline';
import PriceHistoryTable from '../components/trading/PriceHistoryTable';
import LoadingSpinner from '../components/common/LoadingSpinner';
import ErrorAlert from '../components/common/ErrorAlert';
import { useETF } from '../hooks/useETF';
import { useETFHistory } from '../hooks/useETFHistory';

export default function Trading() {
  const { etf, loading: etfLoading, error: etfError, fetchETF, clear: clearETF } = useETF();
  const {
    history,
    loading: historyLoading,
    error: historyError,
    fetchHistory,
    clear: clearHistory,
  } = useETFHistory();

  const handleSearch = (ticker: string) => {
    clearETF();
    clearHistory();
    fetchETF(ticker);
    fetchHistory(ticker);
  };

  const loading = etfLoading || historyLoading;
  const error = etfError || historyError;

  return (
    <PageContainer title="Trading">
      <div className="flex flex-col gap-6">
        <ETFSearchBar onSearch={handleSearch} loading={loading} />

        {error && <ErrorAlert message={error} />}

        {loading && <LoadingSpinner message="Fetching ETF data..." />}

        {etf && !etfLoading && (
          <>
            <ETFDetailCard etf={etf} />

            {!historyLoading && history.length >= 2 && (
              <RiskRangeSparkline history={history} ticker={etf.ticker} />
            )}

            {!historyLoading && history.length > 0 && (
              <PriceHistoryTable history={history} />
            )}
          </>
        )}

        {!etf && !loading && !error && (
          <div className="text-center py-16 text-gray-400">
            <p className="text-lg">Search for an ETF ticker to get started</p>
            <p className="text-sm mt-2">Try SPY, QQQ, or VOO</p>
          </div>
        )}
      </div>
    </PageContainer>
  );
}
