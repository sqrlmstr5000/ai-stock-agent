import dotenv
dotenv.load_dotenv(dotenv_path='../../../.env', override=True)

import os
import pytest
import asyncio
from unittest.mock import patch, MagicMock
import sys
import types
from app import StockAnalysisApp
from graphs import fundamental

# Use a test symbol
TEST_SYMBOL = "AAPL"


# Fake API data for providers
FAKE_MARKET_DATA = MagicMock()
FAKE_MARKET_DATA.model_dump.return_value = {"price": 150, "volume": 1000000}
FAKE_EARNINGS_HISTORY = MagicMock()
FAKE_EARNINGS_HISTORY.model_dump.return_value = {"eps": 5.0, "revenue": 100000000}
FAKE_DIVIDEND_HISTORY = MagicMock()
FAKE_DIVIDEND_HISTORY.model_dump.return_value = {"dividends": [1.0, 1.1, 1.2]}
FAKE_NEWS_DATA = MagicMock()
FAKE_NEWS_DATA.model_dump.return_value = {"headlines": ["Apple launches new product"]}

# Create mock providers to inject into FundamentalGraph
MOCK_YFINANCE = MagicMock()
MOCK_YFINANCE.get_dividend_history.return_value = FAKE_DIVIDEND_HISTORY
MOCK_YFINANCE.get_news.return_value = FAKE_NEWS_DATA
# Patch get_technical_indicators to return a serializable mock
FAKE_TECHNICAL_DATA = MagicMock()
FAKE_TECHNICAL_DATA.model_dump.return_value = {
	"current_price": 150,
	"sma_20": 148,
	"sma_50": 145,
	"sma_200": 140,
	"rsi": 55,
	"volume": 1000000,
	# ... add any other fields your prompt expects ...
}
MOCK_YFINANCE.get_technical_indicators.return_value = FAKE_TECHNICAL_DATA
MOCK_ALPHAVANTAGE = MagicMock()
MOCK_ALPHAVANTAGE.get_market_data.return_value = (FAKE_MARKET_DATA, 1)
MOCK_ALPHAVANTAGE.get_earnings_history.return_value = (FAKE_EARNINGS_HISTORY, 1)

@pytest.mark.asyncio
async def test_analyze_stock_integration(monkeypatch):
	"""
	Integration test for StockAnalysisApp.analyze_stock using fake provider data and live Gemini API.
	Ensures DatabaseManager is patched to avoid real DB connections.
	"""
	# Patch DatabaseManager to avoid real DB init
	from services import database
	monkeypatch.setattr(database, "DatabaseManager", MagicMock())

	# Patch FundamentalGraph __init__ to inject our mock providers
	original_fg_init = fundamental.FundamentalGraph.__init__
	def mock_fg_init(self, llm, yfinance_provider=None, alphavantage_provider=None):
		# Call the real __init__ with our mocks
		original_fg_init(self, llm, MOCK_YFINANCE, MOCK_ALPHAVANTAGE)
	monkeypatch.setattr(fundamental.FundamentalGraph, "__init__", mock_fg_init)

	# Re-import app to ensure patched DatabaseManager and FundamentalGraph are used
	if "app" in sys.modules:
		import importlib
		importlib.reload(sys.modules["app"])
	from app import StockAnalysisApp
	app = StockAnalysisApp()

	# Patch db_manager to avoid DB writes
	monkeypatch.setattr(app, "db_manager", MagicMock())
	app.db_manager.get_stock_by_symbol.return_value = MagicMock(symbol=TEST_SYMBOL, id=1)
	app.db_manager.create_research.return_value = MagicMock()
	app.db_manager.create_historical_values.return_value = MagicMock()

	# Patch save_usage_metadata to a MagicMock to avoid side effects
	monkeypatch.setattr(app, "save_usage_metadata", MagicMock())

	# Run the analysis
	result = await app.analyze_stock(TEST_SYMBOL)

	# Check result structure
	assert "message" in result
	assert result["message"] == "Analysis completed successfully"
	assert "data" in result
	assert isinstance(result["data"], dict)
	# Check that some expected keys are present in structured output
	# (keys depend on your HistoricalTrackedValues schema)
	# Example:
	# assert "final_recommendation" in result["data"]



# Integration test for _compare_historical_values and email trigger (fixed for Peewee Proxy)
@pytest.mark.asyncio
async def test_compare_historical_values_and_email(monkeypatch):
	"""
	Integration test for _compare_historical_values by calling analyze_stock and sending an actual email.
	Avoids Peewee Proxy error by patching all model/database access.
	"""
	# Patch DatabaseManager and all model/database access before importing app
	from services import database
	monkeypatch.setattr(database, "DatabaseManager", MagicMock())

	# Patch FundamentalGraph __init__ to inject our mock providers
	original_fg_init = fundamental.FundamentalGraph.__init__
	def mock_fg_init(self, llm, yfinance_provider=None, alphavantage_provider=None):
		original_fg_init(self, llm, MOCK_YFINANCE, MOCK_ALPHAVANTAGE)
	monkeypatch.setattr(fundamental.FundamentalGraph, "__init__", mock_fg_init)

	if "app" in sys.modules:
		import importlib
		importlib.reload(sys.modules["app"])
	from app import StockAnalysisApp
	app = StockAnalysisApp()

	# Patch db_manager to avoid DB writes and all model methods used by _compare_historical_values
	db_manager_mock = MagicMock()
	db_manager_mock.get_stock_by_symbol.return_value = MagicMock(symbol=TEST_SYMBOL, id=1)
	db_manager_mock.create_historical_values.return_value = MagicMock()
	def get_latest_historical_values_side_effect(*args, **kwargs):
		if not hasattr(get_latest_historical_values_side_effect, "call_count"):
			get_latest_historical_values_side_effect.call_count = 0
		get_latest_historical_values_side_effect.call_count += 1
		if get_latest_historical_values_side_effect.call_count == 1:
			return MagicMock(final_recommendation="Buy", created_at="2025-09-15 10:00", current_price=150, low_price_target=140, high_price_target=160, price_target_percent=5)
		elif get_latest_historical_values_side_effect.call_count == 2:
			return MagicMock(final_recommendation="Hold", created_at="2025-09-10 10:00", current_price=145, low_price_target=135, high_price_target=155, price_target_percent=3)
		else:
			return MagicMock(final_recommendation="Hold", created_at="2025-09-01 10:00", current_price=140, low_price_target=130, high_price_target=150, price_target_percent=2)
	db_manager_mock.get_latest_historical_values.side_effect = get_latest_historical_values_side_effect
	monkeypatch.setattr(app, "db_manager", db_manager_mock)

	# Patch save_usage_metadata to avoid side effects
	monkeypatch.setattr(app, "save_usage_metadata", MagicMock())

	# Patch any model methods used by _compare_historical_values if needed


	# Patch fundamental_graph.analyze_stock to avoid LLM usage
	mock_graph_result = {
		"results": {
			"structured_data": {
				"final_recommendation": "Buy",
				"high_price_target": 160,
				"low_price_target": 140,
				"price_target_percent": 5
			}
		},
		"usage": {}
	}
	import types

	async def mock_analyze_stock_async(*args, **kwargs):
		return mock_graph_result
	app.fundamental_graph.analyze_stock = mock_analyze_stock_async

	# Run the analysis to create historical values
	await app.analyze_stock(TEST_SYMBOL)

	stock_obj = app.db_manager.get_stock_by_symbol(TEST_SYMBOL)
	html_report = app._compare_historical_values(stock_obj)
	assert html_report is not None
	assert "Buy" in html_report or "Hold" in html_report

	# Actually send the email
	from utils import email as email_utils
	subject = f"Stock Analysis Comparison for {TEST_SYMBOL}"
	recipient = os.getenv("TEST_EMAIL_RECIPIENT")
	assert recipient, "TEST_EMAIL_RECIPIENT must be set in environment for this test."
	email_utils.send_via_gmail(recipient, subject, html_report)
