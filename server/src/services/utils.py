import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple

def calculate_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
    """Calculate RSI indicator"""
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_yoy_growth(current_value: Optional[float], previous_value: Optional[float]) -> Optional[float]:
    """Calculate year-over-year growth rate, rounded to 1 decimal place"""
    if current_value is None or previous_value is None or previous_value == 0:
        return None
    return round(((current_value - previous_value) / abs(previous_value)) * 100, 2)

# Helper to match by fiscalDateEnding
def find_by_date(reports, date_key):
    for r in reports:
        if r.get("fiscalDateEnding") == date_key:
            return r
    return None

def safe_float(value) -> Optional[float]:
    """Safely convert a value to float, handling None and "None" cases"""
    if value is None or value == "None" or value == "":
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None