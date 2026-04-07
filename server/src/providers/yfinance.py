
import os
import asyncio
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Annotated
from typing_extensions import TypedDict
import json
from utils.logging import setup_logger
from utils.financial import calculate_rsi, calculate_macd, calculate_bollinger_bands, calculate_obv, calculate_atr
from base.market_data_provider import MarketDataProvider
from models.marketdata import (
    TechnicalIndicators,
    DividendHistory,
    EarningsHistory,
    Earning,
    MarketData,
    News,
    NewsItem,
)
from utils.financial import market_open

logger = setup_logger(__name__)

class YFinanceProvider(MarketDataProvider):
    def __init__(self):
        pass

    @staticmethod
    def _get_interval(period: str) -> str:
        """
        Return the appropriate interval for a given period.

        Valid period: '1d', '5d', '1mo', '3mo', '6mo', '1y', '2y', '5y', '10y', 'ytd', 'max'

        Valid intervals: 1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 4h, 1d, 5d, 1wk, 1mo, 3mo
        """
        if period == '1d':
            return '1h'
        elif period == '5d':
            return '5m'
        elif period == '1y':
            return '1wk'
        return '1d'

    def get_stock_history_by_symbols(self, symbols: List[str], period: str, interval: Optional[str] = None) -> pd.DataFrame:
        """Fetch historical stock data for multiple symbols and period using yf.download. Allows specifying interval."""
        if interval is None:
            interval = self._get_interval(period)
        if market_open():
            logger.warning("***MARKET OPEN***: Data is from previous close.")
        hist = yf.download(symbols, period=period, interval=interval)
        logger.debug(f"yfinance multi-symbol hist: {hist.to_json(indent=2, date_format='iso')}")
        return hist
    
    async def get_stock_history_by_symbols_async(self, symbols: List[str], period: str, interval: Optional[str] = None) -> pd.DataFrame:
        """Async version: Fetch historical stock data for multiple symbols and period using yf.download in a thread."""
        if interval is None:
            interval = self._get_interval(period)
        if market_open():
            logger.warning("***MARKET OPEN***: Data is from previous close.")
        hist = await asyncio.to_thread(yf.download, symbols, period=period, interval=interval)
        logger.debug(f"yfinance multi-symbol hist: {hist.to_json(indent=2, date_format='iso')}")
        return hist
      
    def _get_stock_history(self, symbol: str, period: str, interval: Optional[str] = None) -> pd.DataFrame:
        """Fetch historical stock data for the symbol and period. Allows specifying interval."""
        if interval is None:
            interval = self._get_interval(period)
        if market_open():
            logger.warning("***MARKET OPEN***: Data is from previous close.")
        stock = yf.Ticker(symbol)
        hist = stock.history(period=period, interval=interval)
        logger.debug(f"yfinance hist: {hist.to_json(indent=2, date_format='iso')}")
        return hist

    def get_technical_indicators(self, symbol: str, period: str) -> Optional[TechnicalIndicators]:
        hist = self._get_stock_history(symbol, period)
        # Return None if no close data
        if hist.empty or 'Close' not in hist or hist['Close'].isna().all():
            logger.warning(f"No historical close data for {symbol} with period '{period}'")
            return None

        # Calculate indicators
        sma_20 = hist['Close'].rolling(window=20).mean()
        sma_50 = hist['Close'].rolling(window=50).mean()
        sma_200 = hist['Close'].rolling(window=200).mean()
        rsi = calculate_rsi(hist['Close'])
        macd_data = calculate_macd(hist['Close'])
        bb_data = calculate_bollinger_bands(hist['Close'])
        obv = calculate_obv(hist['Close'], hist['Volume'])
        atr = calculate_atr(hist['High'], hist['Low'], hist['Close'])

        # Prepare OHLCV data in the desired format, similar to Alpha Vantage
        ohlcv_df = hist[['Open', 'High', 'Low', 'Close', 'Volume']].copy()

        # Format values as strings
        for col in ['Open', 'High', 'Low', 'Close']:
            ohlcv_df[col] = ohlcv_df[col].map('{:.4f}'.format)
        ohlcv_df['Volume'] = ohlcv_df['Volume'].astype(int).astype(str)

        # Format index to string 'YYYY-MM-DD HH:MM:SS'
        ohlcv_df.index = ohlcv_df.index.strftime('%Y-%m-%d %H:%M:%S')
        ohlcv_data = ohlcv_df.to_dict(orient='index')

        window = min(20, len(hist['Volume']))
        # volume_trend compares the average volume of the last 5 periods to the average of the last 20 periods (or all available if less than 20)
        volume_trend = float(hist['Volume'].iloc[-5:].mean() / hist['Volume'].iloc[-window:].mean()) if window > 0 and hist['Volume'].iloc[-window:].mean() != 0 else 0.0
        data = {
            'current_price': float(hist['Close'].iloc[-1]),
            'current_volume': int(hist['Volume'].iloc[-1]),
            'sma_20': float(sma_20.iloc[-1]),
            'sma_50': float(sma_50.iloc[-1]),
            'sma_200': float(sma_200.iloc[-1]),
            'rsi': float(rsi.iloc[-1]),
            'volume_trend': volume_trend,
            'macd': macd_data['macd'],
            'macd_signal': macd_data['macd_signal'],
            'macd_hist': macd_data['macd_hist'],
            'bb_upper': bb_data['bb_upper'],
            'bb_middle': bb_data['bb_middle'],
            'bb_lower': bb_data['bb_lower'],
            'obv': obv,
            'atr': atr,
            'ohlcv': ohlcv_data
        }
        logger.info("yfinance technical data:")
        logger.info(f"{json.dumps(data, indent=2)}")
        return TechnicalIndicators(**data)

    def get_dividend_history(self, symbol: str) -> DividendHistory:
        stock = yf.Ticker(symbol)
        div = stock.dividends
        logger.debug(f"yfinance dividends: {div.to_json(indent=2, date_format='iso')}")

        div.index = div.index.strftime('%Y-%m-%d')
        return DividendHistory(dividends=div.to_dict())

    def get_earnings_history(self, symbol: str) -> EarningsHistory:
        stock = yf.Ticker(symbol)
        income = stock.income_stmt
        logger.debug(f"yfinance earnings: {income.to_json(indent=2, date_format='iso')}")

        income_t = income.transpose()
        earnings_history = []
        for date, row in income_t.iterrows():
            earnings_history.append(Earning(
                date=date.strftime('%Y-%m-%d'),
                diluted_eps=row.get("Diluted EPS"),
                basic_eps=row.get("Basic EPS"),
                net_income=row.get("Net Income"),
                net_income_common_stockholders=row.get("Net Income Common Stockholders"),
                net_income_continuous_operations=row.get("Net Income Continuous Operations"),
                total_operating_income_as_reported=row.get("Total Operating Income As Reported"),
                operating_income=row.get("Operating Income"),
                gross_profit=row.get("Gross Profit"),
                total_revenue=row.get("Total Revenue"),
                operating_revenue=row.get("Operating Revenue"),
            ))
        logger.info("yfinance income_stmt data:")
        logger.info(f"{json.dumps(earnings_history, indent=2)}")
        return EarningsHistory(earnings=earnings_history)

    def get_market_data(self, symbol: str) -> MarketData:
        stock = yf.Ticker(symbol)
        info = stock.info

        logger.debug(f"yfinance info: {json.dumps(info, indent=2)}")
        data = {
            'sector': info.get('sector', 'Unknown'),
            'industry': info.get('industry', 'Unknown'),
            'market_cap': info.get('marketCap', 0),
            'beta': info.get('beta', 1.0),
            'pe_ratio': info.get('trailingPE', 0),
            'dividend_yield': info.get('dividendYield', 0),
            'divident_rate': info.get('dividendRate', 0),
            'trailing_eps': info.get('trailingEps', 0),
            'forward_pe': info.get('forwardPE', 0),
            'forward_eps': info.get('forwardEps', 0),
            'peg_ratio': info.get('pegRatio', 0),
            'price_to_book': info.get('priceToBook', 0),
            'price_to_sales': info.get('priceToSalesTrailing12Months', 0),
            'enterprise_value': info.get('enterpriseValue', 0),
            'current_ratio': info.get('currentRatio', 0),
            'quick_ratio': info.get('quickRatio', 0),
            'debt_to_equity': info.get('debtToEquity', 0),
            'revenue_growth': info.get('revenueGrowth', 0),
            'profit_margin': info.get('profitMargins', 0),
            'operating_margin': info.get('operatingMargins', 0),
            'return_on_assets': info.get('returnOnAssets', 0),
            'return_on_equity': info.get('returnOnEquity', 0),
            'revenue_per_share': info.get('revenuePerShare', 0),
            'gross_profit_margin': info.get('grossProfits', 0),
            'operating_cash_flow': info.get('operatingCashflow', 0),
            'free_cash_flow': info.get('freeCashflow', 0),
        }
        logger.info("yfinance market data:")
        logger.info(f"{json.dumps(data, indent=2)}")
        return MarketData(**data)

    def get_news(self, symbol: str) -> News:
        stock = yf.Ticker(symbol)
        raw_news = stock.news
        logger.debug(f"yfinance news: {json.dumps(raw_news, indent=2)}")
        logger.info(f"yfinance returned {len(raw_news)} news items for {symbol}.")
        news = raw_news[:10]  # Last x news items

        news_data = []
        for item in news:
            content = item.get('content', {})
            news_data.append(NewsItem(
                title=content.get('title', ''),
                publisher=content.get('publisher', ''),
                url=content.get('canonicalUrl', {}).get('url', ''),
                timestamp=content.get('pubDate', '')
            ))

        logger.info("yfinance news data:")
        logger.info(f"{json.dumps([item.model_dump() for item in news_data], indent=2)}")
        return News(news=news_data)
