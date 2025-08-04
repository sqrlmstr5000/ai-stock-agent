from typing import List, Optional, Union
import os
import logging
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field


from utils.logging import setup_logger
from app import StockAnalysisApp
from models.models import Stock
from datetime import date, datetime
app = FastAPI(
    title="Stock Analysis API",
    description="API for analyzing stocks using YFinance and AlphaVantage data",
    version="1.0.0"
)

logger = setup_logger("api")

# Initialize the app
stock_app = StockAnalysisApp()

# Models
class StockRequest(BaseModel):
    symbol: str

class StockResponse(BaseModel):
    message: str
    data: Union[str, dict, list]
    token_usage: Optional[dict] = None

class TransactionRequest(BaseModel):
    symbol: str = Field(..., description="Stock symbol")
    action: str = Field(..., description="Transaction action: BUY, SELL, DIVIDEND_REINVESTMENT")
    shares: float = Field(..., description="Number of shares")
    price: float = Field(..., description="Price per share")
    purchase_date: date = Field(..., description="Date of transaction (YYYY-MM-DD)")

class TransactionResponse(BaseModel):
    message: str
    data: dict | list | None = None

class CashTransactionRequest(BaseModel):
    action: str = Field(..., description="Cash action: DEPOSIT or WITHDRAWAL")
    amount: float = Field(..., description="Amount of cash to deposit or withdraw")
    transaction_date: Optional[date] = Field(None, description="Date of transaction (YYYY-MM-DD)")
    note: Optional[str] = Field(None, description="Optional note for the transaction")

class CashTransactionResponse(BaseModel):
    message: str
    data: dict | list | float | None = None

def handle_api_exception(e, msg=None):
    import traceback
    error_msg = msg or str(e)
    logger.error(f"{error_msg}: {e}\n{traceback.format_exc()}")
    raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
async def root():
    return {
        "message": "Stock Analysis API is running",
        "endpoints": {
            "/analyze/{symbol}": "Get full analysis for a single stock",
            "/compare": "Compare multiple stocks",
            "/dividends/{symbol}": "Get dividend history for a stock",
            "/news/{symbol}": "Get news for a stock",
            "/market/{symbol}": "Get market data for a stock",
            "/technical/{symbol}": "Get technical indicators for a stock"
        }
    }

@app.post("/stocks", status_code=201)
async def add_stock(stock: StockRequest) -> StockResponse:
    """Add a new stock to the database"""
    try:
        result = stock_app.add_stock(stock.symbol)
        return StockResponse(**result)
    except Exception as e:
        handle_api_exception(e, "Error adding stock")

@app.get("/stocks")
async def get_stocks() -> StockResponse:
    """Get all stocks from the database"""
    try:
        result = stock_app.get_all_stocks()
        return StockResponse(**result)
    except Exception as e:
        handle_api_exception(e, "Error getting all stocks")

@app.get("/stocks/research")
async def get_stocks_research_history(limit: int = 20):
    """Get research history for all stocks (latest first)"""
    try:
        dbm = stock_app.db_manager
        entries = dbm.get_all_research_history_list(limit)
        data = [
            {
                "id": entry["id"] if isinstance(entry, dict) else entry.id,
                "symbol": entry["symbol"] if isinstance(entry, dict) else entry.stock.symbol,
                "created_at": entry["created_at"] if isinstance(entry, dict) else str(entry.created_at),
                "final_recommendation": entry.get("final_recommendation") if isinstance(entry, dict) else None,
                "final_confidence_score": entry.get("final_confidence_score") if isinstance(entry, dict) else None,
                "high_price_target": entry.get("high_price_target") if isinstance(entry, dict) else None,
                "price_target_percent": entry.get("price_target_percent") if isinstance(entry, dict) else None
            }
            for entry in entries
        ]
        return StockResponse(message="Research history fetched", data=data)
    except Exception as e:
        handle_api_exception(e, "Error getting stocks research history")

# --- Stock Endpoints ---
@app.get("/stock/{symbol}/research")
async def get_research(symbol: str) -> StockResponse:
    """Get all research for a stock"""
    try:
        result = stock_app.get_research(symbol)
        return StockResponse(**result)
    except Exception as e:
        handle_api_exception(e, "Error getting research")

@app.get("/stock/{symbol}/technical")
async def get_technical_analyses(symbol: str) -> StockResponse:
    """Get all technical analyses for a stock"""
    try:
        result = stock_app.get_technical_analyses(symbol)
        return StockResponse(**result)
    except Exception as e:
        handle_api_exception(e, "Error getting technical analyses")

@app.get("/stock/research/{research_id}")
async def get_research_report(research_id: int) -> StockResponse:
    """Get a research report by its ID"""
    try:
        result = stock_app.get_research_report(research_id)
        return StockResponse(**result)
    except Exception as e:
        handle_api_exception(e, "Error getting research report")

@app.get("/stock/technical/{technical_id}")
async def get_technical_report_by_id(technical_id: int) -> StockResponse:
    """Get a technical analysis report by its ID"""
    try:
        result = stock_app.get_technical_report(technical_id)
        return StockResponse(**result)
    except Exception as e:
        handle_api_exception(e, "Error getting technical report")

@app.delete("/stocks/{stock_id}")
async def delete_stock(stock_id: int) -> StockResponse:
    """Delete a stock from the database by id"""
    try:
        stock = Stock.get_or_none(Stock.id == stock_id)
        if not stock:
            raise HTTPException(status_code=404, detail=f"Stock id {stock_id} not found")
        symbol = stock.symbol
        stock.delete_instance()
        return StockResponse(message=f"Stock {symbol} deleted", data={"id": stock_id, "symbol": symbol})
    except HTTPException:
        raise
    except Exception as e:
        handle_api_exception(e, "Error deleting stock")

@app.get("/analyze/{symbol}")
async def analyze_stock(symbol: str) -> StockResponse:
    """Get a full analysis for a single stock"""
    try:
        result = await stock_app.analyze_stock(symbol)
        return StockResponse(**result)
    except Exception as e:
        handle_api_exception(e, "Error analyzing stock")

@app.post("/compare")
async def compare_stocks(symbols: List[str]) -> StockResponse:
    """Compare multiple stocks"""
    try:
        result = await stock_app.compare_stocks(symbols)
        return StockResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        handle_api_exception(e, "Error comparing stocks")

@app.get("/dividends/{symbol}")
async def get_dividends(symbol: str) -> StockResponse:
    """Get dividend history for a stock"""
    try:
        result = await stock_app.get_dividends(symbol)
        return StockResponse(**result)
    except Exception as e:
        handle_api_exception(e, "Error getting dividends")

@app.get("/news/{symbol}")
async def get_news(symbol: str) -> StockResponse:
    """Get news for a stock"""
    try:
        result = await stock_app.get_news(symbol)
        return StockResponse(**result)
    except Exception as e:
        handle_api_exception(e, "Error getting news")

@app.get("/market/{symbol}")
async def get_market_data(symbol: str) -> StockResponse:
    """Get market data for a stock"""
    try:
        result = await stock_app.get_market_data(symbol)
        return StockResponse(**result)
    except Exception as e:
        handle_api_exception(e, "Error getting market data")

@app.get("/transactions")
async def get_all_transactions() -> TransactionResponse:
    """Get all transactions in the database"""
    try:
        result = stock_app.get_transactions(None)
        return TransactionResponse(message="All transactions fetched", data=result)
    except Exception as e:
        handle_api_exception(e, "Error getting all transactions")

@app.get("/technical/{symbol}")
async def get_technical_data(symbol: str) -> StockResponse:
    """Get technical indicators for a stock"""
    try:
        result = await stock_app.get_technical_data(symbol)
        return StockResponse(**result)
    except Exception as e:
        handle_api_exception(e, "Error getting technical data")

@app.get("/technical/generate/{symbol}")
async def generate_technical_analysis(symbol: str) -> StockResponse:
    """Generate a new technical analysis for a stock and store it"""
    try:
        result = await stock_app.analyze_technical(symbol)
        return StockResponse(**result)
    except Exception as e:
        handle_api_exception(e, "Error generating technical analysis")

# --- Transaction Endpoints ---
@app.post("/transactions", status_code=201)
async def add_transaction(txn: TransactionRequest) -> TransactionResponse:
    """Add a new stock transaction log entry"""
    try:
        result = stock_app.add_transaction(txn)
        return TransactionResponse(message="Transaction added", data=result)
    except Exception as e:
        handle_api_exception(e, "Error adding transaction")

@app.get("/transactions/{symbol}")
async def get_transactions(symbol: str) -> TransactionResponse:
    """Get all transactions for a stock symbol"""
    try:
        result = stock_app.get_transactions(symbol)
        return TransactionResponse(message="Transactions fetched", data=result)
    except Exception as e:
        handle_api_exception(e, "Error getting transactions")

@app.get("/transaction/{transaction_id}")
async def get_transaction(transaction_id: int) -> TransactionResponse:
    """Get a transaction by its ID"""
    try:
        result = stock_app.get_transaction(transaction_id)
        if result:
            return TransactionResponse(message="Transaction fetched", data=result)
        else:
            raise HTTPException(status_code=404, detail="Transaction not found")
    except Exception as e:
        handle_api_exception(e, "Error getting transaction")

@app.delete("/transaction/{transaction_id}")
async def delete_transaction(transaction_id: int) -> TransactionResponse:
    """Delete a transaction by its ID"""
    try:
        deleted = stock_app.delete_transaction(transaction_id)
        if deleted:
            return TransactionResponse(message="Transaction deleted", data=None)
        else:
            raise HTTPException(status_code=404, detail="Transaction not found")
    except Exception as e:
        handle_api_exception(e, "Error deleting transaction")

# Portfolio summary endpoint
@app.get("/portfolio")
async def get_portfolio() -> TransactionResponse:
    """Get a comprehensive portfolio summary"""
    try:
        result = stock_app.get_portfolio()
        return TransactionResponse(message="Portfolio summary fetched", data=result)
    except Exception as e:
        handle_api_exception(e, "Error getting portfolio")

# --- Portfolio Research Endpoints ---
@app.get("/portfolio/research")
async def get_portfolio_research_history(limit: int = 10) -> StockResponse:
    """Get portfolio research history (latest first)"""
    try:
        dbm = stock_app.db_manager
        entries = dbm.get_portfolio_research_history(limit)
        data = [
            {
                "id": entry.id,
                "report_date": str(entry.report_date),
                "dca_analysis": entry.dca_analysis,
                "portfolio_analysis": entry.portfolio_analysis,
                "notes": entry.notes
            }
            for entry in entries
        ]
        return StockResponse(message="Portfolio research history fetched", data=data)
    except Exception as e:
        handle_api_exception(e, "Error getting portfolio research history")


@app.get("/portfolio/research/{research_id}")
async def get_portfolio_research(research_id: int) -> StockResponse:
    """Get a single portfolio research entry by ID"""
    try:
        dbm = stock_app.db_manager
        if research_id == 0:
            entry = dbm.get_latest_portfolio_research()
            if entry:
                data = {
                    "id": entry.id,
                    "report_date": str(entry.report_date),
                    "dca_analysis": entry.dca_analysis,
                    "economic_analysis": entry.economic_analysis,
                    "portfolio_analysis": entry.portfolio_analysis,
                    "notes": entry.notes
                }
                return StockResponse(message="Latest portfolio research fetched", data=data)
            else:
                raise HTTPException(status_code=404, detail="No portfolio research entries found")
        else:
            entry = dbm.get_portfolio_research_history_by_id(research_id)
            if entry:
                data = {
                    "id": entry.id,
                    "report_date": str(entry.report_date),
                    "dca_analysis": entry.dca_analysis,
                    "portfolio_analysis": entry.portfolio_analysis,
                    "notes": entry.notes
                }
                return StockResponse(message="Portfolio research entry fetched", data=data)
            else:
                raise HTTPException(status_code=404, detail="Portfolio research entry not found")
    except Exception as e:
        handle_api_exception(e, "Error getting portfolio research entry")

@app.post("/portfolio/analyze")
async def analyze_portfolio() -> StockResponse:
    """Run portfolio-level analysis using current portfolio, latest recommendations, and cash balance"""
    try:
        result = await stock_app.portfolio_analysis()
        return StockResponse(**result)
    except Exception as e:
        handle_api_exception(e, "Error analyzing portfolio")

# --- Cash Balance Endpoints ---
@app.get("/cash/balance")
async def get_cash_balance() -> CashTransactionResponse:
    """Get the current cash balance"""
    try:
        dbm = stock_app.db_manager
        balance = dbm.get_current_cash_balance()
        return CashTransactionResponse(message="Current cash balance fetched", data={"balance": round(balance, 2)})
    except Exception as e:
        handle_api_exception(e, "Error getting cash balance")

@app.get("/cash/transactions")
async def get_cash_transactions(limit: int = 100) -> CashTransactionResponse:
    """Get cash transaction history (most recent first)"""
    try:
        dbm = stock_app.db_manager
        txns = dbm.get_cash_transactions(limit)
        data = [
            {
                "id": txn.id,
                "action": txn.action,
                "amount": txn.amount,
                "transaction_date": str(txn.transaction_date),
                "note": txn.note
            }
            for txn in txns
        ]
        return CashTransactionResponse(message="Cash transactions fetched", data=data)
    except Exception as e:
        handle_api_exception(e, "Error getting cash transactions")

@app.post("/cash/transaction", status_code=201)
async def add_cash_transaction(txn: CashTransactionRequest) -> CashTransactionResponse:
    """Add a new cash transaction (deposit or withdrawal)"""
    try:
        dbm = stock_app.db_manager
        new_txn = dbm.create_cash_transaction(
            action=txn.action,
            amount=txn.amount,
            transaction_date=txn.transaction_date or datetime.now().date(),
            note=txn.note
        )
        data = {
            "id": new_txn.id,
            "action": new_txn.action,
            "amount": new_txn.amount,
            "transaction_date": str(new_txn.transaction_date),
            "note": new_txn.note
        }
        return CashTransactionResponse(message="Cash transaction added", data=data)
    except Exception as e:
        handle_api_exception(e, "Error adding cash transaction")

# --- Usage Endpoints ---
@app.get("/usage/provider")
async def usage_provider(
    provider: str = Query(None, description="API provider name (optional)"),
    start_date: str = Query(None, description="Start date (YYYY-MM-DD, optional)"),
    end_date: str = Query(None, description="End date (YYYY-MM-DD, optional)")
) -> StockResponse:
    """List API usage records for a provider and date range"""
    try:
        data = stock_app.get_provider_usage(provider=provider, start_date=start_date, end_date=end_date)
        return StockResponse(message="API usage records fetched", data=data)
    except Exception as e:
        handle_api_exception(e, "Error getting usage provider")

@app.get("/usage/token")
async def usage_token(
    start_date: str = Query(None, description="Start date (YYYY-MM-DD, optional)"),
    end_date: str = Query(None, description="End date (YYYY-MM-DD, optional)")
) -> StockResponse:
    """List token usage records for LLM calls in a date range"""
    try:
        data = stock_app.get_token_usage(start_date=start_date, end_date=end_date)
        return StockResponse(message="Token usage records fetched", data=data)
    except Exception as e:
        handle_api_exception(e, "Error getting usage token")

#
# Scheduler
#
@app.get("/scheduler/jobs")
async def get_scheduled_jobs():
    """Get all scheduled jobs and their details."""
    try:
        jobs = stock_app.get_scheduled_jobs()
        return {"message": "Scheduled jobs fetched", "data": jobs}
    except Exception as e:
        handle_api_exception(e, "Error getting scheduled jobs")

@app.post("/scheduler/trigger/{job_id}")
async def trigger_job(job_id: str):
    """Trigger a scheduled job to run immediately by job_id."""
    try:
        result = stock_app.trigger_job(job_id)
        if result:
            return {"message": f"Job {job_id} triggered successfully", "data": True}
        else:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found or could not be triggered")
    except Exception as e:
        handle_api_exception(e, "Error triggering job")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
