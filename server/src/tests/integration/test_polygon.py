import asyncio
import pytest
import json
from providers.polygon import PolygonProvider


@pytest.mark.asyncio
async def test_get_earnings_history_print():
	provider = PolygonProvider()
	try:
		# Use a real symbol, e.g., NVDA
		earnings_history, request_count = await provider.get_earnings_history('NVDA')
		print("EarningsHistory:", json.dumps(earnings_history.model_dump(), indent=2))
		print("Request count:", request_count)
	finally:
		await provider.close()

# Missing
# net_interest_income
# interest_income
# interest_expense
# depreciation_and_amortization
# eps_growth (Looks incorrect)
# ebitda
"""
"annual_earnings": [
    {
      "date": "2025-01-26",
      "reported_eps": 2.97,
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
      "net_interest_income": null,
      "interest_income": null,
      "interest_expense": 0.0,
      "non_interest_income": 2573000000.0,
      "other_non_operating_income": null,
      "depreciation": null,
      "depreciation_and_amortization": null,
      "income_before_tax": 84026000000.0,
      "income_tax_expense": 11146000000.0,
      "interest_and_debt_expense": null,
      "net_income_from_continuing_operations": 72880000000.0,
      "comprehensive_income_net_of_tax": null,
      "ebit": 81453000000.0,
      "ebitda": null,
      "revenue_growth": null,
      "eps_growth": null,
      "roce": 0.8706522436240033,
      "capital_efficiency_ratio": 1.394884237980204,
      "current_ratio": 4.439851498864077,
      "quick_ratio": 3.8813099130049316,
      "debt_to_equity": 0.4068476054811098,
      "gross_profit_margin": 0.7498869705816992,
      "operating_cash_flow": 64089000000.0,
      "free_cash_flow": 43668000000.0,
      "market_cap": null,
      "beta": null,
      "pe_ratio": 61.67003367003367,
      "trailing_eps": null,
      "forward_pe": null,
      "peg_ratio": null,
      "price_to_book": null,
      "price_to_sales": 34.46434630681165,
      "profit_margin": 0.5584802715771244,
      "operating_margin": 0.6241752683969747,
      "return_on_assets": 0.6530407433625147,
      "return_on_equity": 0.9187288060811577,
      "revenue_per_share": 5.314477703115455
    },



"""