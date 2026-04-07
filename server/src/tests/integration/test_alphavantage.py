import asyncio
import pytest
import json
from providers.alphavantage import AlphaVantageProvider


@pytest.mark.asyncio
async def test_get_earnings_history_print():
	provider = AlphaVantageProvider()
	# Use a real symbol, e.g., NVDA
	earnings_history, request_count = await provider.get_earnings_history('NVDA')
	print("EarningsHistory:", json.dumps(earnings_history.model_dump(), indent=2))
	print("Request count:", request_count)

"""
"annual_earnings": [
    {
      "date": "2025-01-31",
      "reported_eps": 2.992,
      "estimated_eps": null,
      "net_income": 72880000000.0,
      "net_income_continuous_operations": null,
      "operating_income": 81453000000.0,
      "gross_profit": 97858000000.0,
      "total_revenue": 130497000000.0,
      "cost_of_revenue": 32639000000.0,
      "cost_of_goods_and_services_sold": 32639000000.0,
      "selling_general_and_administrative": 3491000000.0,
      "research_and_development": 12914000000.0,
      "operating_expenses": 16405000000.0,
      "investment_income_net": null,
      "net_interest_income": 1539000000.0,
      "interest_income": 1786000000.0,
      "interest_expense": 247000000.0,
      "non_interest_income": null,
      "other_non_operating_income": null,
      "depreciation": null,
      "depreciation_and_amortization": 1864000000.0,
      "income_before_tax": 84026000000.0,
      "income_tax_expense": 11146000000.0,
      "interest_and_debt_expense": null,
      "net_income_from_continuing_operations": 72880000000.0,
      "comprehensive_income_net_of_tax": null,
      "ebit": 84273000000.0,
      "ebitda": 86137000000.0,
      "revenue_growth": null,
      "eps_growth": 130.69,
      "roce": 0.9007952626290698,
      "capital_efficiency_ratio": 1.394884237980204,
      "current_ratio": 6.183908682883581,
      "quick_ratio": 5.625367097024436,
      "debt_to_equity": 0.4068476054811098,
      "gross_profit_margin": 0.7498869705816992,
      "operating_cash_flow": null,
      "free_cash_flow": null,
      "market_cap": null,
      "beta": null,
      "pe_ratio": null,
      "trailing_eps": null,
      "forward_pe": null,
      "peg_ratio": null,
      "price_to_book": null,
      "price_to_sales": null,
      "profit_margin": null,
      "operating_margin": null,
      "return_on_assets": null,
      "return_on_equity": null,
      "revenue_per_share": null
    },

"""
