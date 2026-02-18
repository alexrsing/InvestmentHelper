import PageContainer from '../components/layout/PageContainer';
import PortfolioSummaryCard from '../components/portfolio/PortfolioSummaryCard';
import AllocationChart from '../components/portfolio/AllocationChart';
import PerformanceCard from '../components/portfolio/PerformanceCard';
import HoldingsTable from '../components/portfolio/HoldingsTable';
import LoadingSpinner from '../components/common/LoadingSpinner';
import ErrorAlert from '../components/common/ErrorAlert';
import { usePortfolio } from '../hooks/usePortfolio';

export default function PortfolioOverview() {
  const { portfolio, loading, error, setError } = usePortfolio();

  if (loading) return <LoadingSpinner message="Loading portfolio..." />;

  return (
    <PageContainer title="Portfolio Overview">
      {error && <ErrorAlert message={error} onDismiss={() => setError(null)} />}

      {portfolio && (
        <div className="flex flex-col gap-6">
          <PortfolioSummaryCard summary={portfolio.summary} />

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <AllocationChart data={portfolio.allocation} />
            <PerformanceCard periods={portfolio.performance} />
          </div>

          <HoldingsTable holdings={portfolio.holdings} />
        </div>
      )}
    </PageContainer>
  );
}
