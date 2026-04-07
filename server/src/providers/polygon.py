import os
import datetime
from typing import Dict, List, Optional, Tuple, Any
import json
import time
import aiohttp
import asyncio
from utils.logging import setup_logger
from utils.financial import safe_float, calculate_yoy_growth, find_by_date
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
from utils.financial import calculate_rsi, safe_float

logger = setup_logger(__name__)

class PolygonProvider():
    RATE_LIMIT = 5  # requests per minute
    BASE_URL = "https://api.polygon.io"

    def __init__(self):
        self.api_key = os.environ.get("POLYGON_API_KEY")
        if not self.api_key:
            raise ValueError("Polygon API key not found in environment variables.")
        self.last_request_time = 0
        self._session = None  # Will be initialized lazily when needed
        
    @property
    async def session(self):
        """Lazily initialize and return the aiohttp ClientSession."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
        
    async def close(self):
        """Close the aiohttp session when done."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
        
    async def _get_request(self, endpoint: str, params: Dict = None) -> Tuple[Any, int]:
        """
        Makes an asynchronous GET request to the Polygon API with rate limiting.
        
        Args:
            endpoint: The API endpoint to call
            params: Optional query parameters
            
        Returns:
            Tuple of (response data, request count)
        """
        # Rate limiting using asyncio.sleep instead of time.sleep
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time
        if time_since_last_request < (60 / self.RATE_LIMIT):
            sleep_time = (60 / self.RATE_LIMIT) - time_since_last_request
            logger.debug(f"Rate limiting: sleeping for {sleep_time:.2f} seconds")
            await asyncio.sleep(sleep_time)
            
        # Prepare request
        url = f"{self.BASE_URL}{endpoint}"
        request_params = params or {}
        request_params["apiKey"] = self.api_key
        
        # Make request asynchronously using aiohttp
        logger.debug(f"Making async GET request to {url} with params {request_params}")
        session = await self.session
        async with session.get(url, params=request_params) as response:
            self.last_request_time = time.time()
            
            # Check for errors
            if response.status != 200:
                error_text = await response.text()
                logger.error(f"Error making request to {url}: {response.status} {error_text}")
                return None, 1
            
            # Parse response
            data = await response.json()
            if data.get("status") != "OK" and "error" in data:
                logger.error(f"API error: {data.get('error')}")
                return None, 1
            
            return data, 1
    
    async def get_short_interest(self, ticker: str, limit: int = 10, sort: str = "settlement_date.desc") -> Tuple[List[dict], int]:
        """
        Fetches short-interest data for a ticker from Polygon's short-interest endpoint.

        Returns a tuple of (list_of_records, request_count).
        """
        endpoint = "/stocks/v1/short-interest"
        params = {
            "ticker": ticker,
            "limit": limit,
            "sort": sort,
        }
        logger.debug(f"Requesting short interest for {ticker} with params {params}")
        result = await self._get_request(endpoint, params)
        if not result:
            return [], 0
        data, count = result
        if not data:
            return [], count or 0

        # Polygon typically returns an object with a 'results' key
        if isinstance(data, dict) and "results" in data:
            records = data.get("results") or []
        elif isinstance(data, list):
            records = data
        else:
            records = []

        return records, count
    
    async def get_short_volume(self, ticker: str, limit: int = 10, sort: str = "date.desc") -> Tuple[List[dict], int]:
        """
        Fetches short-volume data for a ticker from Polygon's short-volume endpoint.

        Returns a tuple of (list_of_records, request_count).
        """
        endpoint = "/stocks/v1/short-volume"
        params = {
            "ticker": ticker,
            "limit": limit,
            "sort": sort,
        }
        logger.debug(f"Requesting short volume for {ticker} with params {params}")
        result = await self._get_request(endpoint, params)
        if not result:
            return [], 0
        data, count = result
        if not data:
            return [], count or 0

        # Polygon typically returns an object with a 'results' key
        if isinstance(data, dict) and "results" in data:
            records = data.get("results") or []
        elif isinstance(data, list):
            records = data
        else:
            records = []

        return records, count
        
    def create_earning(self, result_item, previous_result_item=None):
        """
        Creates an Earning object from Polygon financial data.
        
        Args:
            result_item: Result item from Polygon API containing financials data
            previous_result_item: Previous year's result item for YoY calculations
            
        Returns:
            Earning object
        """
        # Debug log for start_date of both items
        logger.debug(f"create_earning: result_item.start_date={result_item.get('start_date', None) if isinstance(result_item, dict) else None}, previous_result_item.start_date={previous_result_item.get('start_date', None) if isinstance(previous_result_item, dict) else None}")
        if not result_item or "financials" not in result_item:
            logger.warning("No valid financial data provided to create_earning")
            return None
            
        # Access the financial statement data
        income_data = result_item.get("financials", {}).get("income_statement", {})
        balance_data = result_item.get("financials", {}).get("balance_sheet", {})
        
        # Access previous data if available
        previous_income_data = previous_result_item.get("financials", {}).get("income_statement", {}) if previous_result_item else None
        previous_balance_data = previous_result_item.get("financials", {}).get("balance_sheet", {}) if previous_result_item else None
            
        # Extract current values - direct access to values in the data structure
        # Polygon API response may have different structures - handle both patterns
        # First try the structure with direct 'value' field
        reported_eps = safe_float(income_data.get("basic_earnings_per_share", {}).get("value", None))
        total_revenue = safe_float(income_data.get("revenues", {}).get("value", None))
        
        # If values aren't found, they might be in a different structure where 'value' is at a different level
        # or another field like 'value_usd' or other variations
        if reported_eps is None and "basic_earnings_per_share" in income_data:
            eps_data = income_data["basic_earnings_per_share"]
            if isinstance(eps_data, dict):
                for key in ["value", "value_usd", "amount", "raw_value"]:
                    if key in eps_data:
                        reported_eps = safe_float(eps_data.get(key))
                        break
        
        if total_revenue is None and "revenues" in income_data:
            revenue_data = income_data["revenues"]
            if isinstance(revenue_data, dict):
                for key in ["value", "value_usd", "amount", "raw_value"]:
                    if key in revenue_data:
                        total_revenue = safe_float(revenue_data.get(key))
                        break
        
        # Extract previous values for YoY calculations using the same approach
        previous_eps = None
        previous_revenue = None
        
        if previous_income_data:
            previous_eps = safe_float(previous_income_data.get("basic_earnings_per_share", {}).get("value", None))
            if previous_eps is None and "basic_earnings_per_share" in previous_income_data:
                eps_data = previous_income_data["basic_earnings_per_share"]
                if isinstance(eps_data, dict):
                    for key in ["value", "value_usd", "amount", "raw_value"]:
                        if key in eps_data:
                            previous_eps = safe_float(eps_data.get(key))
                            break
            
            previous_revenue = safe_float(previous_income_data.get("revenues", {}).get("value", None))
            if previous_revenue is None and "revenues" in previous_income_data:
                revenue_data = previous_income_data["revenues"]
                if isinstance(revenue_data, dict):
                    for key in ["value", "value_usd", "amount", "raw_value"]:
                        if key in revenue_data:
                            previous_revenue = safe_float(revenue_data.get(key))
                            break
        
        # Calculate YoY growth rates
        #revenue_growth = calculate_yoy_growth(total_revenue, previous_revenue)
        #eps_growth = calculate_yoy_growth(reported_eps, previous_eps)
        
        # Log the calculation for EPS growth for debugging
        #logger.debug(f"EPS growth calculation: current={reported_eps}, previous={previous_eps}, result={eps_growth}")
        
        # Get date from result item
        fiscal_date = result_item.get("fiscal_date", result_item.get("end_date", ""))
        
        # Basic earning data
        base_earning = {
            "date": fiscal_date,
            "reported_eps": reported_eps,
            "estimated_eps": None,  # Polygon doesn't provide this in the same endpoint
        }
        
        # Map Polygon fields to our model fields
        income_mapping = {
            "net_income": "net_income_loss",
            "operating_income": "operating_income_loss",
            "gross_profit": "gross_profit",
            "total_revenue": "revenues",
            "cost_of_revenue": "cost_of_revenue",
            "cost_of_goods_and_services_sold": "cost_of_revenue",  # Alternative field for cost of goods sold
            "operating_expenses": "operating_expenses",
            "interest_income": "interest_income",  # Missing
            "interest_expense": "interest_expense_operating",
            "income_before_tax": "income_loss_from_continuing_operations_before_tax",
            "income_tax_expense": "income_tax_expense_benefit",
            "research_and_development": "research_and_development",
            "selling_general_and_administrative": "selling_general_and_administrative_expenses",
            "depreciation": "depreciation",
            "depreciation_and_amortization": "depreciation_and_amortization",
            "net_income_from_continuing_operations": "income_loss_from_continuing_operations_after_tax",
            "comprehensive_income_net_of_tax": "comprehensive_income_loss",
            "interest_and_debt_expense": "interest_expense",
            "investment_income_net": "investment_income_net",
            "net_interest_income": "net_interest_income",
            "non_interest_income": "nonoperating_income_loss",
            "other_non_operating_income": "other_non_operating_income"
        }
        
        # Add mapped fields
        for model_field, polygon_field in income_mapping.items():
            value = None
            if polygon_field in income_data:
                field_data = income_data.get(polygon_field)
                if isinstance(field_data, dict):
                    # Try to find value in different possible locations
                    for key in ["value", "value_usd", "amount", "raw_value"]:
                        if key in field_data:
                            value = safe_float(field_data.get(key))
                            break
                    
                    # If value is still None but there are other keys, try using the first numeric value
                    if value is None:
                        for key, val in field_data.items():
                            if key != "order" and isinstance(val, (int, float, str)):
                                try:
                                    value = safe_float(val)
                                    break
                                except (ValueError, TypeError):
                                    continue
            
            if value is not None:
                base_earning[model_field] = value
        
        # Calculate financial ratios if balance sheet data is available
        if balance_data:
            try:
                # Extract values needed for calculations
                # First, create a helper function to extract values with flexible field access
                def extract_value(data_dict, field_name):
                    if field_name not in data_dict:
                        return None
                    
                    field_data = data_dict.get(field_name)
                    if isinstance(field_data, dict):
                        # Try standard value fields
                        for key in ["value", "value_usd", "amount", "raw_value"]:
                            if key in field_data:
                                return safe_float(field_data.get(key))
                        
                        # If no standard value field, try any numeric value except "order"
                        for key, val in field_data.items():
                            if key != "order" and isinstance(val, (int, float, str)):
                                try:
                                    return safe_float(val)
                                except (ValueError, TypeError):
                                    continue
                    
                    return None
                
                # Extract all the financial values we need
                ebit = extract_value(income_data, "operating_income_loss")
                revenue = extract_value(income_data, "revenues")
                total_assets = extract_value(balance_data, "assets")
                current_assets = extract_value(balance_data, "current_assets")
                current_liabilities = extract_value(balance_data, "current_liabilities")
                total_liabilities = extract_value(balance_data, "liabilities")
                total_shareholder_equity = extract_value(balance_data, "equity")
                inventory = extract_value(balance_data, "inventory")
                cash_and_equiv = extract_value(balance_data, "cash_and_equivalents")
                gross_profit = extract_value(income_data, "gross_profit")
                net_income = extract_value(income_data, "net_income_loss")
                
                # Handle depreciation and amortization - try different field variations
                depreciation_amortization = extract_value(income_data, "depreciation_and_amortization")
                if depreciation_amortization is None:
                    # Try to get depreciation separately as it might be available even if combined field isn't
                    depreciation = extract_value(income_data, "depreciation") or 0
                    amortization = extract_value(income_data, "amortization") or 0
                    depreciation_amortization = depreciation + amortization if (depreciation > 0 or amortization > 0) else None
                
                income_before_tax = extract_value(income_data, "income_loss_from_continuing_operations_before_tax")
                interest_income = extract_value(income_data, "interest_income")
                interest_expense = extract_value(income_data, "interest_expense")
                net_interest_income = extract_value(income_data, "net_interest_income")
                
                # Get basic average shares if available (for per-share calculations)
                basic_average_shares = extract_value(income_data, "basic_average_shares")
                
                # Try to get cash flow data if available
                cash_flow_data = result_item.get("financials", {}).get("cash_flow_statement", {})
                operating_cashflow = extract_value(cash_flow_data, "net_cash_flow_from_operating_activities")
                capital_expenditures = extract_value(cash_flow_data, "capital_expenditures")
                if capital_expenditures is None:
                    # Use net_cash_flow_from_investing_activities as a proxy (negative value)
                    net_investing = extract_value(cash_flow_data, "net_cash_flow_from_investing_activities")
                    if net_investing is not None:
                        capital_expenditures = -net_investing
                    else:
                        capital_expenditures = None
                
                # Calculate EBIT and EBITDA if needed
                if ebit is None and net_income is not None:
                    interest_expense = extract_value(income_data, "interest_expense")
                    income_tax = extract_value(income_data, "income_tax_expense_benefit")
                    
                    if interest_expense is not None and income_tax is not None:
                        ebit = net_income + interest_expense + income_tax
                
                # Calculate EBITDA
                ebitda = None
                if ebit is not None and depreciation_amortization is not None:
                    ebitda = ebit + depreciation_amortization
                elif net_income is not None:
                    # If depreciation_amortization is still missing or zero, try again to calculate from individual components
                    if depreciation_amortization is None or depreciation_amortization == 0:
                        # Check for fields with variations in naming
                        for dep_field in ["depreciation", "depreciation_expense", "depreciation_depletion_and_amortization"]:
                            depreciation = extract_value(income_data, dep_field)
                            if depreciation:
                                break
                        
                        for amort_field in ["amortization", "amortization_expense", "amortization_of_intangible_assets"]:
                            amortization = extract_value(income_data, amort_field)
                            if amortization:
                                break
                                
                        if depreciation or amortization:
                            depreciation_amortization = (depreciation or 0) + (amortization or 0)
                    
                    interest_expense = extract_value(income_data, "interest_expense") or 0
                    income_tax = extract_value(income_data, "income_tax_expense_benefit") or 0
                    
                    if depreciation_amortization is not None:
                        ebitda = net_income + interest_expense + income_tax + depreciation_amortization
                
                # Calculate capital efficiency ratios
                capital_employed = total_assets - current_liabilities if total_assets is not None and current_liabilities is not None else None
                
                roce = ebit / capital_employed if ebit is not None and capital_employed is not None and capital_employed != 0 else None
                capital_efficiency_ratio = revenue / capital_employed if revenue is not None and capital_employed is not None and capital_employed != 0 else None
                
                # Calculate liquidity ratios
                current_ratio = current_assets / current_liabilities if current_assets is not None and current_liabilities is not None and current_liabilities != 0 else None
                quick_ratio = (current_assets - inventory) / current_liabilities if all(v is not None for v in [current_assets, inventory, current_liabilities]) and current_liabilities != 0 else None
                
                # Calculate leverage ratios
                debt_to_equity = total_liabilities / total_shareholder_equity if total_liabilities is not None and total_shareholder_equity is not None and total_shareholder_equity != 0 else None
                
                # Calculate profitability ratios
                gross_profit_margin = gross_profit / revenue if gross_profit is not None and revenue is not None and revenue != 0 else None
                profit_margin = net_income / revenue if net_income is not None and revenue is not None and revenue != 0 else None
                operating_margin = ebit / revenue if ebit is not None and revenue is not None and revenue != 0 else None
                return_on_assets = net_income / total_assets if net_income is not None and total_assets is not None and total_assets != 0 else None
                return_on_equity = net_income / total_shareholder_equity if net_income is not None and total_shareholder_equity is not None and total_shareholder_equity != 0 else None
                
                # Calculate cash flow metrics
                free_cash_flow = operating_cashflow - capital_expenditures if operating_cashflow is not None and capital_expenditures is not None else None
                
                # Calculate per-share metrics
                revenue_per_share = revenue / basic_average_shares if revenue is not None and basic_average_shares is not None and basic_average_shares != 0 else None
                
                # Add calculated metrics to the base earning
                additional_metrics = {
                    "ebit": ebit,
                    "ebitda": ebitda,
                    "income_before_tax": income_before_tax,
                    "interest_income": interest_income,
                    "interest_expense": interest_expense,
                    "net_interest_income": net_interest_income,
                    "depreciation_and_amortization": depreciation_amortization,
                    "roce": roce,
                    "capital_efficiency_ratio": capital_efficiency_ratio,
                    "current_ratio": current_ratio,
                    "quick_ratio": quick_ratio,
                    "debt_to_equity": debt_to_equity,
                    "gross_profit_margin": gross_profit_margin,
                    "profit_margin": profit_margin,
                    "operating_margin": operating_margin,
                    "return_on_assets": return_on_assets,
                    "return_on_equity": return_on_equity,
                    "operating_cash_flow": operating_cashflow,
                    "free_cash_flow": free_cash_flow,
                    "revenue_per_share": revenue_per_share
                }
                
                # Add all the calculated metrics to base_earning
                base_earning.update({k: v for k, v in additional_metrics.items() if v is not None})
                
            except Exception as e:
                logger.error(f"Error calculating earning ratios: {e}")
        
        return Earning(**base_earning)
    
    async def get_earnings_history(self, symbol: str) -> Tuple[EarningsHistory, int]:
        """
        Fetches earnings history for a given symbol using Polygon.io API asynchronously.
        
        Args:
            symbol: The stock symbol to fetch data for
            
        Returns:
            Tuple of (EarningsHistory object, request count)
        """
        request_count = 0
        
        # Define timeframes
        quarterly_limit = 8  # Fetch more quarters to ensure we have enough for YoY comparisons
        annual_limit = 5     # Fetch 5 years (to calculate YoY for 4)
        
        # Try to get current price for additional calculations
        current_price = None
        try:
            price_data, count = await self._get_request(f"/v2/aggs/ticker/{symbol}/prev", {})
            request_count += count
            
            if price_data and price_data.get("status") == "OK" and "results" in price_data:
                results = price_data.get("results", [])
                if results and len(results) > 0:
                    current_price = safe_float(results[0].get("c"))
                    logger.debug(f"Current price for {symbol}: {current_price}")
        except Exception as e:
            logger.warning(f"Failed to fetch current price for {symbol}: {e}")
        
        # Fetch quarterly and annual financials in parallel
        quarterly_task = self._get_request("/vX/reference/financials", {
            "ticker": symbol,
            "timeframe": "quarterly",
            "limit": quarterly_limit,
            "sort": "filing_date",
            "order": "desc",
        })
        
        annual_task = self._get_request("/vX/reference/financials", {
            "ticker": symbol,
            "timeframe": "annual",
            "limit": annual_limit,
            "sort": "filing_date",
            "order": "desc",
        })
        
        # Wait for both requests to complete concurrently
        quarterly_result, annual_result = await asyncio.gather(
            quarterly_task,
            annual_task
        )
        
        # Unpack results
        quarterly_financials_data, q_count = quarterly_result
        annual_financials_data, a_count = annual_result
        request_count += q_count + a_count
        
        # Process quarterly data
        quarterly_earnings = []
        if quarterly_financials_data and "results" in quarterly_financials_data:
            quarterly_results = quarterly_financials_data["results"]
            
            # Log the structure of the first result to help with debugging
            if quarterly_results and len(quarterly_results) > 0:
                logger.debug(f"Polygon quarterly financial data structure sample: {json.dumps(quarterly_results[0], indent=2)[:1000]}...")
            
            # Get the 4 most recent quarters with complete data
            valid_quarters = [
                q for q in quarterly_results 
                if "financials" in q 
                and "income_statement" in q.get("financials", {})
                and "balance_sheet" in q.get("financials", {})
            ]
            
            # Process up to 4 most recent quarters
            for i in range(min(4, len(valid_quarters))):
                current_quarter_dict = valid_quarters[i]
                current_date = current_quarter_dict.get("end_date")
                
                # Find the same quarter from previous year for YoY comparison
                previous_year_quarter = None
                
                # Look for the closest matching quarter from the previous year
                if current_date:
                    try:
                        current_year = int(current_date.split("-")[0])
                        current_month = int(current_date.split("-")[1])
                        quarter_num = (current_month - 1) // 3 + 1  # Calculate quarter (1-4) from month
                        
                        # Find the quarter from previous year that matches the same fiscal quarter
                        closest_quarter_match = None
                        smallest_month_diff = 12  # Initialize with max possible difference
                        
                        for prev_quarter in valid_quarters:
                            prev_date = prev_quarter.get("end_date", "")
                            if prev_date and prev_date != current_date:  # Skip the current quarter
                                try:
                                    prev_year = int(prev_date.split("-")[0])
                                    prev_month = int(prev_date.split("-")[1])
                                    
                                    # Check if it's from the previous year
                                    if prev_year == current_year - 1:
                                        # Calculate how close this quarter is to the same period in previous year
                                        month_diff = abs(prev_month - current_month)
                                        
                                        # Keep track of the closest match
                                        if month_diff < smallest_month_diff:
                                            smallest_month_diff = month_diff
                                            closest_quarter_match = prev_quarter
                                except (ValueError, IndexError):
                                    continue
                        
                        # Use the closest matching quarter as the previous year's comparison
                        if closest_quarter_match:
                            previous_year_quarter = closest_quarter_match
                            prev_date = closest_quarter_match.get("end_date", "")
                            logger.debug(f"Found previous year quarter for {current_date}: {prev_date}")
                    except (ValueError, IndexError) as e:
                        logger.warning(f"Error finding previous year quarter for {current_date}: {e}")
                
                earning = self.create_earning(current_quarter_dict, previous_year_quarter)
                
                # Add price-based metrics if we have a current price
                if earning and current_price:
                    if earning.reported_eps:
                        # Set PE ratio if we have EPS data
                        setattr(earning, 'pe_ratio', current_price / earning.reported_eps)
                        
                    # Add other price-based metrics if we have the necessary data
                    if earning.total_revenue and getattr(earning, 'revenue_per_share', None):
                        setattr(earning, 'price_to_sales', current_price / earning.revenue_per_share)
                
                if earning:
                    quarterly_earnings.append(earning)
        
        # Process annual data
        annual_earnings = []
        if annual_financials_data and "results" in annual_financials_data:
            annual_results = annual_financials_data["results"]
            
            # Log the structure of the first result to help with debugging
            if annual_results and len(annual_results) > 0:
                logger.debug(f"Polygon annual financial data structure sample: {json.dumps(annual_results[0], indent=2)[:1000]}...")
            
            # Get years with complete data
            valid_years = [
                y for y in annual_results 
                if "financials" in y 
                and "income_statement" in y.get("financials", {})
                and "balance_sheet" in y.get("financials", {})
            ]
            
            # Process up to 4 most recent years
            for i in range(min(4, len(valid_years))):
                current_year = valid_years[i]
                previous_year = valid_years[i+1] if i+1 < len(valid_years) else None
                
                # Log fiscal years for debugging
                current_fiscal_year = current_year.get("fiscal_year", "")
                previous_fiscal_year = previous_year.get("fiscal_year", "") if previous_year else "None"
                logger.debug(f"Processing annual data: current fiscal year={current_fiscal_year}, previous fiscal year={previous_fiscal_year}")
                
                earning = self.create_earning(current_year, previous_year)
                
                # Add price-based metrics if we have a current price
                if earning and current_price:
                    if earning.reported_eps:
                        # Set PE ratio if we have EPS data
                        setattr(earning, 'pe_ratio', current_price / earning.reported_eps)
                        
                    # Add other price-based metrics if we have the necessary data
                    if earning.total_revenue and getattr(earning, 'revenue_per_share', None):
                        setattr(earning, 'price_to_sales', current_price / earning.revenue_per_share)
                
                if earning:
                    annual_earnings.append(earning)
        
        earnings_history = EarningsHistory(
            quarterly_earnings=quarterly_earnings,
            annual_earnings=annual_earnings
        )
        
        logger.info("Polygon earnings data:")
        logger.debug(f"{json.dumps(earnings_history.model_dump(), indent=2)}")
        
        return earnings_history, request_count
