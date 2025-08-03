import os
import requests
import math
from services.utils import safe_float

class FredProvider:
    BASE_URL = "https://api.stlouisfed.org/fred/series/observations"

    # FRED Series IDs for common US macro indicators
    SERIES = {
        "gdp": "GDP",
        "cpi": "CPIAUCSL",
        "unemployment": "UNRATE",
        "interest_rate": "FEDFUNDS",
        "consumer_confidence": "UMCSENT",
        "business_confidence": "NAPM",
        "retail_sales": "RSAFS",
        "industrial_production": "INDPRO",
        "vix": "VIXCLS",
        "yield_curve_10y_2y": "T10Y2Y",
        "housing_starts": "HOUST",
        "pmi": "NAPM",
    }

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("FRED_API_KEY")
        if not self.api_key:
            raise ValueError("FRED API key must be provided via argument or FRED_API_KEY env var.")

    def get_series(self, series_id: str, start_date: str = None, end_date: str = None):
        params = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json"
        }
        if start_date:
            params["observation_start"] = start_date
        if end_date:
            params["observation_end"] = end_date
        resp = requests.get(self.BASE_URL, params=params)
        resp.raise_for_status()
        return resp.json()

    def get_gdp(self, **kwargs):
        return self.get_series(self.SERIES["gdp"], **kwargs)

    def get_cpi(self, **kwargs):
        return self.get_series(self.SERIES["cpi"], **kwargs)

    def get_unemployment(self, **kwargs):
        return self.get_series(self.SERIES["unemployment"], **kwargs)

    def get_interest_rate(self, **kwargs):
        return self.get_series(self.SERIES["interest_rate"], **kwargs)

    def get_consumer_confidence(self, **kwargs):
        return self.get_series(self.SERIES["consumer_confidence"], **kwargs)

    def get_business_confidence(self, **kwargs):
        return self.get_series(self.SERIES["business_confidence"], **kwargs)

    def get_retail_sales(self, **kwargs):
        return self.get_series(self.SERIES["retail_sales"], **kwargs)

    def get_industrial_production(self, **kwargs):
        return self.get_series(self.SERIES["industrial_production"], **kwargs)

    def get_vix(self, **kwargs):
        return self.get_series(self.SERIES["vix"], **kwargs)

    def get_yield_curve(self, **kwargs):
        return self.get_series(self.SERIES["yield_curve_10y_2y"], **kwargs)

    def get_housing_starts(self, **kwargs):
        return self.get_series(self.SERIES["housing_starts"], **kwargs)

    def get_pmi(self, **kwargs):
        return self.get_series(self.SERIES["pmi"], **kwargs)

    def get_bulk_economic_data(self, start_date: str = None, end_date: str = None):
        """Fetch a bundle of key indicators for economic analysis."""
        return {
            "gdp": self.get_gdp(start_date=start_date, end_date=end_date),
            "cpi": self.get_cpi(start_date=start_date, end_date=end_date),
            "unemployment": self.get_unemployment(start_date=start_date, end_date=end_date),
            "interest_rate": self.get_interest_rate(start_date=start_date, end_date=end_date),
            "consumer_confidence": self.get_consumer_confidence(start_date=start_date, end_date=end_date),
            "business_confidence": self.get_business_confidence(start_date=start_date, end_date=end_date),
            "retail_sales": self.get_retail_sales(start_date=start_date, end_date=end_date),
            "industrial_production": self.get_industrial_production(start_date=start_date, end_date=end_date),
            "vix": self.get_vix(start_date=start_date, end_date=end_date),
            "yield_curve": self.get_yield_curve(start_date=start_date, end_date=end_date),
            "housing_starts": self.get_housing_starts(start_date=start_date, end_date=end_date),
            "pmi": self.get_pmi(start_date=start_date, end_date=end_date),
        }

    def get_series_trend(self, start_date: str = None, end_date: str = None):
        """Fetch bulk economic data and calculate summary stats for each series."""
        bulk_data = self.get_bulk_economic_data(start_date=start_date, end_date=end_date)
        trends = {}
        for key, series_data in bulk_data.items():
            # FRED API returns a dict with 'observations' key
            observations = series_data.get('observations', [])
            # Filter out missing values
            valid_obs = [obs for obs in observations if obs.get('value') not in (None, '.', '')]
            values = []
            dates = []
            for obs in valid_obs:
                v = safe_float(obs['value'])
                if v is not None:
                    values.append(v)
                    dates.append(obs['date'])
            if not values:
                trends[key] = {
                    'series_start_value': None,
                    'series_start_date': None,
                    'series_end_value': None,
                    'series_end_date': None,
                    'trend': None,
                    'rate_of_change': None,
                    'absolute_change': None,
                    'min_value': None,
                    'min_date': None,
                    'max_value': None,
                    'max_date': None,
                    'mean_value': None,
                    'std_dev': None
                }
                continue
            start_value = values[0]
            start_date = dates[0]
            end_value = values[-1]
            end_date = dates[-1]
            trend = end_value / start_value if start_value != 0 else None
            rate_of_change = (end_value - start_value) / start_value if start_value != 0 else None
            absolute_change = end_value - start_value
            min_value = min(values)
            max_value = max(values)
            min_index = values.index(min_value)
            max_index = values.index(max_value)
            min_date = dates[min_index]
            max_date = dates[max_index]
            mean_value = sum(values) / len(values) if values else None
            if len(values) > 1:
                mean = mean_value
                std_dev = math.sqrt(sum((v - mean) ** 2 for v in values) / (len(values) - 1))
            else:
                std_dev = 0.0
            trends[key] = {
                'series_start_value': start_value,
                'series_start_date': start_date,
                'series_end_value': end_value,
                'series_end_date': end_date,
                'trend': trend,
                'rate_of_change': rate_of_change,
                'absolute_change': absolute_change,
                'min_value': min_value,
                'min_date': min_date,
                'max_value': max_value,
                'max_date': max_date,
                'mean_value': mean_value,
                'std_dev': std_dev
            }
        return trends