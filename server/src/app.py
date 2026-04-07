import asyncio
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
from graphs.swing import SwingTradeGraph
from providers.yfinance import YFinanceProvider
from providers.alphavantage import AlphaVantageProvider
from scheduler import Scheduler
from services.database import Stock, Research, HistoricalValues
from utils.logging import setup_logger
from utils.email import send_via_gmail
from models.models import ApiRequestUsage, StockSplit
from services.database import DatabaseManager

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

        self.db_manager = DatabaseManager()  # Create a new instance
        # self.stock_advisor = StockAdvisor(db_manager=self.db_manager)
        self.logger = setup_logger("stock_app")
        # Initialize all graphs
        self.llm = self.setup_llm()
        self.yfinance_provider = YFinanceProvider()
        self.alphavantage_provider = AlphaVantageProvider() 
        self.fundamental_graph = FundamentalGraph(llm=self.llm, yfinance_provider=self.yfinance_provider, alphavantage_provider=self.alphavantage_provider)
        self.technical_graph = TechnicalAnalysisGraph(llm=self.llm, yfinance_provider=self.yfinance_provider, alphavantage_provider=self.alphavantage_provider)
        self.swing_graph = SwingTradeGraph(llm=self.llm, yfinance_provider=self.yfinance_provider, alphavantage_provider=self.alphavantage_provider)
        self.portfolio_graph = PortfolioGraph(llm=self.llm)

        # Initialize and start the scheduler
        self.scheduler = Scheduler(app=self)
        self.scheduler.start()

        self._initialized = True

    # Initialize the ollama endpoint
    def setup_llm(self):
        return ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            temperature=0, # Set temperature to 0 for reasoning tasks, higher (0.7-1.0) for creative tasks
            max_retries=2,
            api_key=os.getenv("GEMINI_API_KEY"),
        )

    def add_stock(self, symbol: str) -> Dict[str, Any]:
        """Add a new stock to the database"""
        try:
            with self.db_manager.get_connection():
                stock, created = self.db_manager.get_or_create_stock(symbol)
            if created:
                # Fetch splits and update if new stock (DB access inside update_stock_splits is protected)
                splits, _ = self.alphavantage_provider.get_splits(symbol)
                self.update_stock_splits(symbol, splits)
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
            with self.db_manager.get_connection():
                stocks = self.db_manager.get_all_stocks()
            return {
                "message": "Stocks retrieved successfully",
                "data": [{"symbol": stock.symbol, "id": stock.id} for stock in stocks]
            }
        except Exception as e:
            self.logger.error(f"Error getting all stocks: {str(e)}\n{traceback.format_exc()}")
            raise e
        
    def update_stock_splits(self, symbol, splits):
        """Update StockSplit table for a given symbol and list of splits."""
        dbm = self.db_manager
        # Protect DB reads/writes with connection context
        with self.db_manager.get_connection():
            stock_obj = dbm.get_stock_by_symbol(symbol)
        if stock_obj:
            for split in splits:
                try:
                    effective_date = split.get("effective_date")
                    split_factor = split.get("split_factor")
                    if not effective_date or not split_factor:
                        continue
                    # Convert split_factor to float
                    split_factor = float(split_factor)
                    # Check if split already exists (perform under connection)
                    with self.db_manager.get_connection():
                        exists = StockSplit.select().where(
                            (StockSplit.stock == stock_obj) &
                            (StockSplit.effective_date == effective_date)
                        ).exists()
                        if not exists:
                            StockSplit.create(
                                stock=stock_obj,
                                effective_date=effective_date,
                                split_factor=split_factor
                            )
                except Exception as e:
                    self.logger.error(f"Error saving split for {symbol} on {effective_date}: {e}")

    def get_research(self, symbol: str) -> Dict[str, Any]:
        """Get all research for a stock"""
        try:
            with self.db_manager.get_connection():
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
            with self.db_manager.get_connection():
                research = self.db_manager.get_research_by_id(research_id)
            if not research:
                return {"message": "Research not found", "data": ""}

            report = {
                "id": research.id,
                "type": "stock",
                "symbol": research.stock.symbol if hasattr(research, 'stock') and research.stock else None,
                "created_at": research.created_at.strftime("%Y-%m-%d %H:%M:%S") if hasattr(research, 'created_at') and research.created_at else None,
                "market": getattr(research, 'market', None),
                "dividend": getattr(research, 'dividend', None),
                "news": getattr(research, 'news', None),
                "technical": getattr(research, 'technical', None),
                "recommendation": getattr(research, 'recommendation', None)
            }
            return {
                "message": "Research report retrieved successfully",
                "data": report
            }
        except Exception as e:
            self.logger.error(f"Error getting research report for id {research_id}: {str(e)}{traceback.format_exc()}")
            raise e

    def save_usage_metadata(self, source: str, usage: dict):
        """Save token usage and API usage for each graph node using the database."""
        if not usage:
            self.logger.info(f"No usage metadata to save for {source}.")
            return
        for node, node_usage in usage.items():
            token_usage = node_usage.get("token_usage")
            if token_usage:
                input_tokens = token_usage.get("input_tokens", 0)
                output_tokens = token_usage.get("output_tokens", 0)
                total_tokens = token_usage.get("total_tokens", 0)
                self.db_manager.save_token_usage(
                    step=f"{source}:{node}",
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens
                )
            api_usage = node_usage.get("api_usage")
            if api_usage is not None:
                for provider, count in api_usage.items():
                    if count is not None:
                        ApiRequestUsage.create(
                            step=f"{source}:{node}",
                            provider=provider,
                            count=count
                        )
            self.logger.info(f"Usage for {source} - {node}: {json.dumps(node_usage, default=str)}")

    async def compare_stocks(self, symbols: List[str]) -> Dict[str, Any]:
        """Compare multiple stocks and store results"""
        try:
            if len(symbols) < 2:
                raise ValueError("At least two symbols are required for comparison")

            stocks = [self.db_manager.get_stock_by_symbol(symbol) for symbol in symbols]


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
            now = datetime.now()
            formatted_date = now.strftime('%Y-%m-%d %H:%M')
            historical_data = {
                "stock": stock,
                "final_recommendation": data.get("final_recommendation"),
                "final_confidence_score": data.get("final_confidence_score"),
                "pe_ratio": data.get("pe_ratio"),
                "revenue_growth_yoy": data.get("revenue_growth"),
                "eps_growth_yoy": data.get("eps_growth_yoy"),
                "net_profit_margin": data.get("profit_margin"),
                "free_cash_flow": data.get("free_cash_flow"),
                "debt_to_equity_ratio": data.get("debt_to_equity"),
                "news_sentiment_score": data.get("news_sentiment_score"),
                "analyst_consensus_rating": data.get("analyst_consensus"),
                "current_price": data.get("current_price"),
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

    def _compare_historical_values(self, stock: Stock) -> Optional[str]:
        """Compare the latest and previous HistoricalValues for a stock and return rendered HTML.

        Loads the latest `HistoricalValues` record and the immediately previous one (by created_at),
        computes differences for numeric fields, and returns an HTML string rendered from a
        template stored at `server/templates/historical_compare.html`.

        Returns:
            Rendered HTML string, or None if there is not enough historical data to compare.
        """
        try:
            # Get latest historical entry
            latest = self.db_manager.get_latest_historical_values(stock)
            if not latest:
                return None

            # Query previous record
            prev = self.db_manager.get_latest_historical_values(stock, before_date=latest.created_at)

            if not prev:
                return None

            # Only compare final_recommendation; if it changed, render template with requested fields
            prev_rec = getattr(prev, 'final_recommendation', None)
            latest_rec = getattr(latest, 'final_recommendation', None)

            # If recommendation didn't change, return None
            if prev_rec == latest_rec:
                return None

            # Prepare context values for template
            ctx = {
                'symbol': getattr(stock, 'symbol', 'N/A'),
                'date_latest': getattr(latest, 'created_at', ''),
                'date_prev': getattr(prev, 'created_at', ''),
                'prev_final_recommendation': prev_rec or '',
                'latest_final_recommendation': latest_rec or '',
                'prev_final_confidence_score': getattr(prev, 'final_confidence_score', ''),
                'latest_final_confidence_score': getattr(latest, 'final_confidence_score', ''),
                'prev_current_price': getattr(prev, 'current_price', ''),
                'latest_current_price': getattr(latest, 'current_price', ''),
                'prev_low_price_target': getattr(prev, 'low_price_target', ''),
                'latest_low_price_target': getattr(latest, 'low_price_target', ''),
                'prev_high_price_target': getattr(prev, 'high_price_target', ''),
                'latest_high_price_target': getattr(latest, 'high_price_target', ''),
                'prev_price_target_percent': getattr(prev, 'price_target_percent', ''),
                'latest_price_target_percent': getattr(latest, 'price_target_percent', ''),
            }

            # Load template from repo path
            # Use the requested relative template path
            tpl_path = os.path.join(os.path.dirname(__file__), 'templates', 'historical_compare.html')
            tpl_path = os.path.normpath(tpl_path)
            try:
                self.logger.info(f"Loading historical comparison template from {tpl_path}")
                with open(tpl_path, 'r', encoding='utf-8') as f:
                    tpl = f.read()
            except Exception as exc:
                # If template cannot be loaded, log and skip rendering
                self.logger.error(f"Could not load historical comparison template at {tpl_path}: {exc}")
                return None

            rendered = tpl.format(**ctx)
            return rendered
        except Exception as e:
            self.logger.error(f"Error comparing historical values: {e}\n{traceback.format_exc()}")
            return None

    #
    # Technical
    #
    async def analyze_technical(self, symbol: str) -> Dict[str, Any]:
        """Analyze technicals for a stock and store results in database"""
        try:
            stock = self.db_manager.get_stock_by_symbol(symbol)

            # Get analysis from TechnicalAnalysisGraph (async)
            graph_result = await self.technical_graph.analyze_technical(symbol, self.llm)
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
            stock = self.db_manager.get_stock_by_symbol(symbol)
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
    def add_transaction(self, txn_req, portfolio_id: int):
        stock, created = self.db_manager.get_or_create_stock(symbol=txn_req.symbol)
        if not stock or not getattr(stock, 'symbol', None):
            self.logger.error(f"Failed to create or retrieve stock for symbol: {getattr(txn_req, 'symbol', None)}. Stock object: {stock}")
            raise ValueError(f"Could not create or retrieve stock for symbol: {getattr(txn_req, 'symbol', None)}")
        if created:
            splits, _ = self.alphavantage_provider.get_splits(txn_req.symbol)
            self.update_stock_splits(txn_req.symbol, splits)
        txn = self.db_manager.create_transaction(
            stock=stock,
            portfolio_id=portfolio_id,
            action=txn_req.action,
            shares=txn_req.shares,
            price=txn_req.price, 
            purchase_date=txn_req.purchase_date
        )
        return {
            "id": txn.id,
            "symbol": stock.symbol,
            "portfolio_id": portfolio_id,
            "action": txn.action,
            "shares": txn.shares,
            "price": txn.price,
            "purchase_date": str(txn.purchase_date)
        }

    def get_transactions(self, portfolio_id: int = None, symbol: str = None):
        if symbol:
            txns = self.db_manager.get_transactions_by_symbol(symbol=symbol, portfolio_id=portfolio_id)
        else:
            txns = list(self.db_manager.get_all_transactions(portfolio_id=portfolio_id))
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
        t = self.db_manager.get_transaction_by_id(transaction_id)
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

    def delete_transaction(self, transaction_id: int, portfolio_id: int):
        return self.db_manager.delete_transaction(transaction_id=transaction_id, portfolio_id=portfolio_id)

    def get_portfolio_holdings(self, portfolio_id: int):
        """Summarize all transactions into a comprehensive portfolio table, adjusting for stock splits."""
        txns = self.get_transactions(portfolio_id=portfolio_id)
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
            # Adjust shares and price for splits
            stock = self.db_manager.get_stock_by_symbol(sym)
            splits = []
            if stock:
                splits = list(StockSplit.select().where(
                    (StockSplit.stock == stock) &
                    (StockSplit.effective_date > t['purchase_date'])
                ).order_by(StockSplit.effective_date))
            split_factor = 1.0
            for split in splits:
                try:
                    split_factor *= float(split.split_factor)
                except Exception:
                    continue
            adj_shares = t['shares'] * split_factor
            adj_price = t['price'] / split_factor if split_factor != 0 else t['price']
            if t['action'] == 'BUY':
                portfolio[sym]['shares'] += adj_shares
                portfolio[sym]['total_cost'] += adj_shares * adj_price
                portfolio[sym]['buys'] += adj_shares
            elif t['action'] == 'SELL':
                portfolio[sym]['shares'] -= adj_shares
                portfolio[sym]['sells'] += adj_shares
            elif t['action'] == 'DIVIDEND_REINVESTMENT':
                portfolio[sym]['shares'] += adj_shares
                portfolio[sym]['dividends'] += adj_shares * adj_price
        # Calculate average cost and round total_cost for each symbol
        for sym, row in portfolio.items():
            # Round total_cost and shares to 2 decimal places
            row['total_cost'] = round(row['total_cost'], 2)
            row['shares'] = round(row['shares'], 2)
            if row['shares'] > 0:
                row['avg_cost'] = round(row['total_cost'] / (row['buys'] + row['dividends']/row['avg_cost'] if row['avg_cost'] else row['buys']), 2) if (row['buys'] + row['dividends']) else 0.0
            else:
                row['avg_cost'] = 0.0
        # Return as a list of dicts for table rendering
        return list(portfolio.values())

    def get_portfolio_holdings_combined(self, portfolio_id: int):
        """Return portfolio holdings with latest historical values for each symbol."""
        holdings = self.get_portfolio_holdings(portfolio_id=portfolio_id)
        combined = []
        for h in holdings:
            symbol = h["symbol"]
            stock = self.db_manager.get_stock_by_symbol(symbol)
            # Add latest close, volume, and data_updated_at from Stock table
            if stock:
                h['close'] = stock.close
                h['volume'] = stock.volume
                h['data_updated_at'] = stock.data_updated_at
            # Calculate gain_loss if close and avg_cost are available
            gain_loss = None
            try:
                close = h.get('close')
                avg_cost = h.get('avg_cost')
                shares = h.get('shares')
                if close is not None and avg_cost is not None and shares is not None:
                    gain_loss = round((close - avg_cost) * shares, 2)
            except Exception:
                gain_loss = None
            hist = self.db_manager.get_latest_historical_values(stock)
            hist_data = None
            if hist:
                hist_data = {
                    "created_at": hist.created_at,
                    "final_recommendation": hist.final_recommendation.upper(),
                    "final_confidence_score": hist.final_confidence_score,
                    "analyst_consensus_rating": hist.analyst_consensus_rating,
                    "low_price_target": hist.low_price_target,
                    "high_price_target": hist.high_price_target,
                    "price_target_percent": hist.price_target_percent
                }
            combined.append({**h, "historical": hist_data, "gain_loss": gain_loss})
        return combined

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
                "step": r.step,
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
    # Scheduler
    #
    def get_scheduled_jobs(self) -> list:
        """Return a list of all scheduled jobs with their details."""
        jobs = self.scheduler.get_all_jobs()
        job_list = []
        for job in jobs:
            job_list.append({
                'id': job.id,
                'name': job.name,
                'next_run_time': str(job.next_run_time),
                'trigger': str(job.trigger),
                'func_ref': str(job.func_ref),
                'args': job.args,
                'kwargs': job.kwargs
            })
        return job_list
    
    def trigger_job(self, job_id: str) -> bool:
        """Trigger a scheduled job to run immediately by job_id."""
        return self.scheduler.trigger_job_now(job_id)

    #
    # Scheduled Reports
    #
    async def sync_stock_splits(self, max_api_calls=25):
        """
        Fetch and sync stock splits for all symbols in all portfolios using AlphaVantageProvider.
        Respects API usage limits and saves usage metadata.
        """
        self.logger.info("Starting sync for stock splits...")
        dbm = self.db_manager
        provider = "alphavantage"
        with self.db_manager.get_connection():
            portfolios = dbm.get_portfolios()
        symbols_set = set()
        for portfolio in portfolios:
            holdings = self.get_portfolio_holdings(portfolio_id=portfolio.id)
            for holding in holdings:
                symbol = holding.get('symbol')
                if symbol:
                    symbols_set.add(symbol)
        symbols = list(symbols_set)
        with self.db_manager.get_connection():
            total_calls = self.get_provider_usage_summary(provider)["total"]
        usage = {}
        for symbol in symbols:
            with self.db_manager.get_connection():
                stock_obj = self.db_manager.get_stock_by_symbol(symbol)
            # Skip if splits_updated_at greater than 30 days
            if stock_obj and stock_obj.splits_updated_at:
                try:
                    days_since_update = (datetime.now() - stock_obj.splits_updated_at).days
                    if days_since_update > 30:
                        self.logger.info(f"Skipping {symbol}: splits updated {days_since_update} days ago.")
                        continue
                except Exception as e:
                    self.logger.warning(f"Error checking splits_updated_at for {symbol}: {e}")
            if total_calls + 1 > max_api_calls:
                self.logger.warning(f"API limit reached for {provider}. Stopping sync for stock splits.")
                break
            splits, request_count = self.alphavantage_provider.get_splits(symbol)
            self.update_stock_splits(symbol, splits)
            # Update splits_updated_at in Stock table
            if stock_obj:
                try:
                    with self.db_manager.get_connection():
                        stock_obj.splits_updated_at = datetime.now()
                        stock_obj.save()
                except Exception:
                    # If saving the timestamp fails, continue; split data is already stored
                    self.logger.warning(f"Failed to update splits_updated_at for {symbol}")
            usage[symbol] = {"api_usage": {provider: request_count}}
            total_calls += request_count
        self.save_usage_metadata("sync_stock_splits", usage)

    async def get_latest_prices(self) -> Dict[str, dict]:
        """
        Fetch the most recent OHLCV data for each symbol using yfinance.
        Returns a dict mapping symbol to its latest OHLCV data.
        """
        self.logger.info("Fetching latest OHLCV data for all symbols...")
        # Gather all unique symbols from all portfolios
        with self.db_manager.get_connection():
            portfolios = self.db_manager.get_portfolios()
        symbols_set = set()
        for portfolio in portfolios:
            holdings = self.get_portfolio_holdings(portfolio_id=portfolio.id)
            for holding in holdings:
                symbol = holding.get('symbol')
                if symbol:
                    symbols_set.add(symbol)
        symbols = list(symbols_set)
        hist = await self.yfinance_provider.get_stock_history_by_symbols_async(symbols, period='1d', interval='1d')
        latest_prices = {}
        for symbol in symbols:
            try:
                # Get the index (date/time) of the last row
                last_idx = hist["Open"][symbol].index[-1]
                ohlcv = {
                    "open": float(hist["Open"][symbol].iloc[-1]),
                    "high": float(hist["High"][symbol].iloc[-1]),
                    "low": float(hist["Low"][symbol].iloc[-1]),
                    "close": float(hist["Close"][symbol].iloc[-1]),
                    "volume": int(hist["Volume"][symbol].iloc[-1]),
                    "datetime": str(last_idx)
                }
                latest_prices[symbol] = ohlcv
                # Update Stock table with close, volume, and data_updated_at
                with self.db_manager.get_connection():
                    stock_obj = self.db_manager.get_stock_by_symbol(symbol)
                    if stock_obj:
                        stock_obj.close = ohlcv["close"]
                        stock_obj.volume = ohlcv["volume"]
                        stock_obj.data_updated_at = datetime.fromisoformat(str(last_idx)) if hasattr(datetime, 'fromisoformat') else str(last_idx)
                        stock_obj.save()
            except Exception as e:
                self.logger.warning(f"Could not fetch latest OHLCV for {symbol}: {e}")
                latest_prices[symbol] = None
        return latest_prices
    
    async def daily_stock_report(self, max_api_calls=25):
        dbm = self.db_manager
        provider = "alphavantage"  # Change if using a different provider
        with self.db_manager.get_connection():
            portfolios = dbm.get_portfolios()
        for portfolio in portfolios:
            self.logger.info(f"Starting daily stock report for portfolio: {portfolio.name} (id={portfolio.id})")
            holdings = self.get_portfolio_holdings(portfolio_id=portfolio.id)
            if not holdings or len(holdings) == 0:
                self.logger.info(f"No holdings found for portfolio: {portfolio.name} (id={portfolio.id}), skipping.")
                continue
            with self.db_manager.get_connection():
                usage = self.get_provider_usage_summary(provider)
            total_calls = usage["total"]
            avg_calls = usage["average"]
            self.logger.info(f"API usage for {provider}: total={total_calls}, average={avg_calls}")
            for holding in holdings:
                symbol = holding["symbol"]
                stock = dbm.get_stock_by_symbol(symbol)
                latest_research = dbm.get_latest_research(stock)
                last_date = latest_research.created_at if latest_research else None
                # Only analyze if not updated in last 7 days or no reports exist
                if not last_date or (datetime.now() - last_date).days > 7:
                    self.logger.info(f"Checking {symbol}: last report date = {last_date}")
                    # Use average calls per record as estimate for this symbol
                    if total_calls + 4 <= max_api_calls:
                        self.logger.info(f"Analyzing {symbol}. Current API usage: total={total_calls}, average={avg_calls}")
                        await self.analyze_stock(symbol)
                        usage = self.get_provider_usage_summary(provider)
                        total_calls = usage["total"]
                        avg_calls = usage["average"]
                        self.logger.info(f"Post-analysis API usage for {provider}: total={total_calls}, average={avg_calls}")
                    else:
                        self.logger.warning(f"API limit reached for {provider}. Stopping daily stock report for this portfolio.")
                        break

    async def portfolio_analysis_all(self):
        """Run portfolio_analysis for each portfolio in the database."""
        dbm = self.db_manager
        with self.db_manager.get_connection():
            portfolios = dbm.get_portfolios()
        results = []
        for p in portfolios:
            portfolio_id = p.id
            self.logger.info(f"Running portfolio_analysis for portfolio_id={portfolio_id}")
            result = await self.portfolio_analysis(portfolio_id=portfolio_id)
            results.append({"portfolio_id": portfolio_id, "result": result})
            # Sleep to prevent rate limit
            await asyncio.sleep(60)
        return results
    
    #                    
    #  Analysis
    #
    async def analyze_stock(self, symbol: str) -> Dict[str, Any]:
        """Analyze a stock and store results in database"""
        try:
            stock = self.db_manager.get_stock_by_symbol(symbol)

            # Get analysis from FundamentalGraph (async) with error handling
            try:
                graph_result = await self.fundamental_graph.analyze_stock(symbol=symbol)
            except Exception as e:
                self.logger.error(f"Exception during graph execution for {symbol}: {str(e)}\n{traceback.format_exc()}")
                raise
            results = graph_result["results"]
            usage = graph_result.get("usage", {})
            results_str = self.fundamental_graph.get_report_str(symbol, results)
            results_structured_output = json.dumps(results.get("structured_data", {}), indent=2, default=str)
            # Combine all validate_ node results into a single string
            validate_sections = []
            for section in ["technical", "market", "dividend", "news"]:
                val = results.get(f"validate_{section}")
                if val:
                    validate_sections.append(f"[{section.upper()} VALIDATION]\n{val}")
            validate_combined = "\n\n".join(validate_sections) if validate_sections else None

            # Save to database
            research = self.db_manager.create_research(
                stock=stock,
                market=results.get("revised_market", {}).get("analysis", "N/A"),
                dividend=results.get("revised_dividend", {}).get("analysis", "N/A"),
                news=results.get("revised_news", {}).get("analysis", "N/A"),
                technical=results.get("revised_technical", {}).get("analysis", "N/A"),
                recommendation=results.get("recommendation"),
                structured_output=results_structured_output,
                validation=validate_combined
            )

            # Save historical values if available
            structured_data = results.get("structured_data", {})
            if structured_data:
                self._save_historical_values(stock, structured_data)
                compare = self._compare_historical_values(stock)
                if compare:
                    self.logger.info(f"Significant change detected for {symbol}, sending email alert.")
                    # Send email alert
                    subject = f"StockAdvisor Alert: {symbol} Recommendation Change"
                    body = f"The recommendation for {symbol} has changed.\n\n{compare}"
                    send_via_gmail(subject, body)

            # Save usage metadata
            source = f"stock:{symbol}"
            self.save_usage_metadata(source, usage)

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

    async def portfolio_analysis(self, portfolio_id: int):
        portfolio = self.db_manager.get_portfolio_by_id(portfolio_id=portfolio_id)
        holdings = self.get_portfolio_holdings(portfolio_id=portfolio_id)
        dbm = self.db_manager
        self.logger.info(f"Starting monthly portfolio analysis for portfolio {portfolio.name}.")
        summaries = []
        for holding in holdings:
            stock = dbm.get_stock_by_symbol(holding["symbol"])
            latest_research = dbm.get_latest_research(stock)
            if latest_research and latest_research.recommendation:
                self.logger.info(f"{holding['symbol']}: recommendation found.")
                summaries.append(latest_research.recommendation)
            else:
                self.logger.info(f"{holding['symbol']}: no recommendation found.")
                summaries.append(f"No recommendation for {holding['symbol']}")
        cash_balance = dbm.get_current_cash_balance(portfolio_id=portfolio_id)
        self.logger.info(f"Portfolio cash balance: ${cash_balance}")
        try:
            analysis = await self.portfolio_graph.analyze_portfolio(summaries=summaries, holdings=holdings, portfolio=portfolio, cash_balance=cash_balance)
            results = analysis.get("results", {})
            usage = analysis.get("usage", {})
            # Save to PortfolioResearch table using the singleton db_manager
            self.db_manager.create_portfolio_research(
                portfolio_id=portfolio_id,
                dca_analysis=results.get("dca_analysis"),
                economic_analysis=results.get("economic_analysis"),
                portfolio_analysis=results.get("portfolio_analysis")
            )
            source = f"portfolio:{portfolio.name}"
            self.save_usage_metadata(source=source, usage=usage)

            self.logger.info(f"Monthly portfolio analysis complete.")
            return {
                "message": "Portfolio analysis completed successfully",
                "data": results
            }
        except Exception as e:
            self.logger.error(f"Error analyzing portfolio: {str(e)}\n{traceback.format_exc()}")
            raise e

    async def swing_trade_analysis(self, symbol: str):
        self.logger.info(f"Starting swing trade analysis for {symbol}.")
        try:
            # Perform swing trade analysis
            latest_research = self.db_manager.get_latest_research_by_symbol(symbol)
            analysis = await self.swing_graph.analyze_swing_trade(symbol=symbol, research=latest_research)
            results = analysis.get("results", {})
            usage = analysis.get("usage", {})
            # Extract relevant fields for SwingResearch
            pattern_analysis = results.get("pattern_analysis", {}).get("analysis", "N/A")
            trade_recommendation = results.get("trade_recommendation", {}).get("analysis", "N/A")
            swing_trade_plan = results.get("swing_trade_plan")
            stock = self.db_manager.get_stock_by_symbol(symbol)

            self.db_manager.create_swing_trade_research(    
                stock=stock,
                pattern_analysis=pattern_analysis,
                trade_recommendation=trade_recommendation,
            )
            if swing_trade_plan:
                # Look up the Stock object by ticker (symbol)
                # Explicitly map fields to avoid passing extra keys
                self.db_manager.create_swing_trade_plan_history(
                    stock=stock,
                    direction=swing_trade_plan.get('direction'),
                    entry_price=swing_trade_plan.get('entry_price'),
                    stop_loss_price=swing_trade_plan.get('stop_loss_price'),
                    take_profit_price=swing_trade_plan.get('take_profit_price'),
                    risk_per_trade_usd=swing_trade_plan.get('risk_per_trade_usd'),
                    position_size=swing_trade_plan.get('position_size'),
                    risk_reward_ratio=swing_trade_plan.get('risk_reward_ratio'),
                    entry_reason=swing_trade_plan.get('entry_reason'),
                    exit_reason=swing_trade_plan.get('exit_reason')
                )
            source = f"swing:{symbol}"
            self.save_usage_metadata(source=source, usage=usage)

            self.logger.info(f"Swing trade analysis complete.")
            return {
                "message": "Swing trade analysis completed successfully",
                "data": results
            }
        except Exception as e:
            self.logger.error(f"Error analyzing swing trade: {str(e)}\n{traceback.format_exc()}")
            raise e