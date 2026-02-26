from typing import List, Tuple


class SymbolMappingService:
    def __init__(self):
        self.symbol_mapping = {
            "index_proxies": {"COMPQ": "QQQ", "SPX": "SPY", "RUT": "IWM"},
            "currency_proxies": {"USD/YEN": "FXY", "EUR/USD": "FXE", "GBP/USD": "FXB"},
            "commodity_proxies": {"GOLD": ["GLD", "AAAU"], "WTIC": "USO", "NATGAS": "UNG"},
            "direct_stocks": {"MSFT": "MSFT", "AMZN": "AMZN", "TSLA": ["TSLA", "TSLP"]},
            "cryptocurrency_proxies": {"ETH/USD": ["ETHE", "ETHW"], "BITCOIN": "IBIT"},
        }

    def map_symbol(self, symbol: str) -> str:
        """
        Map a symbol to its tradable equivalent

        Args:
            symbol: The symbol to map

        Returns:
            The mapped symbol or the original symbol if no mapping exists
        """
        # Check all mapping categories
        for category, mappings in self.symbol_mapping.items():
            if symbol in mappings:
                mapping = mappings[symbol]
                # Handle both single strings and lists
                if isinstance(mapping, list):
                    return mapping[0]  # Return first option
                else:
                    return mapping

        # If no mapping found, return the original symbol
        # This handles ETF symbols that don't need mapping
        return symbol

    def get_all_mapped_symbols(self, source_symbol: str) -> List[str]:
        """
        Get all mapped symbols for a source symbol

        Args:
            source_symbol: The source symbol

        Returns:
            List of all mapped symbols (empty if no mapping exists)
        """
        for category, mappings in self.symbol_mapping.items():
            if source_symbol in mappings:
                mapping = mappings[source_symbol]
                if isinstance(mapping, list):
                    return mapping
                else:
                    return [mapping]
        return []

    def has_mapping(self, symbol: str) -> bool:
        """
        Check if a symbol has a mapping

        Args:
            symbol: The symbol to check

        Returns:
            True if the symbol has a mapping
        """
        for category, mappings in self.symbol_mapping.items():
            if symbol in mappings:
                return True
        return False

    def get_source_and_target(self, symbol: str) -> Tuple[str, List[str]]:
        """
        Get the source symbol and all target symbols

        Args:
            symbol: The symbol (could be source or already mapped)

        Returns:
            Tuple of (source_symbol, [target_symbols])
        """
        # Check if this symbol has mappings (it's a source)
        mapped_symbols = self.get_all_mapped_symbols(symbol)
        if mapped_symbols:
            return (symbol, mapped_symbols)

        # Otherwise return as-is
        return (symbol, [symbol])
