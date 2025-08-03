from abc import ABC, abstractmethod

class MarketDataProvider(ABC):
    @abstractmethod
    def get_technical_indicators(self):
        pass

    @abstractmethod
    def get_dividend_history(self):
        pass

    @abstractmethod
    def get_earnings_history(self):
        pass

    @abstractmethod
    def get_market_data(self):
        pass

    @abstractmethod
    def get_news(self):
        pass
