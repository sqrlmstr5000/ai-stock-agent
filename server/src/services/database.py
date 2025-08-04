import os
import json
from datetime import datetime, date
from importlib import util
from peewee import *
from playhouse.sqlite_ext import SqliteExtDatabase, JSONField
from playhouse.migrate import SqliteMigrator
from typing import Optional
from pathlib import Path
from services.migrations import get_migration_files
from utils.logging import setup_logger
from models.models import db, Stock, StockTransactionLog, TechnicalAnalysis, Research, HistoricalValues, TechnicalHistoricalValues, PortfolioResearch, CashBalance, TokenUsage, ApiRequestUsage

# Configure logging
logger = setup_logger(__name__)

MIGRATIONS_VERSION_TABLE = 'migrations_version'

class DatabaseManager:
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self._initialize()
            DatabaseManager._initialized = True

    def _initialize(self):
        """Initialize the database and run migrations"""
        logger.info("Initializing database...")
        db.connect()
        db.create_tables([Stock, StockTransactionLog, TechnicalAnalysis, Research, HistoricalValues, TechnicalHistoricalValues, PortfolioResearch, CashBalance, TokenUsage, ApiRequestUsage])
        db.close()
        self._run_migrations()

    def _run_migrations(self):
        """Run all pending database migrations"""
        logger.info("Checking for database migrations...")
        
        # Create migrations version table if it doesn't exist
        db.execute_sql(
            f'''CREATE TABLE IF NOT EXISTS {MIGRATIONS_VERSION_TABLE} (
                version INTEGER PRIMARY KEY,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )'''
        )
        
        current_version = self._get_current_version()
        logger.info(f"Current database version: {current_version}")
        
        migrator = SqliteMigrator(db)
        
        # Get all migration files
        migrations = get_migration_files()
        logger.info(f"Found {len(migrations)} migration files")
        
        for version, file_path in migrations:
            if version <= current_version:
                continue
                
            logger.info(f"Running migration {version} from {file_path}")
            
            try:
                # Import the migration module
                spec = util.spec_from_file_location(f"migration_{version}", file_path)
                module = util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                # Run the upgrade function
                with db.atomic():
                    module.upgrade(migrator)
                    self._set_version(version)
                    
                logger.info(f"Successfully applied migration {version}")
                
            except Exception as e:
                logger.error(f"Error applying migration {version}: {str(e)}")
                raise

    def _get_current_version(self):
        """Get the current database migration version"""
        try:
            cursor = db.execute_sql(
                f'SELECT version FROM {MIGRATIONS_VERSION_TABLE} ORDER BY version DESC LIMIT 1'
            )
            result = cursor.fetchone()
            return result[0] if result else 0
        except Exception:
            return 0

    def _set_version(self, version: int):
        """Set the current database migration version"""
        db.execute_sql(
            f'INSERT INTO {MIGRATIONS_VERSION_TABLE} (version) VALUES (?)',
            (version,)
        )

    def get_or_create_stock(self, symbol: str) -> Optional[Stock]:
        """Get or create a stock entry, returns None if creation fails"""
        try:
            stock, created = Stock.get_or_create(symbol=symbol.upper())
            if stock is not None:
                return stock
            else:
                logger.error(f"Failed to get or create stock for symbol: {symbol}")
                return None
        except Exception as e:
            logger.error(f"Exception in get_or_create_stock for symbol {symbol}: {e}")
            return None

    # --- TransactionLog Methods ---
    @staticmethod
    def create_transaction(
        stock: Stock,
        action: str,
        shares: float,
        price: float,
        purchase_date: date
    ) -> StockTransactionLog:
        """Create a new stock transaction log entry"""
        return StockTransactionLog.create(
            stock=stock,
            action=action,
            shares=shares,
            price=price,
            purchase_date=purchase_date
        )

    @staticmethod
    def get_transactions_by_symbol(symbol: str) -> list:
        """Get all transactions for a stock symbol"""
        stock = Stock.get_or_none(Stock.symbol == symbol.upper())
        if stock:
            return list(StockTransactionLog.select().where(StockTransactionLog.stock == stock).order_by(StockTransactionLog.purchase_date.desc()))
        return []

    @staticmethod
    def get_transaction_by_id(transaction_id: int) -> StockTransactionLog:
        """Get a transaction by its ID"""
        return StockTransactionLog.get_or_none(StockTransactionLog.id == transaction_id)

    @staticmethod
    def delete_transaction(transaction_id: int) -> bool:
        """Delete a transaction by its ID"""
        txn = StockTransactionLog.get_or_none(StockTransactionLog.id == transaction_id)
        if txn:
            txn.delete_instance()
            return True
        return False

    @staticmethod
    def get_all_stocks() -> list[Stock]:
        """Get all stocks from the database"""
        return list(Stock.select())

    #
    # Research
    #
    @staticmethod
    def create_research(
        stock: Stock,
        market: str = None,
        news: str = None,
        technical: str = None,
        dividend: str = None,
        recommendation: str = None,
        structured_output: dict = None
    ) -> Research:
        """Create a new research entry for a stock"""
        return Research.create(
            stock=stock,
            market=market,
            news=news,
            technical=technical,
            dividend=dividend,
            recommendation=recommendation,
            structured_output=structured_output
        )

    @staticmethod
    def get_latest_research(stock: Stock) -> Research:
        """Get the latest research entry for a stock"""
        return (Research
                .select()
                .where(Research.stock == stock)
                .order_by(Research.created_at.desc())
                .first())

    @staticmethod
    def get_research_history(stock: Stock, limit: int = 10) -> list:
        """Get research history for a stock"""
        return list(Research
                   .select()
                   .where(Research.stock == stock)
                   .order_by(Research.created_at.desc())
                   .limit(limit))
    
    @staticmethod
    def get_all_research_history_list(stock: Stock, limit: int = 9) -> list:
        """Get research history for a stock, selecting only id, symbol, created_at, and structured_output with parsed fields."""
        query = (Research
                 .select(Research.id, Research.stock, Research.created_at, Research.structured_output)
                 .order_by(Research.created_at.desc())
                 .limit(limit))
        results = []
        for entry in query:
            # Parse structured_output JSON and extract required fields
            so = entry.structured_output
            if isinstance(so, str):
                try:
                    so = json.loads(so)
                except Exception:
                    so = {}
            results.append({
                "id": entry.id,
                "symbol": entry.stock.symbol,
                "created_at": str(entry.created_at),
                "final_recommendation": so.get("final_recommendation"),
                "final_confidence_score": so.get("final_confidence_score"),
                "high_price_target": so.get("high_price_target"),
                "price_target_percent": so.get("price_target_percent")
            })
        return results

    @staticmethod
    def get_research_by_symbol(symbol: str) -> list:
        """Get all research entries for a stock symbol"""
        stock = Stock.get_or_none(Stock.symbol == symbol.upper())
        if stock:
            return list(Research
                       .select()
                       .where(Research.stock == stock)
                       .order_by(Research.created_at.desc()))
        return []

    @staticmethod
    def get_research_by_id(research_id: int) -> Optional[Research]:
        """Get a research entry by its ID"""
        return Research.get_or_none(Research.id == research_id)

    @staticmethod
    def update_research(research: Research, **kwargs) -> Research:
        """Update an existing research entry"""
        for key, value in kwargs.items():
            if hasattr(research, key):
                setattr(research, key, value)
        research.save()
        return research

    @staticmethod
    def create_historical_values(
        stock: Stock,
        report_date: date,
        final_recommendation: str = None,
        final_confidence_score: int = None,
        pe_ratio: Optional[float] = None,
        revenue_growth_yoy: Optional[float] = None,
        eps_growth_yoy: Optional[float] = None,
        net_profit_margin: Optional[float] = None,
        free_cash_flow: Optional[float] = None,
        debt_to_equity_ratio: Optional[float] = None,
        close_price: Optional[float] = None,
        volume: Optional[int] = None,
        sma_20: Optional[float] = None,
        sma_50: Optional[float] = None,
        sma_200: Optional[float] = None,
        rsi: Optional[float] = None,
        news_sentiment_score: Optional[float] = None,
        analyst_consensus_rating: Optional[str] = None,
        low_price_target: Optional[float] = None,
        high_price_target: Optional[float] = None,
        price_target_percent: Optional[float] = None
    ) -> HistoricalValues:
        """Create a new historical values entry for a stock"""
        return HistoricalValues.create(
            stock=stock,
            report_date=report_date,
            final_recommendation=final_recommendation,
            final_confidence_score=final_confidence_score,
            pe_ratio=pe_ratio,
            revenue_growth_yoy=revenue_growth_yoy,
            eps_growth_yoy=eps_growth_yoy,
            net_profit_margin=net_profit_margin,
            free_cash_flow=free_cash_flow,
            debt_to_equity_ratio=debt_to_equity_ratio,
            close_price=close_price,
            volume=volume,
            sma_20=sma_20,
            sma_50=sma_50,
            sma_200=sma_200,
            rsi=rsi,
            news_sentiment_score=news_sentiment_score,
            analyst_consensus_rating=analyst_consensus_rating,
            low_price_target=low_price_target,
            high_price_target=high_price_target,
            price_target_percent=price_target_percent
        )

    @staticmethod
    def get_historical_values(
        stock: Stock,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 100
    ) -> list:
        """Get historical values for a stock within a date range"""
        query = HistoricalValues.select().where(HistoricalValues.stock == stock)
        
        if start_date:
            query = query.where(HistoricalValues.report_date >= start_date)
        if end_date:
            query = query.where(HistoricalValues.report_date <= end_date)
            
        return list(query.order_by(HistoricalValues.report_date.desc()).limit(limit))

    @staticmethod
    def get_latest_historical_values(stock: Stock) -> Optional[HistoricalValues]:
        """Get the latest historical values for a stock"""
        return (HistoricalValues
                .select()
                .where(HistoricalValues.stock == stock)
                .order_by(HistoricalValues.report_date.desc())
                .first())

    #
    # TechnicalAnalysis 
    #
    @staticmethod
    def create_technical(
        stock: Stock,
        technical: str = None,
    ):
        """Create a new technical analysis entry for a stock"""
        return TechnicalAnalysis.create(
            stock=stock,
            technical=technical,
        )

    @staticmethod
    def get_latest_technical(stock: Stock):
        """Get the latest technical analysis entry for a stock"""
        return (
            TechnicalAnalysis
            .select()
            .where(TechnicalAnalysis.stock == stock)
            .order_by(TechnicalAnalysis.created_at.desc())
            .first()
        )

    @staticmethod
    def get_dayof_technical(stock: Stock, report_date: date):
        """Get the latest technical analysis entry for a stock on a specific day"""
        start_dt = datetime.combine(report_date, datetime.min.time())
        end_dt = datetime.combine(report_date, datetime.max.time())
        return (
            TechnicalAnalysis
            .select()
            .where(
                (TechnicalAnalysis.stock == stock) &
                (TechnicalAnalysis.created_at >= start_dt) &
                (TechnicalAnalysis.created_at <= end_dt)
            )
            .order_by(TechnicalAnalysis.created_at.desc())
            .first()
        )

    @staticmethod
    def get_technical_history(stock: Stock, limit: int = 10) -> list:
        """Get technical analysis history for a stock"""
        return list(
            TechnicalAnalysis
            .select()
            .where(TechnicalAnalysis.stock == stock)
            .order_by(TechnicalAnalysis.created_at.desc())
            .limit(limit)
        )

    @staticmethod
    def get_technical_by_symbol(symbol: str) -> list:
        """Get all technical analysis entries for a stock symbol"""
        stock = Stock.get_or_none(Stock.symbol == symbol.upper())
        if stock:
            return list(
                TechnicalAnalysis
                .select()
                .where(TechnicalAnalysis.stock == stock)
                .order_by(TechnicalAnalysis.created_at.desc())
            )
        return []

    @staticmethod
    def get_technical_by_id(technical_id: int):
        """Get a technical analysis entry by its ID"""
        from models.models import TechnicalAnalysis
        return TechnicalAnalysis.get_or_none(TechnicalAnalysis.id == technical_id)

    @staticmethod
    def create_technical_historical_values(
        stock: Stock,
        report_date: date,
        close_price: Optional[float] = None,
        volume: Optional[int] = None,
        sma_20: Optional[float] = None,
        sma_50: Optional[float] = None,
        sma_200: Optional[float] = None,
        rsi: Optional[float] = None
    ):
        """Create a new technical historical values entry for a stock"""
        from models.models import TechnicalHistoricalValues
        return TechnicalHistoricalValues.create(
            stock=stock,
            report_date=report_date,
            close_price=close_price,
            volume=volume,
            sma_20=sma_20,
            sma_50=sma_50,
            sma_200=sma_200,
            rsi=rsi
        )

    # --- PortfolioResearch Methods ---
    @staticmethod
    def create_portfolio_research(
        report_date: date = None,
        dca_analysis: str = None,
        economic_analysis: str = None,
        portfolio_analysis: str = None,
        notes: str = None
    ) -> PortfolioResearch:
        """Create a new portfolio research entry"""
        if report_date is None:
            report_date = datetime.now().date()
        return PortfolioResearch.create(
            report_date=report_date,
            dca_analysis=dca_analysis,
            economic_analysis=economic_analysis,
            portfolio_analysis=portfolio_analysis,
            notes=notes
        )

    @staticmethod
    def get_latest_portfolio_research() -> PortfolioResearch:
        """Get the latest portfolio research entry"""
        return (PortfolioResearch
                .select()
                .order_by(PortfolioResearch.report_date.desc())
                .first())

    @staticmethod
    def get_portfolio_research_history(limit: int = 10) -> list:
        """Get portfolio research history"""
        return list(PortfolioResearch
                    .select()
                    .order_by(PortfolioResearch.report_date.desc())
                    .limit(limit))

    @staticmethod
    def get_portfolio_research_history_by_id(research_id: int) -> Optional[PortfolioResearch]:
        """Get a portfolio research entry by its ID"""
        return PortfolioResearch.get_or_none(PortfolioResearch.id == research_id)
    
    # --- TokenUsage Methods ---
    @staticmethod
    def save_token_usage(step: str, input_tokens: int, output_tokens: int, total_tokens: int) -> TokenUsage:
        """Save token usage stats for a step"""
        return TokenUsage.create(
            step=step,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens
        )
    
    @staticmethod
    def get_token_usage(start_date: Optional[str] = None, end_date: Optional[str] = None) -> list:
        """Get token usage records for a date range (YYYY-MM-DD)"""
        query = TokenUsage.select()
        if start_date:
            query = query.where(TokenUsage.created_at >= start_date)
        if end_date:
            query = query.where(TokenUsage.created_at <= end_date)
        return [
            {
                "date": str(row.created_at.date()),
                "step": row.step,
                "input_tokens": row.input_tokens,
                "output_tokens": row.output_tokens,
                "total_tokens": row.total_tokens
            }
            for row in query.order_by(TokenUsage.created_at.desc())
        ]

    # --- CashBalance Methods ---
    @staticmethod
    def create_cash_transaction(
        action: str,
        amount: float,
        transaction_date: date = None,
        note: str = None
    ) -> CashBalance:
        """Create a new cash transaction (deposit or withdrawal)"""
        if transaction_date is None:
            transaction_date = datetime.now().date()
        return CashBalance.create(
            action=action,
            amount=amount,
            transaction_date=transaction_date,
            note=note
        )

    @staticmethod
    def get_cash_transactions(limit: int = 100) -> list:
        """Get cash transactions, most recent first"""
        return list(CashBalance.select().order_by(CashBalance.transaction_date.desc()).limit(limit))

    @staticmethod
    def get_current_cash_balance() -> float:
        """Get the current cash balance (sum of all deposits minus withdrawals)"""
        deposits = (CashBalance
                    .select(fn.SUM(CashBalance.amount))
                    .where(CashBalance.action == "DEPOSIT")
                    .scalar() or 0.0)
        withdrawals = (CashBalance
                       .select(fn.SUM(CashBalance.amount))
                       .where(CashBalance.action == "WITHDRAWAL")
                       .scalar() or 0.0)
        return float(deposits) - float(withdrawals)
    
    @staticmethod
    def get_all_transactions() -> list:
        """Get all transactions in the database"""
        return list(StockTransactionLog.select().order_by(StockTransactionLog.purchase_date.desc()))
    """Database manager for handling stock research data"""

# Initialize singleton database manager when module is imported
db_manager = DatabaseManager()
