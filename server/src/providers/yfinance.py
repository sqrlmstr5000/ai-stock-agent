
import os
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Annotated
from typing_extensions import TypedDict
import json
from utils.logging import setup_logger
from services.utils import calculate_rsi
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

logger = setup_logger(__name__)

class YFinanceProvider(MarketDataProvider):
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.stock = yf.Ticker(symbol)

    def get_technical_indicators(self) -> TechnicalIndicators:
        # Fetch technical data
        hist = self.stock.history(period='1y')
        logger.debug(f"yfinance hist: {hist.to_json(indent=2, date_format='iso')}")

        # Calculate indicators
        sma_20 = hist['Close'].rolling(window=20).mean()
        sma_50 = hist['Close'].rolling(window=50).mean()
        sma_200 = hist['Close'].rolling(window=200).mean()
        rsi = calculate_rsi(hist['Close'])

        # Prepare OHLCV data in the desired format, similar to Alpha Vantage
        ohlcv_df = hist[['Open', 'High', 'Low', 'Close', 'Volume']].copy()

        # Format values as strings
        for col in ['Open', 'High', 'Low', 'Close']:
            ohlcv_df[col] = ohlcv_df[col].map('{:.4f}'.format)
        ohlcv_df['Volume'] = ohlcv_df['Volume'].astype(int).astype(str)

        # Format index to string 'YYYY-MM-DD'
        ohlcv_df.index = ohlcv_df.index.strftime('%Y-%m-%d')
        ohlcv_data = ohlcv_df.to_dict(orient='index')

        data = {
            'current_price': float(hist['Close'].iloc[-1]),
            'sma_20': float(sma_20.iloc[-1]),
            'sma_50': float(sma_50.iloc[-1]),
            'sma_200': float(sma_200.iloc[-1]),
            'rsi': float(rsi.iloc[-1]),
            'volume_trend': float(hist['Volume'].iloc[-5:].mean() / hist['Volume'].iloc[-20:].mean()),
            'ohlcv': ohlcv_data
        }
        logger.info("yfinance technical data:")
        logger.info(f"{json.dumps(data, indent=2)}")
        return TechnicalIndicators(**data)

    def get_dividend_history(self) -> DividendHistory:
        div = self.stock.dividends
        logger.debug(f"yfinance dividends: {div.to_json(indent=2, date_format='iso')}")

        div.index = div.index.strftime('%Y-%m-%d')
        return DividendHistory(dividends=div.to_dict())

    def get_earnings_history(self) -> EarningsHistory:
        income = self.stock.income_stmt
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

    def get_market_data(self) -> MarketData:
        # Fetch market data
        info = self.stock.info

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

    def get_news(self) -> News:
            # Fetch news
        raw_news = self.stock.news
        logger.debug(f"yfinance news: {json.dumps(raw_news, indent=2)}")
        logger.info(f"yfinance returned {len(raw_news)} news items for {self.symbol}.")
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
