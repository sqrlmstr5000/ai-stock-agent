import pytest
import json
from providers.edgar import EdgarProvider
import pandas as pd

def test_get_insider_trading_data_print():
    provider = EdgarProvider()
    symbol = "LLY"  # Use a real symbol for testing
    data = provider.get_insider_trading_summary(symbol=symbol, days=30)
    print("InsiderTradingData Summary:")
    print(data)

def test_get_institutional_holdings_data_print():
    provider = EdgarProvider()
    symbol = "VFIAX"  # Use a real symbol for testing
    df = provider.get_institutional_holdings_data(symbol=symbol, days=180)
    print("InstitutionalHoldingsData DataFrame:")
    print(df)

def test_get_etf_holdings_print():
    provider = EdgarProvider()
    symbol = "VFIAX"  # Example ETF symbol, replace with a real ETF if needed
    df = provider.get_etf_holdings(symbol=symbol)
    print("ETF Holdings DataFrame:")
    print(df)


