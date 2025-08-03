import os
import requests
from typing import Dict, List, Optional, Tuple
import json
from utils.logging import setup_logger
from services.utils import safe_float, calculate_yoy_growth, find_by_date
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
import pandas as pd
from services.utils import calculate_rsi

logger = setup_logger(__name__)

class AlphaVantageProvider(MarketDataProvider):
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.api_key = os.environ.get("ALPHA_VANTAGE_API_KEY")
        if not self.api_key:
            raise ValueError("Alpha Vantage API key not found in environment variables.")
        self.base_url = "https://www.alphavantage.co/query"

    def get_technical_indicators(self) -> TechnicalIndicators:
        # Fetch daily prices
        params = {
            "function": "TIME_SERIES_DAILY",
            "symbol": self.symbol,
            "apikey": self.api_key,
        }
        response = requests.get(self.base_url, params=params)
        daily_data = response.json()
        ohlcv = daily_data.get("Time Series (Daily)", {})
        logger.debug(f"Alpha Vantage TIME_SERIES_DAILY: {json.dumps(daily_data, indent=2)}")

        if "Time Series (Daily)" not in daily_data:
            logger.error(f"Error fetching daily data for {self.symbol}: {daily_data}")
            # Return default values or raise an exception
            return TechnicalIndicators(
                current_price=0.0, sma_20=0.0, sma_50=0.0, sma_200=0.0, rsi=0.0, volume_trend=0.0
            )

        prices = {
            date: float(price["4. close"])
            for date, price in ohlcv.items()
        }
        volumes = {
            date: int(price["5. volume"])
            for date, price in ohlcv.items()
        }

        price_series = pd.Series(prices)
        volume_series = pd.Series(volumes)

        current_price = price_series.iloc[-1]
        sma_20 = price_series.rolling(window=20).mean().iloc[-1] if len(price_series) >= 20 else current_price
        sma_50 = price_series.rolling(window=50).mean().iloc[-1] if len(price_series) >= 50 else current_price
        sma_200 = price_series.rolling(window=200).mean().iloc[-1] if len(price_series) >= 200 else current_price
        volume_trend = (sum(list(volumes.values())[:5]) / 5) / (
            sum(list(volumes.values())[:20]) / 20
        ) if len(volumes) >= 20 and sum(list(volumes.values())[:20]) >0 else 1

        rsi = calculate_rsi(price_series).iloc[-1] if len(price_series) > 14 else 50

        return TechnicalIndicators(
            current_price=current_price,
            sma_20=float(sma_20),
            sma_50=float(sma_50),
            sma_200=float(sma_200),
            rsi=float(rsi),
            volume_trend=volume_trend,
            ohlcv=ohlcv
        )

    def get_dividend_history(self) -> DividendHistory:
        params = {
            "function": "CASH_FLOW",
            "symbol": self.symbol,
            "apikey": self.api_key,
        }
        response = requests.get(self.base_url, params=params)
        data = response.json()
        logger.debug(f"Alpha Vantage CASH_FLOW: {data}")

        dividends = {}
        for report in data.get("quarterlyReports", [])[:4]:
            dividends[report.get("fiscalDateEnding")] = float(
                report.get("dividendPayout", 0)
            )

        return DividendHistory(dividends=dividends)

    def create_earning(self, earning_data, report_data, balance_data=None, previous_earning_data=None, previous_report_data=None, previous_balance_data=None):
        # Get current values
        reported_eps = safe_float(earning_data.get("reportedEPS"))
        total_revenue = safe_float(report_data.get("totalRevenue")) if report_data else None

        # Get previous values for YoY calculations
        previous_eps = safe_float(previous_earning_data.get("reportedEPS")) if previous_earning_data else None
        previous_revenue = safe_float(previous_report_data.get("totalRevenue")) if previous_report_data else None

        # Calculate YoY growth rates
        revenue_growth = calculate_yoy_growth(total_revenue, previous_revenue)
        eps_growth = calculate_yoy_growth(reported_eps, previous_eps)

        # Basic earning data
        base_earning = {
            "date": earning_data.get("fiscalDateEnding", ""),
            "reported_eps": reported_eps,
            "estimated_eps": safe_float(earning_data.get("estimatedEPS")),
            "revenue_growth": revenue_growth,
            "eps_growth": eps_growth
        }

        if not report_data:
            return Earning(**base_earning)

        # Add financial report data if available
        report_data_fields = {
            "net_income": "netIncome",
            "operating_income": "operatingIncome",
            "gross_profit": "grossProfit",
            "total_revenue": "totalRevenue",
            "cost_of_revenue": "costOfRevenue",
            "cost_of_goods_and_services_sold": "costofGoodsAndServicesSold",
            "selling_general_and_administrative": "sellingGeneralAndAdministrative",
            "research_and_development": "researchAndDevelopment",
            "operating_expenses": "operatingExpenses",
            "investment_income_net": "investmentIncomeNet",
            "net_interest_income": "netInterestIncome",
            "interest_income": "interestIncome",
            "interest_expense": "interestExpense",
            "non_interest_income": "nonInterestIncome",
            "other_non_operating_income": "otherNonOperatingIncome",
            "depreciation": "depreciation",
            "depreciation_and_amortization": "depreciationAndAmortization",
            "income_before_tax": "incomeBeforeTax",
            "income_tax_expense": "incomeTaxExpense",
            "interest_and_debt_expense": "interestAndDebtExpense",
            "net_income_from_continuing_operations": "netIncomeFromContinuingOperations",
            "comprehensive_income_net_of_tax": "comprehensiveIncomeNetOfTax",
            "ebit": "ebit",
            "ebitda": "ebitda"
        }

        for model_field, report_field in report_data_fields.items():
            base_earning[model_field] = safe_float(report_data.get(report_field))

        # Calculate Capital Efficiency and other values
        roce = None
        capital_efficiency_ratio = None
        #enterprise_value = None
        current_ratio = None
        quick_ratio = None
        debt_to_equity = None
        revenue_growth = None
        gross_profit_margin = None
        operating_cash_flow = None
        free_cash_flow = None
        try:
            ebit = safe_float(report_data.get("ebit"))
            revenue = safe_float(report_data.get("totalRevenue")) if report_data else None
            total_assets = safe_float(balance_data.get("totalAssets")) if balance_data else None
            current_liabilities = safe_float(balance_data.get("totalCurrentLiabilities")) if balance_data else None
            total_liabilities = safe_float(balance_data.get("totalLiabilities")) if balance_data else None
            total_shareholder_equity = safe_float(balance_data.get("totalShareholderEquity")) if balance_data else None
            inventory = safe_float(balance_data.get("inventory")) if balance_data else None
            cash_and_equiv = safe_float(balance_data.get("cashAndCashEquivalentsAtCarryingValue")) if balance_data else None
            gross_profit = safe_float(report_data.get("grossProfit")) if report_data else None
            operating_cashflow = safe_float(report_data.get("operatingCashflow")) if report_data else None
            capital_expenditures = safe_float(report_data.get("capitalExpenditures")) if report_data else None

            capital_employed = total_assets - current_liabilities if total_assets is not None and current_liabilities is not None else None
            if ebit is not None and capital_employed is not None and capital_employed != 0:
                roce = ebit / capital_employed
            if revenue is not None and capital_employed is not None and capital_employed != 0:
                capital_efficiency_ratio = revenue / capital_employed
            if total_assets is not None and current_liabilities is not None and current_liabilities != 0:
                current_ratio = total_assets / current_liabilities
            if total_assets is not None and inventory is not None and current_liabilities is not None and current_liabilities != 0:
                quick_ratio = (total_assets - inventory) / current_liabilities
            if total_liabilities is not None and total_shareholder_equity is not None and total_shareholder_equity != 0:
                debt_to_equity = total_liabilities / total_shareholder_equity
            if gross_profit is not None and revenue is not None and revenue != 0:
                gross_profit_margin = gross_profit / revenue
            if operating_cashflow is not None:
                operating_cash_flow = operating_cashflow
            if operating_cashflow is not None and capital_expenditures is not None:
                free_cash_flow = operating_cashflow - capital_expenditures

            """
            # Calculate missing values
            enterprise_value = int(overview_data.get("MarketCapitalization", 0)) + int(latest_balance_sheet.get("totalLiabilities", 0)) - int(latest_cash_flow.get("cashAndCashEquivalentsAtCarryingValue", 0))
            current_ratio = float(latest_balance_sheet.get("totalCurrentAssets", 0)) / float(latest_balance_sheet.get("totalCurrentLiabilities", 0))
            quick_ratio = (float(latest_balance_sheet.get("totalCurrentAssets", 0)) - float(latest_balance_sheet.get("inventory", 0))) / float(latest_balance_sheet.get("totalCurrentLiabilities", 0))
            debt_to_equity = float(latest_balance_sheet.get("totalLiabilities", 0)) / float(latest_balance_sheet.get("totalShareholderEquity", 0))
            gross_profit_margin = float(latest_income_statement.get("grossProfit", 0)) / float(latest_income_statement.get("totalRevenue", 0))
            operating_cash_flow = float(latest_cash_flow.get("operatingCashflow", 0))
            free_cash_flow = float(latest_cash_flow.get("operatingCashflow", 0)) - float(latest_cash_flow.get("capitalExpenditures", 0))
            """
        except Exception as e:
            logger.error(f"Error calculating earning ratios: {e}")
        base_earning["roce"] = roce
        base_earning["capital_efficiency_ratio"] = capital_efficiency_ratio
        #base_earning["enterprise_value"] = enterprise_value
        base_earning["current_ratio"] = current_ratio
        base_earning["quick_ratio"] = quick_ratio
        base_earning["debt_to_equity"] = debt_to_equity
        base_earning["revenue_growth"] = revenue_growth
        base_earning["gross_profit_margin"] = gross_profit_margin
        base_earning["operating_cash_flow"] = operating_cash_flow
        base_earning["free_cash_flow"] = free_cash_flow

        return Earning(**base_earning)
    
    def get_earnings_history(self) -> EarningsHistory:
        request_count = 0
        # Fetch earnings per share
        params = {
            "function": "EARNINGS",
            "symbol": self.symbol,
            "apikey": self.api_key,
        }
        response = requests.get(self.base_url, params=params)
        earnings_data = response.json()
        request_count += 1
        logger.debug(f"Alpha Vantage EARNINGS: {earnings_data}")

        # Fetch income statement
        params = {
            "function": "INCOME_STATEMENT",
            "symbol": self.symbol,
            "apikey": self.api_key,
        }
        response = requests.get(self.base_url, params=params)
        income_statement_data = response.json()
        request_count += 1
        logger.debug(f"Alpha Vantage INCOME_STATEMENT: {income_statement_data}")

        # Fetch balance sheet
        params = {
            "function": "BALANCE_SHEET",
            "symbol": self.symbol,
            "apikey": self.api_key,
        }
        response = requests.get(self.base_url, params=params)
        balance_sheet_data = response.json()
        request_count += 1
        logger.debug(f"Alpha Vantage BALANCE_SHEET: {balance_sheet_data}")

        # Process quarterly earnings
        quarterly_earnings = []
        quarterly_data = earnings_data.get("quarterlyEarnings", [])[:5]  # Get 5 quarters to calculate YoY
        quarterly_reports = income_statement_data.get("quarterlyReports", [])[:5]
        quarterly_balance = balance_sheet_data.get("quarterlyReports", [])[:5]

        for i in range(min(4, len(quarterly_data))):  # Process only the most recent 4 quarters
            current_quarter = quarterly_data[i]
            date = current_quarter.get("fiscalDateEnding")
            current_report = find_by_date(quarterly_reports, date)
            current_balance = find_by_date(quarterly_balance, date)

            if current_report is None:
                continue  # Skip if no matching income statement report

            # Previous year (same quarter last year)
            previous_quarter = quarterly_data[i+4] if i+4 < len(quarterly_data) else None
            previous_date = previous_quarter.get("fiscalDateEnding") if previous_quarter else None
            previous_report = find_by_date(quarterly_reports, previous_date) if previous_date else None
            previous_balance = find_by_date(quarterly_balance, previous_date) if previous_date else None

            quarterly_earnings.append(self.create_earning(
                current_quarter,
                current_report,
                current_balance,
                previous_quarter,
                previous_report,
                previous_balance
            ))

        # Process annual earnings
        annual_earnings = []
        annual_data = earnings_data.get("annualEarnings", [])[:5]  # Get 5 years to calculate YoY
        annual_reports = income_statement_data.get("annualReports", [])[:5]
        annual_balance = balance_sheet_data.get("annualReports", [])[:5]

        for i in range(min(4, len(annual_data))):  # Process only the most recent 4 years
            current_year = annual_data[i]
            date = current_year.get("fiscalDateEnding")
            current_report = find_by_date(annual_reports, date)
            current_balance = find_by_date(annual_balance, date)

            if current_report is None:
                continue  # Skip if no matching income statement report

            previous_year = annual_data[i+1] if i+1 < len(annual_data) else None
            previous_date = previous_year.get("fiscalDateEnding") if previous_year else None
            previous_report = find_by_date(annual_reports, previous_date) if previous_date else None
            previous_balance = find_by_date(annual_balance, previous_date) if previous_date else None

            annual_earnings.append(self.create_earning(
                current_year,
                current_report,
                current_balance,
                previous_year,
                previous_report,
                previous_balance
            ))

        earnings_history = EarningsHistory(
            quarterly_earnings=quarterly_earnings,
            annual_earnings=annual_earnings
        )
        logger.info("AlphaVantage earnings data:")
        logger.debug(f"{json.dumps(earnings_history.model_dump(), indent=2)}")
        return earnings_history, request_count

    def get_market_data(self) -> MarketData:
        request_count = 0
        # Fetch overview data
        params = {
            "function": "OVERVIEW",
            "symbol": self.symbol,
            "apikey": self.api_key,
        }
        response = requests.get(self.base_url, params=params)
        overview_data = response.json()
        request_count += 1
        logger.debug(f"Alpha Vantage OVERVIEW: {overview_data}")

        return MarketData(
            sector=overview_data.get("Sector", "Unknown"),
            industry=overview_data.get("Industry", "Unknown"),
            market_cap=int(overview_data.get("MarketCapitalization", 0)),
            beta=safe_float(overview_data.get("Beta", 1.0)) or 0.0,
            pe_ratio=safe_float(overview_data.get("PERatio", 0)) or 0.0,
            dividend_yield=safe_float(overview_data.get("DividendYield", 0)) or 0.0,
            divident_rate=safe_float(overview_data.get("DividendPerShare", 0)) or 0.0,
            trailing_eps=safe_float(overview_data.get("EPS", 0)) or 0.0,
            forward_pe=safe_float(overview_data.get("ForwardPE", 0)) or 0.0,
            peg_ratio=safe_float(overview_data.get("PEGRatio", 0)) or 0.0,
            price_to_book=safe_float(overview_data.get("PriceToBookRatio", 0)) or 0.0,
            price_to_sales=safe_float(overview_data.get("PriceToSalesRatioTTM", 0)) or 0.0,
            profit_margin=safe_float(overview_data.get("ProfitMargin", 0)) or 0.0,
            operating_margin=safe_float(overview_data.get("OperatingMarginTTM", 0)) or 0.0,
            return_on_assets=safe_float(overview_data.get("ReturnOnAssetsTTM", 0)) or 0.0,
            return_on_equity=safe_float(overview_data.get("ReturnOnEquityTTM", 0)) or 0.0,
            revenue_per_share=safe_float(overview_data.get("RevenuePerShareTTM", 0)) or 0.0,
        ), request_count

    def get_news(self) -> News:
        params = {
            "function": "NEWS_SENTIMENT",
            "tickers": self.symbol,
            "apikey": self.api_key,
        }
        response = requests.get(self.base_url, params=params)
        data = response.json()
        logger.debug(f"Alpha Vantage NEWS_SENTIMENT: {data}")

        news_items = []
        for item in data.get("feed", [])[:10]:
            news_items.append(
                NewsItem(
                    title=item.get("title", ""),
                    publisher=item.get("source", ""),
                    url=item.get("url", ""),
                    timestamp=item.get("time_published", ""),
                )
            )

        return News(news=news_items)

    def safe_float(value) -> Optional[float]:
            """Safely convert a value to float, handling None and "None" cases"""
            if value is None or value == "None" or value == "":
                return None
            try:
                return float(value)
            except (ValueError, TypeError):
                return None
