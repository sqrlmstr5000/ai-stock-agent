import os
from datetime import datetime, date
from importlib import util
from peewee import *
from playhouse.postgres_ext import JSONField
from playhouse.migrate import PostgresqlMigrator
from typing import Optional
from pathlib import Path
from peewee import Proxy

database_proxy = Proxy()

class BaseModel(Model):
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)

    def save(self, *args, **kwargs):
        self.updated_at = datetime.now()
        return super(BaseModel, self).save(*args, **kwargs)

    class Meta:
        database = database_proxy

class Stock(BaseModel):
    """Stock table to store unique stock symbols"""
    symbol = CharField(unique=True, max_length=10)
    close = FloatField(null=True)
    volume = BigIntegerField(null=True)
    data_updated_at = DateTimeField(null=True)
    splits_updated_at = DateTimeField(null=True)

    class Meta:
        indexes = (
            # Index for data update queries
            (('data_updated_at',), False),
        )

    def __str__(self):
        return self.symbol

class Research(BaseModel):
    """Research table to store analysis results for each stock"""
    stock = ForeignKeyField(Stock, backref='research_entries')
    market = TextField(null=True)     # Market data analysis
    news = TextField(null=True)       # News 
    technical = TextField(null=True)  # Technical analysis
    dividend = TextField(null=True)   # Dividend analysis
    recommendation = TextField(null=True)  # Overall recommendation
    structured_output = JSONField(null=True)  # Structured data in JSON format
    validation = TextField(null=True)  # Validation summary

    class Meta:
        indexes = (
            # Index on stock and created_at for efficient querying of latest research
            (('stock', 'created_at'), False),
            (('created_at',), False),
        )

class StockSplit(BaseModel):
    """Table to store stock split history for each stock symbol"""
    stock = ForeignKeyField(Stock, backref='splits', on_delete='CASCADE')
    effective_date = DateField()
    split_factor = FloatField()

    class Meta:
        indexes = (
            # Composite index for efficient querying by stock and date
            (('stock', 'effective_date'), True),  # Unique per stock/date
        )

    def __str__(self):
        return f"{self.stock.symbol} split {self.split_factor} on {self.effective_date}"

class Portfolio(BaseModel):
    """Table to store portfolio metadata and configuration"""
    name = CharField(unique=True)
    rules = TextField(null=True)  # formerly principals
    report = TextField(null=True)  # formerly report_instructions

    def __str__(self):
        return self.name

class PortfolioResearch(BaseModel):
    """Table to store portfolio-level research and recommendations"""
    portfolio = ForeignKeyField(Portfolio, backref="research_entries", null=False)
    dca_analysis = TextField(null=True) 
    economic_analysis = TextField(null=True)  
    portfolio_analysis = TextField(null=True)   
    notes = TextField(null=True)  # Optional notes or summary
    validation = TextField(null=True)  # Validation summary

    class Meta:
        indexes = (
            (('created_at',), False),
        )

class StockTransactionLog(BaseModel):
    """Table to log stock transactions (buy, sell, dividend reinvestment)"""
    ACTION_CHOICES = (
        ("BUY", "BUY"),
        ("SELL", "SELL"),
        ("DIVIDEND_REINVESTMENT", "DIVIDEND_REINVESTMENT"),
    )
    stock = ForeignKeyField(Stock, backref="transactions")
    portfolio = ForeignKeyField(Portfolio, backref="transactions", null=False)
    action = CharField(choices=ACTION_CHOICES, max_length=24)
    shares = FloatField()
    price = FloatField()
    purchase_date = DateField()

    class Meta:
        indexes = (
            (('stock', 'portfolio', 'purchase_date'), False),
            (('portfolio',), False),
        )

    def __str__(self):
        return f"{self.purchase_date} {self.action} {self.shares} shares of {self.stock.symbol} @ {self.price}"

class CashBalance(BaseModel):
    """Table to log cash transactions and track cash balance"""
    ACTION_CHOICES = (
        ("DEPOSIT", "DEPOSIT"),
        ("WITHDRAWAL", "WITHDRAWAL"),
    )
    portfolio = ForeignKeyField(Portfolio, backref="cash_balances", null=False)
    action = CharField(choices=ACTION_CHOICES, max_length=24)
    amount = FloatField()
    transaction_date = DateField(default=datetime.now)
    note = CharField(null=True)

    class Meta:
        indexes = (
            (('portfolio', 'transaction_date'), False),
            (('action',), False),
        )

    def __str__(self):
        return f"{self.transaction_date} {self.action} ${self.amount} ({self.note or ''})"

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
    close_price = FloatField(null=True)
    volume = BigIntegerField(null=True)
    sma_20 = FloatField(null=True)
    sma_50 = FloatField(null=True)
    sma_200 = FloatField(null=True)
    rsi = FloatField(null=True)

    class Meta:
        indexes = (
            # Index for efficient querying by stock and created_at
            (('stock', 'created_at'), False),
        )
        order_by = ('-created_at',)

class HistoricalValues(BaseModel):
    """Historical tracked values for stock analysis over time"""
    stock = ForeignKeyField(Stock, backref='historical_values')
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
    current_price = FloatField(null=True)
    low_price_target = FloatField(null=True)
    high_price_target = FloatField(null=True)
    price_target_percent = FloatField(null=True)

    class Meta:
        indexes = (
            # Index for efficient querying by stock and created_at
            (('stock', 'created_at'), False),
        )
        # Order by created_at descending by default
        order_by = ('-created_at',)

class SwingResearch(BaseModel):
    """Table to store swing trade research results"""
    stock = ForeignKeyField(Stock, backref='swingresearch')
    pattern_analysis = TextField(null=True)
    trade_recommendation = TextField(null=True)

    class Meta:
        indexes = (
            (('stock', 'created_at'), False),
        )

class SwingTradePlanHistory(BaseModel):
    stock = ForeignKeyField(Stock, backref='swingtradeplan_history')
    direction = CharField(max_length=8)  # 'long' or 'short'
    entry_price = FloatField()
    stop_loss_price = FloatField()
    take_profit_price = FloatField()
    risk_per_trade_usd = FloatField()
    position_size = IntegerField()
    risk_reward_ratio = FloatField()
    entry_reason = TextField()
    exit_reason = TextField()

    class Meta:
        indexes = (
            # Index on stock and created_at for efficient querying of latest research
            (('stock', 'created_at'), False),
        )

class SwingStock(BaseModel): 
    """Table to store swing stock positions linked to a stock and a portfolio"""
    stock = ForeignKeyField(Stock, backref='swing_stocks', on_delete='CASCADE')
    portfolio = ForeignKeyField(Portfolio, backref='swing_stocks', null=False, on_delete='CASCADE')

    class Meta:
        indexes = (
            (('stock', 'portfolio', 'created_at'), False),
        )
        order_by = ('-created_at',)

    def __str__(self):
        return f"{self.portfolio.name}: {self.stock.symbol} ({self.status or 'unknown'})"

class TokenUsage(BaseModel):
    """Table to store token usage statistics for each analysis step"""
    step = CharField()
    input_tokens = IntegerField(default=0)
    output_tokens = IntegerField(default=0)
    total_tokens = IntegerField(default=0)
    created_at = DateTimeField(default=datetime.now)

    class Meta:
        indexes = (
            (('created_at',), False),
            (('step',), False),
        )

    def __str__(self):
        return f"{self.created_at} {self.step}: in={self.input_tokens}, out={self.output_tokens}, total={self.total_tokens}"

class ApiRequestUsage(BaseModel):
    """Table to track API request counts per provider"""
    step = CharField()
    provider = CharField()
    count = IntegerField(default=0)

    class Meta:
        indexes = (
            (('provider',), False),
        )

    def __str__(self):
        return f"{self.provider}: {self.count} requests"
