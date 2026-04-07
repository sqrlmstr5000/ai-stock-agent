import pytest
from unittest.mock import patch, MagicMock
from providers.fred import FredProvider


@pytest.fixture
def fred_provider():
    provider = FredProvider(api_key="DUMMY")
    return provider

def make_obs(values, start_date="2024-01-01"):
    # Helper to create FRED-style observations
    return [
        {"date": f"2024-01-{i+1:02d}", "value": v} for i, v in enumerate(values)
    ]

def test_get_series_trend_basic(fred_provider):
    # Patch get_bulk_economic_data to return controlled data
    with patch.object(fred_provider, 'get_bulk_economic_data') as mock_bulk:
        mock_bulk.return_value = {
            'gdp': { 'observations': make_obs([1, 2, 3, 4, 5]) },
            'cpi': { 'observations': make_obs([10, 10, 10, 10, 10]) },
            'unemployment': { 'observations': make_obs([5, 4, 3, 2, 1]) },
            'vix': { 'observations': make_obs(['.', None, '', 7, 8]) },
            'empty': { 'observations': [] },
        }
        trends = fred_provider.get_series_trend("2024-01-01", "2024-01-05")
        # GDP: increasing
        assert trends['gdp']['series_start_value'] == 1
        assert trends['gdp']['series_end_value'] == 5
        assert trends['gdp']['trend'] == 5/1
        assert trends['gdp']['rate_of_change'] == 4/1
        # CPI: flat
        assert trends['cpi']['trend'] == 1.0
        assert trends['cpi']['std_dev'] == 0.0
        # Unemployment: decreasing
        assert trends['unemployment']['series_start_value'] == 5
        assert trends['unemployment']['series_end_value'] == 1
        # VIX: skips missing, only 7 and 8
        assert trends['vix']['series_start_value'] == 7
        assert trends['vix']['series_end_value'] == 8
        # Empty: all None
        assert trends['empty']['series_start_value'] is None
        assert trends['empty']['trend'] is None

def test_get_series_trend_single_value(fred_provider):
    with patch.object(fred_provider, 'get_bulk_economic_data') as mock_bulk:
        mock_bulk.return_value = {
            'gdp': { 'observations': make_obs([42]) },
        }
        trends = fred_provider.get_series_trend()
        assert trends['gdp']['series_start_value'] == 42
        assert trends['gdp']['series_end_value'] == 42
        assert trends['gdp']['std_dev'] == 0.0
        assert trends['gdp']['trend'] == 1.0
        assert trends['gdp']['rate_of_change'] == 0.0

def test_get_series_trend_all_missing(fred_provider):
    with patch.object(fred_provider, 'get_bulk_economic_data') as mock_bulk:
        mock_bulk.return_value = {
            'gdp': { 'observations': make_obs(['.', None, '']) },
        }
        trends = fred_provider.get_series_trend()
        assert trends['gdp']['series_start_value'] is None
        assert trends['gdp']['trend'] is None
