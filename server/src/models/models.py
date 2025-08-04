from datetime import datetime, date
from importlib import util
from peewee import *
from playhouse.sqlite_ext import SqliteExtDatabase, JSONField
from playhouse.migrate import SqliteMigrator
from typing import Optional
from pathlib import Path

# Define config directory path
CONFIG_DIR = Path('/config')
DB_PATH = CONFIG_DIR / 'sa.db'

# Ensure config directory exists
CONFIG_DIR.mkdir(parents=True, exist_ok=True)

# Use SQLite database with JSON extension support
db = SqliteExtDatabase(DB_PATH, pragmas={
    'journal_mode': 'wal',  # Write-Ahead Logging for better concurrency
    'cache_size': -1024 * 64,  # 64MB cache
    'foreign_keys': 1,  # Enable foreign key support
    'ignore_check_constraints': 0,
    'synchronous': 0  # Reduce disk I/O
})

class BaseModel(Model):
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)

    def save(self, *args, **kwargs):
        self.updated_at = datetime.now()
        return super(BaseModel, self).save(*args, **kwargs)

    class Meta:
        database = db

class Stock(BaseModel):
    """Stock table to store unique stock symbols"""
    symbol = CharField(unique=True, max_length=10)

    def __str__(self):
        return self.symbol

class StockTransactionLog(BaseModel):
    """Table to log stock transactions (buy, sell, dividend reinvestment)"""
    ACTION_CHOICES = (
        ("BUY", "BUY"),
        ("SELL", "SELL"),
        ("DIVIDEND_REINVESTMENT", "DIVIDEND_REINVESTMENT"),
    )
    stock = ForeignKeyField(Stock, backref="transactions")
    action = CharField(choices=ACTION_CHOICES, max_length=24)
    shares = FloatField()
    price = FloatField()
    purchase_date = DateField()

    def __str__(self):
        return f"{self.purchase_date} {self.action} {self.shares} shares of {self.stock.symbol} @ {self.price}"

# --- CashBalance Table ---
class CashBalance(BaseModel):
    """Table to log cash transactions and track cash balance"""
    ACTION_CHOICES = (
        ("DEPOSIT", "DEPOSIT"),
        ("WITHDRAWAL", "WITHDRAWAL"),
    )
    action = CharField(choices=ACTION_CHOICES, max_length=24)
    amount = FloatField()
    transaction_date = DateField(default=datetime.now)
    note = CharField(null=True)

    def __str__(self):
        return f"{self.transaction_date} {self.action} ${self.amount} ({self.note or ''})"


class Research(BaseModel):
    """Research table to store analysis results for each stock"""
    stock = ForeignKeyField(Stock, backref='research_entries')
    market = TextField(null=True)     # Market data analysis
    news = TextField(null=True)       # News 
    technical = TextField(null=True)  # Technical analysis
    dividend = TextField(null=True)   # Dividend analysis
    recommendation = TextField(null=True)  # Overall recommendation
    structured_output = JSONField(null=True)  # Structured data in JSON format

    class Meta:
        indexes = (
            # Index on stock and created_at for efficient querying of latest research
            (('stock', 'created_at'), False),
        )

class TechnicalAnalysis(BaseModel):
    """Table to store technical analysis results for each stock"""
    stock = ForeignKeyField(Stock, backref='technical_analyses')
    technical = TextField(null=True)  # Technical analysis results
    structured_output = JSONField(null=True)  # Structured data in JSON format

    class Meta:
        indexes = (
            # Index on stock and created_at for efficient querying of latest technical analysis
            (('stock', 'created_at'), False),
        )

class TechnicalHistoricalValues(BaseModel):
    """Historical tracked technical indicator values for stock analysis over time"""
    stock = ForeignKeyField(Stock, backref='technical_historical_values')
    report_date = DateField()
    close_price = FloatField(null=True)
    volume = BigIntegerField(null=True)
    sma_20 = FloatField(null=True)
    sma_50 = FloatField(null=True)
    sma_200 = FloatField(null=True)
    rsi = FloatField(null=True)

    class Meta:
        indexes = (
            # Composite index for efficient querying by stock and date
            (('stock', 'report_date'), False),
        )
        order_by = ('-report_date',)

class HistoricalValues(BaseModel):
    """Historical tracked values for stock analysis over time"""
    stock = ForeignKeyField(Stock, backref='historical_values')
    report_date = DateField()
    final_recommendation = CharField(null=True)
    final_confidence_score = IntegerField(null=True)

    # Key Fundamental Metrics
    pe_ratio = FloatField(null=True)
    revenue_growth_yoy = FloatField(null=True)
    eps_growth_yoy = FloatField(null=True)
    net_profit_margin = FloatField(null=True)
    free_cash_flow = FloatField(null=True)
    debt_to_equity_ratio = FloatField(null=True)

    # Key Market Sentiment Data
    news_sentiment_score = FloatField(null=True)
    analyst_consensus_rating = CharField(null=True)

    # Price Targets
    low_price_target = FloatField(null=True)
    high_price_target = FloatField(null=True)
    price_target_percent = FloatField(null=True)

    class Meta:
        indexes = (
            # Composite index for efficient querying by stock and date
            (('stock', 'report_date'), False),  # True makes it unique
        )
        # Order by date descending by default
        order_by = ('-report_date',)

class PortfolioResearch(BaseModel):
    """Table to store portfolio-level research and recommendations"""
    report_date = DateField(default=datetime.now)
    dca_analysis = TextField(null=True) 
    economic_analysis = TextField(null=True)  
    portfolio_analysis = TextField(null=True)  
    notes = TextField(null=True)  # Optional notes or summary

    class Meta:
        indexes = (
            (('report_date',), False),
        )

class TokenUsage(BaseModel):
    """Table to store token usage statistics for each analysis step"""
    step = CharField()
    input_tokens = IntegerField(default=0)
    output_tokens = IntegerField(default=0)
    total_tokens = IntegerField(default=0)
    created_at = DateTimeField(default=datetime.now)

    def __str__(self):
        return f"{self.created_at} {self.step}: in={self.input_tokens}, out={self.output_tokens}, total={self.total_tokens}"

class ApiRequestUsage(BaseModel):
    """Table to track API request counts per provider"""
    step = CharField()
    provider = CharField()
    count = IntegerField(default=0)

    def __str__(self):
        return f"{self.provider}: {self.count} requests"
