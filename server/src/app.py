import os
import traceback
import json
from typing import List, Optional, Dict, Any
from datetime import date, time
from datetime import datetime, timedelta
from langchain_google_genai import ChatGoogleGenerativeAI

from graphs.fundamental import FundamentalGraph
from graphs.technical import TechnicalAnalysisGraph
from graphs.portfolio import PortfolioGraph
from providers.yfinance import YFinanceProvider
from providers.alphavantage import AlphaVantageProvider
from services.database import db_manager, Stock, Research, HistoricalValues
from utils.logging import setup_logger
from models.models import ApiRequestUsage

class StockAnalysisApp:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(StockAnalysisApp, cls).__new__(cls)
            # Initialize the singleton instance
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize the StockAnalysisApp with database and advisors (only once)"""
        if self._initialized:
            return
            
        self.db_manager = db_manager  # Use the singleton instance
        # self.stock_advisor = StockAdvisor(db_manager=self.db_manager)
        self.logger = setup_logger("stock_app")
        # Initialize all graphs
        self.llm = self.setup_llm()
        self.fundamental_graph = FundamentalGraph(llm=self.llm)
        self.technical_graph = TechnicalAnalysisGraph(llm=self.llm)
        self.portfolio_graph = PortfolioGraph(llm=self.llm)
        self._initialized = True

    # Initialize the ollama endpoint
    def setup_llm(self):
        return ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            temperature=1.0,
            max_retries=2,
            api_key=os.getenv("GEMINI_API_KEY"),
        )

    def add_stock(self, symbol: str) -> Dict[str, Any]:
        """Add a new stock to the database"""
        try:
            stock = self.db_manager.get_or_create_stock(symbol)
            return {
                "message": f"Stock {symbol} added successfully",
                "data": {"symbol": stock.symbol, "id": stock.id}
            }
        except Exception as e:
            self.logger.error(f"Error adding stock: {str(e)}\n{traceback.format_exc()}")
            raise e

    def get_all_stocks(self) -> Dict[str, Any]:
        """Get all stocks from the database"""
        try:
            stocks = self.db_manager.get_all_stocks()
            return {
                "message": "Stocks retrieved successfully",
                "data": [{"symbol": stock.symbol, "id": stock.id} for stock in stocks]
            }
        except Exception as e:
            self.logger.error(f"Error getting all stocks: {str(e)}\n{traceback.format_exc()}")
            raise e

    def get_research(self, symbol: str) -> Dict[str, Any]:
        """Get all research for a stock"""
        try:
            research_entries = self.db_manager.get_research_by_symbol(symbol)
            data = [{
                "id": entry.id,
                "symbol": entry.stock.symbol,
                "created_at": entry.created_at
            } for entry in research_entries]
            return {
                "message": f"Research for {symbol} retrieved successfully",
                "data": data
            }
        except Exception as e:
            self.logger.error(f"Error getting research for {symbol}: {str(e)}{traceback.format_exc()}")
            raise e

    def get_research_report(self, research_id: int) -> Dict[str, Any]:
        """Get a research report by its ID"""
        try:
            research = self.db_manager.get_research_by_id(research_id)
            if not research:
                return {"message": "Research not found", "data": ""}

            report_part_technical = None
            # Use get_dayof_technical to get technical for the same day as research
            technical_entry = self.db_manager.get_dayof_technical(research.stock, research.created_at.date())
            if technical_entry:
                report_part_technical = technical_entry.technical
            report_parts = [
                f"# {research.stock.symbol} Research Report\n",
                f"\n**Date:** {research.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n",
                "\n## Technical Analysis\n",
                report_part_technical or "No technical analysis available.",
                "\n## Market Analysis\n",
                research.market or "No market analysis available.",
                "\n## News Analysis\n",
                research.news or "No news analysis available.",
                "\n## Recommendation\n",
                research.recommendation or "No recommendation available."
            ]
            report = "".join(report_parts)

            return {
                "message": "Research report retrieved successfully",
                "data": report
            }
        except Exception as e:
            self.logger.error(f"Error getting research report for id {research_id}: {str(e)}{traceback.format_exc()}")
            raise e

    async def analyze_stock(self, symbol: str) -> Dict[str, Any]:
        """Analyze a stock and store results in database"""
        try:
            # Get or create stock in database
            stock = self.db_manager.get_or_create_stock(symbol)

            # Get latest technical analysis
            ta = self.db_manager.get_latest_technical(stock)

            # Get analysis from FundamentalGraph (async)
            graph_result = await self.fundamental_graph.analyze_stock(symbol=symbol, technical=ta)
            results = graph_result["results"]
            usage = graph_result.get("usage", {})
            results_str = self.fundamental_graph.get_report_str(symbol, results)
            results_structured_output = json.dumps(results.get("structured_data", {}), indent=2, default=str)
            # Save to database
            research = self.db_manager.create_research(
                stock=stock,
                market=results.get("market", {}).get("analysis", "N/A"),
                dividend=results.get("dividend", {}).get("analysis", "N/A"),
                news=results.get("news", {}).get("analysis", "N/A"),
                recommendation=results.get("recommendation"),
                structured_output=results_structured_output
            )

            # Save historical values if available
            structured_data = results.get("structured_data", {})
            if structured_data:
                self._save_historical_values(stock, structured_data)

            # Save usage metadata
            self.save_usage_metadata(symbol, usage)

            # Save reports
            # TODO: Add a setting to export reports. Create an /output container directory
            #self.stock_advisor.save_report(symbol, results_str)
            #self.stock_advisor.save_report(symbol, results.get("structured_data", {}), report_type='json')

            return {
                "message": "Analysis completed successfully",
                "data": results.get("structured_data", {}),
                "usage": usage
            }
        except Exception as e:
            self.logger.error(f"Error analyzing stock: {str(e)}\n{traceback.format_exc()}")
            raise e

    def save_usage_metadata(self, symbol: str, usage: dict):
        """Save token usage and API usage for each graph node using the database."""
        if not usage:
            self.logger.info(f"No usage metadata to save for {symbol}.")
            return
        for node, node_usage in usage.items():
            token_usage = node_usage.get("token_usage")
            if token_usage:
                input_tokens = token_usage.get("input_tokens", 0)
                output_tokens = token_usage.get("output_tokens", 0)
                total_tokens = token_usage.get("total_tokens", 0)
                self.db_manager.save_token_usage(
                    step=f"{symbol}:{node}",
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens
                )
            api_usage = node_usage.get("api_usage")
            if api_usage is not None:
                for provider, count in api_usage.items():
                    if count is not None:
                        ApiRequestUsage.create(
                            step=f"{symbol}:{node}",
                            provider=provider,
                            count=count
                        )
            self.logger.info(f"Usage for {symbol} - {node}: {json.dumps(node_usage, default=str)}")

    async def compare_stocks(self, symbols: List[str]) -> Dict[str, Any]:
        """Compare multiple stocks and store results"""
        try:
            if len(symbols) < 2:
                raise ValueError("At least two symbols are required for comparison")

            # Get or create stocks in database
            stocks = [self.db_manager.get_or_create_stock(symbol) for symbol in symbols]


            # Get comparison from FundamentalGraph (async)
            comparison = await self.fundamental_graph.compare_stocks(symbols)
            comparison_str = comparison["comparison"]

            # Save report
            self.fundamental_graph.save_report('-'.join(symbols), comparison_str)

            return {
                "message": "Comparison completed successfully",
                "data": {"comparison": comparison_str},
                "token_usage": comparison["token_usage"]
            }
        except Exception as e:
            self.logger.error(f"Error comparing stocks: {str(e)}\n{traceback.format_exc()}")
            raise e


    def _save_historical_values(self, stock: Stock, data: Dict[str, Any]) -> None:
        """Save historical values from structured data"""
        try:
            historical_data = {
                "stock": stock,
                "report_date": date.today(),
                "final_recommendation": data.get("final_recommendation"),
                "final_confidence_score": data.get("final_confidence_score"),
                "pe_ratio": data.get("pe_ratio"),
                "revenue_growth_yoy": data.get("revenue_growth"),
                "eps_growth_yoy": data.get("eps_growth_yoy"),
                "net_profit_margin": data.get("profit_margin"),
                "free_cash_flow": data.get("free_cash_flow"),
                "debt_to_equity_ratio": data.get("debt_to_equity"),
                "analyst_consensus_rating": data.get("analyst_consensus"),
                "low_price_target": data.get("low_price_target"),
                "high_price_target": data.get("high_price_target"),
                "price_target_percent": data.get("price_target_percent")
            }
            # Filter out None values
            historical_data = {k: v for k, v in historical_data.items() if v is not None}
            self.db_manager.create_historical_values(**historical_data)
        except Exception as e:
            # Log error but don't raise it to avoid interrupting the main flow
            self.logger.error(f"Error saving historical values: {str(e)}\n{traceback.format_exc()}")

    #
    # Technical
    #
    async def analyze_technical(self, symbol: str) -> Dict[str, Any]:
        """Analyze technicals for a stock and store results in database"""
        try:
            # Get or create stock in database
            stock = self.db_manager.get_or_create_stock(symbol)

            # Get analysis from TechnicalAnalysisGraph (async)
            graph_result = await self.technical_graph.analyze_technical(symbol, self.llm, YFinanceProvider(symbol))
            results = graph_result["results"] if "results" in graph_result else graph_result
            usage = graph_result.get("usage", {})

            # Save to database (store structured_output as dict, not JSON string)
            technical = self.db_manager.create_technical(
                stock=stock,
                technical=results.get("analysis", "N/A"),
                structured_output=results.get("structured_data", results)
            )

            # Save technical historical values if available (follow research pattern)
            structured_data = results.get("structured_data", {})
            if structured_data:
                self._save_technical_values(stock, structured_data)

            # Save usage metadata
            self.save_usage_metadata(symbol, usage)

            return {
                "message": "Technical analysis completed successfully",
                "data": results,
                "usage": usage
            }
        except Exception as e:
            self.logger.error(f"Error analyzing technicals: {str(e)}\n{traceback.format_exc()}")
            raise e

    def _save_technical_values(self, stock: Stock, data: Dict[str, Any]) -> None:
        """Save technical historical values from structured data"""
        try:
            technical_data = {
                "stock": stock,
                "report_date": date.today(),
                "close_price": data.get("current_price"),
                "volume": data.get("volume"),
                "sma_20": data.get("sma_20"),
                "sma_50": data.get("sma_50"),
                "sma_200": data.get("sma_200"),
                "rsi": data.get("rsi")
            }
            # Filter out None values
            technical_data = {k: v for k, v in technical_data.items() if v is not None}
            self.db_manager.create_technical_historical_values(**technical_data)
        except Exception as e:
            self.logger.error(f"Error saving technical values: {str(e)}\n{traceback.format_exc()}")

    def get_technical_analyses(self, symbol: str) -> Dict[str, Any]:
        """Get all technical analyses for a stock"""
        try:
            stock = self.db_manager.get_or_create_stock(symbol)
            technical_entries = self.db_manager.get_technical_by_symbol(symbol)
            data = [
                {
                    "id": entry.id,
                    "symbol": stock.symbol,
                    "created_at": entry.created_at
                }
                for entry in technical_entries
            ]
            return {
                "message": f"Technical analyses for {symbol} retrieved successfully",
                "data": data
            }
        except Exception as e:
            self.logger.error(f"Error getting technical analyses for {symbol}: {str(e)}\n{traceback.format_exc()}")
            raise e

    def get_technical_report(self, technical_id: int) -> Dict[str, Any]:
        """Get a technical analysis report by its ID"""
        try:
            technical = self.db_manager.get_technical_by_id(technical_id)
            if not technical:
                return {"message": "Technical analysis not found", "data": ""}

            report_parts = [
                f"# {technical.stock.symbol} Technical Analysis Report\n",
                f"\n**Date:** {technical.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n",
                "\n## Technical Analysis\n",
                technical.technical or "No technical analysis available."
            ]
            report = "".join(report_parts)
            return {
                "message": "Technical analysis report retrieved successfully",
                "data": report
            }
        except Exception as e:
            self.logger.error(f"Error getting technical report for id {technical_id}: {str(e)}\n{traceback.format_exc()}")
            raise e
        
    #
    # Portfolio
    #
    def add_transaction(self, txn_req):
        stock = db_manager.get_or_create_stock(txn_req.symbol)
        txn = db_manager.create_transaction(
            stock=stock,
            action=txn_req.action,
            shares=txn_req.shares,
            price=txn_req.price,
            purchase_date=txn_req.purchase_date
        )
        return {
            "id": txn.id,
            "symbol": stock.symbol,
            "action": txn.action,
            "shares": txn.shares,
            "price": txn.price,
            "purchase_date": str(txn.purchase_date)
        }

    def get_transactions(self, symbol: str = None):
        if symbol:
            txns = db_manager.get_transactions_by_symbol(symbol)
        else:
            txns = list(db_manager.get_all_transactions())
        return [
            {
                "id": t.id,
                "symbol": t.stock.symbol,
                "action": t.action,
                "shares": t.shares,
                "price": t.price,
                "purchase_date": str(t.purchase_date)
            } for t in txns
        ]

    def get_transaction(self, transaction_id: int):
        t = db_manager.get_transaction_by_id(transaction_id)
        if t:
            return {
                "id": t.id,
                "symbol": t.stock.symbol,
                "action": t.action,
                "shares": t.shares,
                "price": t.price,
                "purchase_date": str(t.purchase_date)
            }
        return None

    def delete_transaction(self, transaction_id: int):
        return db_manager.delete_transaction(transaction_id)

    def get_portfolio(self):
        """Summarize all transactions into a comprehensive portfolio table"""
        txns = self.get_transactions(None)
        # Summarize by symbol
        portfolio = {}
        for t in txns:
            sym = t['symbol']
            if sym not in portfolio:
                portfolio[sym] = {
                    'symbol': sym,
                    'shares': 0.0,
                    'avg_cost': 0.0,
                    'total_cost': 0.0,
                    'buys': 0.0,
                    'sells': 0.0,
                    'dividends': 0.0
                }
            if t['action'] == 'BUY':
                portfolio[sym]['shares'] += t['shares']
                portfolio[sym]['total_cost'] += t['shares'] * t['price']
                portfolio[sym]['buys'] += t['shares']
            elif t['action'] == 'SELL':
                portfolio[sym]['shares'] -= t['shares']
                portfolio[sym]['sells'] += t['shares']
            elif t['action'] == 'DIVIDEND_REINVESTMENT':
                portfolio[sym]['shares'] += t['shares']
                portfolio[sym]['dividends'] += t['shares'] * t['price']
        # Calculate average cost and round total_cost for each symbol
        for sym, row in portfolio.items():
            # Round total_cost to 2 decimal places
            row['total_cost'] = round(row['total_cost'], 2)
            if row['shares'] > 0:
                row['avg_cost'] = round(row['total_cost'] / (row['buys'] + row['dividends']/row['avg_cost'] if row['avg_cost'] else row['buys']), 2) if (row['buys'] + row['dividends']) else 0.0
            else:
                row['avg_cost'] = 0.0
        # Return as a list of dicts for table rendering
        return list(portfolio.values())

    async def analyze_portfolio(self, summaries: list, portfolio: list, cash_balance: float = 0) -> dict:
        """Run portfolio-level analysis using summaries, portfolio holdings, and cash balance"""
        try:
            results = await self.portfolio_graph.analyze_portfolio(summaries, portfolio, cash_balance)
            # Save to PortfolioResearch table using the singleton db_manager
            self.db_manager.create_portfolio_research(
                dca_analysis=results.get("dca_analysis"),
                portfolio_analysis=results.get("portfolio_analysis")
            )
            return {
                "message": "Portfolio analysis completed successfully",
                "data": results
            }
        except Exception as e:
            self.logger.error(f"Error analyzing portfolio: {str(e)}\n{traceback.format_exc()}")
            raise e

    #
    # Usage Tracking
    #   
    def get_provider_usage(self, provider: str = None, start_date: str = None, end_date: str = None) -> list:
        """List API usage records for a provider and date range."""
        from datetime import datetime, time
        query = ApiRequestUsage.select()
        if provider:
            query = query.where(ApiRequestUsage.provider == provider)
        if start_date:
            start_dt = datetime.combine(datetime.strptime(start_date, "%Y-%m-%d").date(), time.min)
            query = query.where(ApiRequestUsage.created_at >= start_dt)
        if end_date:
            end_dt = datetime.combine(datetime.strptime(end_date, "%Y-%m-%d").date(), time.max)
            query = query.where(ApiRequestUsage.created_at <= end_dt)
        records = list(query)
        return [
            {
                "id": r.id,
                "provider": r.provider,
                "count": r.count,
                "created_at": str(r.created_at)
            }
            for r in records
        ]

    def get_token_usage(self, start_date: str = None, end_date: str = None) -> list:
        """List token usage records for LLM calls in a date range."""
        dbm = self.db_manager
        return dbm.get_token_usage(start_date=start_date, end_date=end_date)
    
    def get_provider_usage_summary(self, provider: str) -> dict:
        """Return a dict with total and average API calls for a provider from midnight to now."""
        now = datetime.now()
        midnight = datetime.combine(now.date(), time.min)
        self.logger.info(f"Getting API usage for {provider} from {midnight} to {now}")
        query = (ApiRequestUsage
                 .select()
                 .where(
                     (ApiRequestUsage.provider == provider) &
                     (ApiRequestUsage.created_at >= midnight) &
                     (ApiRequestUsage.created_at <= now)
                 ))
        records = list(query)
        total = sum([r.count for r in records])
        avg = total / len(records) if records else 0
        usage = {"total": total, "average": avg}
        self.logger.info(f"API usage for {provider}: {usage}")
        return usage

    #
    # Scheduled Reports
    #
    async def daily_stock_report(self, max_api_calls=25):
        portfolio = self.get_portfolio()
        dbm = self.db_manager
        provider = "alphavantage"  # Change if using a different provider
        usage = self.get_provider_usage_summary(provider)
        total_calls = usage["total"]
        avg_calls = usage["average"]
        self.logger.info(f"Starting daily stock report. API usage for {provider}: total={total_calls}, average={avg_calls}")
        for holding in portfolio:
            symbol = holding["symbol"]
            stock = dbm.get_or_create_stock(symbol)
            latest_research = dbm.get_latest_research(stock)
            last_date = latest_research.created_at if latest_research else None
            # Only analyze if not updated in last 7 days or no reports exist
            if not last_date or (datetime.now() - last_date).days > 7:
                self.logger.info(f"Checking {symbol}: last report date = {last_date}")
                # Use average calls per record as estimate for this symbol
                if total_calls + avg_calls <= max_api_calls:
                    self.logger.info(f"Analyzing {symbol}. Current API usage: total={total_calls}, average={avg_calls}")
                    await self.analyze_stock(symbol)
                    usage = self.get_provider_usage_summary(provider)
                    total_calls = usage["total"]
                    avg_calls = usage["average"]
                    self.logger.info(f"Post-analysis API usage for {provider}: total={total_calls}, average={avg_calls}")
                else:
                    self.logger.warning(f"API limit reached for {provider}. Stopping daily stock report.")
                    break

    async def monthly_portfolio_analysis(self):
        portfolio = self.get_portfolio()
        dbm = self.db_manager
        self.logger.info("Starting monthly portfolio analysis.")
        summaries = []
        for holding in portfolio:
            stock = dbm.get_or_create_stock(holding["symbol"])
            latest_research = dbm.get_latest_research(stock)
            if latest_research and latest_research.recommendation:
                self.logger.info(f"{holding['symbol']}: recommendation found.")
                summaries.append(latest_research.recommendation)
            else:
                self.logger.info(f"{holding['symbol']}: no recommendation found.")
                summaries.append(f"No recommendation for {holding['symbol']}")
        cash_balance = dbm.get_current_cash_balance()
        self.logger.info(f"Portfolio cash balance: ${cash_balance}")
        result = await self.analyze_portfolio(summaries, portfolio, cash_balance)
        self.logger.info(f"Monthly portfolio analysis complete. Result: {result}")