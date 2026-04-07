import os
import json
import time
import random
from contextlib import contextmanager
from datetime import datetime, date
from importlib import util
from peewee import *
from playhouse.postgres_ext import PostgresqlExtDatabase
from playhouse.migrate import PostgresqlMigrator
from typing import Optional, List, Dict, Any, Union
from pathlib import Path
from services.migrations import get_migration_files
from utils.logging import setup_logger
from models.models import Stock, StockSplit, StockTransactionLog, TechnicalAnalysis, Research, HistoricalValues, TechnicalHistoricalValues, Portfolio, PortfolioResearch, CashBalance, SwingResearch, SwingTradePlanHistory, SwingStock, TokenUsage, ApiRequestUsage
from models.models import database_proxy

# Configure logging
logger = setup_logger(__name__)

MIGRATIONS_VERSION_TABLE = 'migrations_version'

class DatabaseManager:
    _tables = [Stock, StockSplit, StockTransactionLog, TechnicalAnalysis, Research, HistoricalValues, TechnicalHistoricalValues, Portfolio, PortfolioResearch, CashBalance, SwingResearch, SwingTradePlanHistory, SwingStock, TokenUsage, ApiRequestUsage]

    def __init__(self):
        self._initialize()

    def _initialize(self): 
        """Initialize the database and run migrations"""
        logger.info("Initializing database...")
        # Set up PostgreSQL database connection
        POSTGRES_DB = os.getenv('POSTGRES_DB', 'your_db_name')
        POSTGRES_USER = os.getenv('POSTGRES_USER', 'your_db_user')
        POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD', 'your_db_password')
        POSTGRES_HOST = os.getenv('POSTGRES_HOST', 'localhost')
        POSTGRES_PORT = os.getenv('POSTGRES_PORT', '5432')

        self._db = PostgresqlExtDatabase(
            POSTGRES_DB,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
            host=POSTGRES_HOST,
            port=POSTGRES_PORT,
            autorollback=True
        )

        # Bind the Peewee Proxy to the actual db instance
        database_proxy.initialize(self._db)
        self.db = database_proxy

        self._db.connect()
        self._db.create_tables(self._tables)
        self._run_migrations()
        #self._db.close()

    def _run_migrations(self):
        """Run all pending database migrations"""
        logger.info("Checking for database migrations...")
        # Create migrations version table if it doesn't exist
        self._db.execute_sql(
            f'''CREATE TABLE IF NOT EXISTS {MIGRATIONS_VERSION_TABLE} (
                version INTEGER PRIMARY KEY,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )'''
        )
        
        current_version = self._get_current_version()
        logger.info(f"Current database version: {current_version}")
        
        migrator = PostgresqlMigrator(self._db)
        
        # Get all migration files
        migrations = get_migration_files()
        logger.info(f"Found {len(migrations)} migration files")
        
        # Determine if there are any pending migrations
        pending_migrations = [(version, file_path) for version, file_path in migrations if version > current_version]
        if not pending_migrations:
            logger.info("No pending migrations to apply. Skipping backup.")
            return
        # Backup database before running migrations
        try:
            backup_path = self.backup_database()
            logger.info(f"Database backup created before migrations: {backup_path}")
        except Exception as e:
            logger.error(f"Failed to create backup before migrations: {e}")
        
        for version, file_path in pending_migrations:
            logger.info(f"Running migration {version} from {file_path}")
            try:
                # Import the migration module
                spec = util.spec_from_file_location(f"migration_{version}", file_path)
                module = util.module_from_spec(spec)
                spec.loader.exec_module(module)
                # Run the upgrade function
                with self._db.atomic():
                    module.upgrade(migrator)
                    self._set_version(version)
                logger.info(f"Successfully applied migration {version}")
            except Exception as e:
                logger.error(f"Error applying migration {version}: {str(e)}")
                raise

    # --- connection helpers (simple, small surface area) ---
    def _ensure_connection(self, max_retries: int = 10, base_delay: float = 0.5):
        """Ensure the database connection is usable; reconnect with backoff if needed.

        This is intentionally small: it only reconnects the `PostgresqlExtDatabase` instance
        if it's closed or not usable. Keep retries short to avoid blocking the app too long.
        """
        retries = 0
        while True:
            try:
                if getattr(self, "_db", None) is None:
                    raise Exception("Database instance not initialized")
                # Re-open closed connection
                if self._db.is_closed():
                    self._db.connect()
                # Peewee provides is_connection_usable() on connection objects; fall back to True
                is_usable = getattr(self._db, "is_connection_usable", lambda: True)()
                if not is_usable:
                    try:
                        self._db.close()
                    except Exception:
                        pass
                    self._db.connect()
                return
            except Exception as exc:
                retries += 1
                if retries >= max_retries:
                    logger.error(f"Failed to ensure DB connection after {retries} attempts: {exc}")
                    raise
                sleep_for = base_delay * (2 ** (retries - 1)) * (1 + random.random() * 0.2)
                logger.warning(f"DB not usable, reconnect attempt {retries}/{max_retries}, sleeping {sleep_for:.2f}s")
                time.sleep(sleep_for)

    @contextmanager
    def get_connection(self):
        """Simple context manager that ensures the DB connection is usable for the block.

        Does not close pooled connections afterwards (PostgresqlExtDatabase manages pooling).
        Use this around app-level entry points (API handlers, scheduled jobs) before calling
        DatabaseManager methods that touch the DB.
        """
        self._ensure_connection()
        try:
            yield self._db
        finally:
            # Keep connection open; do not close here.
            pass

    def _get_current_version(self):
        """Get the current database migration version"""
        try:
            cursor = self._db.execute_sql(
                f'SELECT version FROM {MIGRATIONS_VERSION_TABLE} ORDER BY version DESC LIMIT 1'
            )
            result = cursor.fetchone()
            return result[0] if result else 0
        except Exception:
            return 0

    def _set_version(self, version: int):
        """Set the current database migration version"""
        self._db.execute_sql(
            f'INSERT INTO {MIGRATIONS_VERSION_TABLE} (version) VALUES (%s)',
            (version,)
        )

    @staticmethod
    def get_stock_by_id(stock_id: int) -> Optional[Stock]:
        """Get a stock by its ID. Returns the Stock instance or None if not found."""
        return Stock.get_or_none(Stock.id == stock_id)

    @staticmethod
    def get_stock_by_symbol(symbol: str) -> Optional[Stock]:
        """Get a stock by its symbol. Returns the Stock instance or None if not found."""
        return Stock.get_or_none(Stock.symbol == symbol.upper())

    @staticmethod
    def get_or_create_stock(symbol: str) -> tuple[Optional[Stock], bool]:
        """Get or create a stock entry, returns (stock, created) tuple. If creation fails, returns (None, False)"""
        try:
            stock, created = Stock.get_or_create(symbol=symbol.upper())
            if stock is not None:
                logger.debug(f"Stock {symbol} {'created' if created else 'found'} in database.")
                return stock, created
            else:
                logger.error(f"Failed to get or create stock for symbol: {symbol}")
                return None, False
        except Exception as e:
            logger.error(f"Exception in get_or_create_stock for symbol {symbol}: {e}")
            return None, False

    @staticmethod
    def delete_stock_by_id(stock_id: int) -> bool:
        """Delete a stock by its ID. Returns True if deleted, False if not found."""
        stock = Stock.get_or_none(Stock.id == stock_id)
        if stock:
            stock.delete_instance()
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
        structured_output: dict = None,
        validation: str = None
    ) -> Research:
        """Create a new research entry for a stock"""
        return Research.create(
            stock=stock,
            market=market,
            news=news,
            technical=technical,
            dividend=dividend,
            recommendation=recommendation,
            structured_output=structured_output,
            validation=validation
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
    def get_latest_research_by_symbol(symbol: str) -> Optional[Research]:
        """Get the latest research entry for a stock symbol"""
        stock = Stock.get_or_none(Stock.symbol == symbol.upper())
        if stock:
            return (Research
                    .select()
                    .where(Research.stock == stock)
                    .order_by(Research.created_at.desc())
                    .first())
        return None

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
        current_price: Optional[float] = None,
        low_price_target: Optional[float] = None,
        high_price_target: Optional[float] = None,
        price_target_percent: Optional[float] = None
    ) -> HistoricalValues:
        """Create a new historical values entry for a stock"""
        return HistoricalValues.create(
            stock=stock,
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
            current_price=current_price,
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
            query = query.where(HistoricalValues.created_at >= start_date)
        if end_date:
            query = query.where(HistoricalValues.created_at <= end_date)

        return list(query.order_by(HistoricalValues.created_at.desc()).limit(limit))

    @staticmethod
    def get_latest_historical_values(stock: Stock, before_date: Optional[datetime] = None) -> Optional[HistoricalValues]:
        """Get the latest historical values for a stock.

        If `before_date` is provided, return the latest record with `created_at` <= `before_date`.
        Otherwise return the latest record regardless of date.
        """
        query = HistoricalValues.select().where(HistoricalValues.stock == stock)
        if before_date is not None:
            query = query.where(HistoricalValues.created_at <= before_date)
        return query.order_by(HistoricalValues.created_at.desc()).first()

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
        portfolio_id: int,
        dca_analysis: str = None,
        economic_analysis: str = None,
        portfolio_analysis: str = None,
        notes: str = None
    ) -> PortfolioResearch:
        """Create a new portfolio research entry"""
        return PortfolioResearch.create(
            portfolio_id=portfolio_id,
            dca_analysis=dca_analysis,
            economic_analysis=economic_analysis,
            portfolio_analysis=portfolio_analysis,
            notes=notes
        )

    @staticmethod
    def get_latest_portfolio_research(portfolio_id: int = None) -> PortfolioResearch:
        """Get the latest portfolio research entry, optionally filtered by portfolio_id"""
        query = PortfolioResearch.select()
        if portfolio_id is not None:
            query = query.where(PortfolioResearch.portfolio == portfolio_id)
        return query.order_by(PortfolioResearch.created_at.desc()).first()


    @staticmethod
    def get_portfolio_research_history(limit: int = 10, portfolio_id: int = None) -> list:
        """Get portfolio research history, optionally filtered by portfolio_id"""
        query = PortfolioResearch.select()
        if portfolio_id is not None:
            query = query.where(PortfolioResearch.portfolio == portfolio_id)
        return list(query.order_by(PortfolioResearch.created_at.desc()).limit(limit))

    @staticmethod
    def get_portfolio_research_history_by_id(research_id: int, portfolio_id: int = None) -> Optional[PortfolioResearch]:
        """Get a portfolio research entry by its ID, optionally filtered by portfolio_id"""
        query = PortfolioResearch.select().where(PortfolioResearch.id == research_id)
        if portfolio_id is not None:
            query = query.where(PortfolioResearch.portfolio == portfolio_id)
        return query.first()

    @staticmethod
    def delete_portfolio_research(research_id: int, portfolio_id: int = None) -> bool:
        """Delete a portfolio research entry by its ID, optionally filtered by portfolio_id"""
        query = PortfolioResearch.select().where(PortfolioResearch.id == research_id)
        if portfolio_id is not None:
            query = query.where(PortfolioResearch.portfolio == portfolio_id)
        entry = query.first()
        if entry:
            entry.delete_instance()
            return True
        return False
    
    @staticmethod
    def get_portfolio_by_id(portfolio_id: int) -> Portfolio:
        """Get a portfolio by its ID"""
        return Portfolio.get_or_none(Portfolio.id == portfolio_id)

    @staticmethod
    def get_portfolios() -> list:
        """Get all portfolios from the database"""
        return list(Portfolio.select())

    @staticmethod
    def save_portfolio(portfolio_id: int = None, name: str = None, rules: str = None, report: str = None) -> Portfolio:
        """Create a new portfolio or update an existing one by id"""
        if portfolio_id:
            portfolio = Portfolio.get_or_none(Portfolio.id == portfolio_id)
            if not portfolio:
                raise ValueError(f"Portfolio with id {portfolio_id} does not exist.")
            if name is not None:
                portfolio.name = name
            if rules is not None:
                portfolio.rules = rules
            if report is not None:
                portfolio.report = report
            portfolio.save()
            return portfolio
        else:
            return Portfolio.create(
                name=name,
                rules=rules,
                report=report
            )

    @staticmethod
    def delete_portfolio(portfolio_id: int) -> bool:
        """Delete a portfolio by id"""
        portfolio = Portfolio.get_or_none(Portfolio.id == portfolio_id)
        if portfolio:
            portfolio.delete_instance()
            return True
        return False

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
        note: str = None,
        portfolio_id: int = None
    ) -> CashBalance:
        """Create a new cash transaction (deposit or withdrawal), optionally for a portfolio"""
        if transaction_date is None:
            transaction_date = datetime.now().date()
        return CashBalance.create(
            action=action,
            amount=amount,
            transaction_date=transaction_date,
            note=note,
            portfolio=portfolio_id
        )

    @staticmethod
    def get_cash_transactions(limit: int = 100, portfolio_id: int = None) -> list:
        """Get cash transactions, most recent first, optionally filtered by portfolio_id"""
        query = CashBalance.select()
        if portfolio_id is not None:
            query = query.where(CashBalance.portfolio == portfolio_id)
        return list(query.order_by(CashBalance.transaction_date.desc()).limit(limit))

    @staticmethod
    def get_current_cash_balance(portfolio_id: int = None) -> float:
        """Get the current cash balance (sum of all deposits minus withdrawals), optionally for a portfolio"""
        deposit_query = CashBalance.select(fn.SUM(CashBalance.amount)).where(CashBalance.action == "DEPOSIT")
        withdrawal_query = CashBalance.select(fn.SUM(CashBalance.amount)).where(CashBalance.action == "WITHDRAWAL")
        if portfolio_id is not None:
            deposit_query = deposit_query.where(CashBalance.portfolio == portfolio_id)
            withdrawal_query = withdrawal_query.where(CashBalance.portfolio == portfolio_id)
        deposits = deposit_query.scalar() or 0.0
        withdrawals = withdrawal_query.scalar() or 0.0
        return float(deposits) - float(withdrawals)
    
    # --- TransactionLog Methods ---
    @staticmethod
    def create_transaction(
        stock: Stock,
        action: str,
        shares: float,
        price: float,
        purchase_date: date,
        portfolio_id: int = None
    ) -> StockTransactionLog:
        """Create a new stock transaction log entry, optionally for a portfolio"""
        return StockTransactionLog.create(
            stock=stock.id,
            action=action,
            shares=shares,
            price=price,
            purchase_date=purchase_date,
            portfolio=portfolio_id
        )

    @staticmethod
    def get_transactions_by_symbol(symbol: str, portfolio_id: int = None) -> list:
        """Get all transactions for a stock symbol, optionally filtered by portfolio_id"""
        stock = Stock.get_or_none(Stock.symbol == symbol.upper())
        if stock:
            query = StockTransactionLog.select().where(StockTransactionLog.stock == stock)
            if portfolio_id is not None:
                query = query.where(StockTransactionLog.portfolio == portfolio_id)
            return list(query.order_by(StockTransactionLog.purchase_date.desc()))
        return []

    @staticmethod
    def get_transaction_by_id(transaction_id: int) -> StockTransactionLog:
        """Get a transaction by its ID, optionally filtered by portfolio_id"""
        query = StockTransactionLog.select().where(StockTransactionLog.id == transaction_id)
        return query.first()

    @staticmethod
    def delete_transaction(transaction_id: int, portfolio_id: int) -> bool:
        """Delete a transaction by its ID, optionally filtered by portfolio_id"""
        query = StockTransactionLog.select().where(StockTransactionLog.id == transaction_id)
        if portfolio_id is not None:
            query = query.where(StockTransactionLog.portfolio == portfolio_id)
        txn = query.first()
        if txn:
            txn.delete_instance()
            return True
        return False
    
    @staticmethod
    def get_all_transactions(portfolio_id: int = None) -> list:
        """Get all transactions in the database, optionally filtered by portfolio_id"""
        query = StockTransactionLog.select()
        if portfolio_id is not None:
            query = query.where(StockTransactionLog.portfolio == portfolio_id)
        return list(query.order_by(StockTransactionLog.purchase_date.desc()))

    #
    # Swing
    #
    @staticmethod
    def create_swing_trade_research(
        stock: Stock,
        pattern_analysis: str = None,
        trade_recommendation: str = None,
    ):
        """Create a new swing trade research entry"""
        from models.models import SwingResearch
        return SwingResearch.create(
            stock=stock,
            pattern_analysis=pattern_analysis,
            trade_recommendation=trade_recommendation,
        )

    @staticmethod
    def create_swing_trade_plan_history(
        stock: Stock,
        direction: str,
        entry_price: float,
        stop_loss_price: float,
        take_profit_price: float,
        risk_per_trade_usd: float,
        position_size: int,
        risk_reward_ratio: float,
        entry_reason: str,
        exit_reason: str
    ) -> SwingTradePlanHistory:
        """Create a new swing trade plan history entry"""
        return SwingTradePlanHistory.create(
            stock=stock,
            direction=direction,
            entry_price=entry_price,
            stop_loss_price=stop_loss_price,
            take_profit_price=take_profit_price,
            risk_per_trade_usd=risk_per_trade_usd,
            position_size=position_size,
            risk_reward_ratio=risk_reward_ratio,
            entry_reason=entry_reason,
            exit_reason=exit_reason
        )

    @staticmethod
    def create_swing_stock(stock: Stock, portfolio: Portfolio) -> SwingStock:
        """Create or get a swing stock entry linking a stock to a portfolio"""
        from models.models import SwingStock
        swing_stock, created = SwingStock.get_or_create(stock=stock, portfolio=portfolio)
        return swing_stock

    #
    # Backup/Restore
    #
    def backup_database(self, backup_dir: str = None) -> str:
        """Backup the PostgreSQL database to the specified directory (default: /output/backup). Returns the backup file path."""        # Only works for PostgreSQL
        if backup_dir is None:
            backup_dir = '/output/backup'
        os.makedirs(backup_dir, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f"backup_{timestamp}.dump"
        backup_path = os.path.join(backup_dir, backup_filename)

        # Get connection info from self._db object
        db_params = self._db.connect_params.copy() if hasattr(self._db, 'connect_params') else {}
        db_name = db_params.get('database') or os.environ.get('POSTGRES_DB')
        db_user = db_params.get('user') or os.environ.get('POSTGRES_USER')
        db_host = db_params.get('host') or os.environ.get('POSTGRES_HOST', 'localhost')
        db_port = str(db_params.get('port') or os.environ.get('POSTGRES_PORT', 5432))
        db_password = db_params.get('password') or os.environ.get('POSTGRES_PASSWORD')

        if not db_name or not db_user:
            logger.error("PostgreSQL database name and user must be specified in db config or environment.")
            raise ValueError("PostgreSQL database name and user must be specified.")

        # Prepare pg_dump command
        env = os.environ.copy()
        if db_password:
            env['PGPASSWORD'] = db_password
        cmd = [
            'pg_dump',
            '-h', db_host,
            '-p', db_port,
            '-U', db_user,
            '-F', 'c',  # custom format for compressed backup
            '-f', backup_path,
            db_name
        ]

        import subprocess
        try:
            logger.info(f"Backing up PostgreSQL database '{db_name}' to {backup_path}")
            subprocess.run(cmd, env=env, check=True)
            logger.info(f"Database backed up to {backup_path}")
            return backup_path
        except Exception as e:
            logger.error(f"Error during PostgreSQL backup: {e}")
            raise