"""Tests for SymbolMappingService."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from services.symbol_mapping_service import SymbolMappingService


class TestSymbolMappingService:
    """Test symbol mapping from index/commodity symbols to tradable ETFs."""

    def setup_method(self):
        self.service = SymbolMappingService()

    def test_index_proxy_spx_to_spy(self):
        assert self.service.map_symbol("SPX") == "SPY"

    def test_index_proxy_compq_to_qqq(self):
        assert self.service.map_symbol("COMPQ") == "QQQ"

    def test_index_proxy_rut_to_iwm(self):
        assert self.service.map_symbol("RUT") == "IWM"

    def test_passthrough_for_already_etf(self):
        """Symbols that are already ETF tickers pass through unchanged."""
        assert self.service.map_symbol("SPY") == "SPY"
        assert self.service.map_symbol("XLK") == "XLK"
        assert self.service.map_symbol("TLT") == "TLT"

    def test_commodity_proxies(self):
        assert self.service.map_symbol("GOLD") == "GLD"
        assert self.service.map_symbol("WTIC") == "USO"
        assert self.service.map_symbol("NATGAS") == "UNG"

    def test_currency_proxies(self):
        assert self.service.map_symbol("USD/YEN") == "FXY"
        assert self.service.map_symbol("EUR/USD") == "FXE"

    def test_cryptocurrency_proxies(self):
        assert self.service.map_symbol("BITCOIN") == "IBIT"

    def test_list_mapping_returns_first(self):
        """When mapping value is a list, map_symbol returns the first."""
        assert self.service.map_symbol("GOLD") == "GLD"  # ["GLD", "AAAU"]

    def test_get_all_mapped_symbols(self):
        result = self.service.get_all_mapped_symbols("GOLD")
        assert result == ["GLD", "AAAU"]

    def test_has_mapping(self):
        assert self.service.has_mapping("SPX") is True
        assert self.service.has_mapping("XLK") is False
