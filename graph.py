import os
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Annotated
from typing_extensions import TypedDict
import json
import argparse
import logging

from langchain_core.prompts import PromptTemplate
from langchain.agents import AgentExecutor, Tool
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.runnables import Runnable
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.output_parsers import StrOutputParser
from langchain_google_genai import ChatGoogleGenerativeAI

token_usage_stats = {
    "total": {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
    },
    "technical": {},
    "market": {},
    "news": {},
    "recommendation": {},
    "comparison": {},
}

def update_token_usage(step: str, usage: Dict[any, any]):
    """Helper function to update the token usage statistics"""
    input_tokens = usage.get("input_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)
    total_tokens = usage.get("total_tokens", 0)

    token_usage_stats[step] = {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
    }

    token_usage_stats["total"]["input_tokens"] += input_tokens
    token_usage_stats["total"]["output_tokens"] += output_tokens
    token_usage_stats["total"]["total_tokens"] += total_tokens


class State(TypedDict):
    # Messages have the type "list". The `add_messages` function
    # in the annotation defines how this state key should be updated
    # (in this case, it appends messages to the list, rather than overwriting them)
    messages: Annotated[list, add_messages]
    symbol: str
    llm: ChatGoogleGenerativeAI
    results: Dict

# Initialize the ollama endpoint
def setup_llm():
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=1.0,
        max_retries=2,
        api_key=os.getenv("GEMINI_API_KEY"),
    )

# Technical Analysis Node
def get_technical_indicators(symbol: str):
    # Fetch technical data
    stock = yf.Ticker(symbol)
    hist = stock.history(period='1y')
    logging.debug(f"yfinance hist: {hist.to_json(indent=2, date_format='iso')}")

    # Calculate indicators
    sma_20 = hist['Close'].rolling(window=20).mean()
    sma_50 = hist['Close'].rolling(window=50).mean()
    rsi = calculate_rsi(hist['Close'])

    data = {
        'current_price': hist['Close'].iloc[-1],
        'sma_20': sma_20.iloc[-1],
        'sma_50': sma_50.iloc[-1],
        'rsi': rsi.iloc[-1],
        'volume_trend': hist['Volume'].iloc[-5:].mean() / hist['Volume'].iloc[-20:].mean()
    }
    logging.info("yfinance technical data:")
    logging.info(f"{json.dumps(data, indent=2)}")
    return data

def technical_analysis(state: State) -> State:
    """Node for technical analysis"""
    symbol = state["symbol"]
    logging.info(f"Starting technical analysis for {symbol}...")
    llm = state["llm"]

    data = get_technical_indicators(symbol)

    prompt = PromptTemplate.from_template(
        """Analyze these technical indicators for {symbol}:
        {data}

        Provide:
        1. Trend analysis
        2. Support/Resistance levels
        3. Technical rating (Bullish/Neutral/Bearish)
        4. Key signals
        """
    )

    chain = prompt | llm
    analysis = chain.invoke({"symbol": symbol, "data": json.dumps(data, indent=2)})

    update_token_usage("technical", analysis.usage_metadata)

    state["results"]["technical"] = {
        "data": data,
        "analysis": analysis.content
    }
    return state

# Dividends
def get_dividends(symbol: str):
    stock = yf.Ticker(symbol)
    div = stock.dividends
    logging.debug(f"yfinance dividends: {div.to_json(indent=2, date_format='iso')}")

    div.index = div.index.strftime('%Y-%m-%d')
    return div.to_dict()

# Market Analysis Node
def get_earnings_history(symbol: str):
    stock = yf.Ticker(symbol)
    income = stock.income_stmt
    logging.debug(f"yfinance earnings: {income.to_json(indent=2, date_format='iso')}")

    income_t = income.transpose()
    earnings_history = []
    for date, row in income_t.iterrows():
        earnings_history.append({
            'date': date.strftime('%Y-%m-%d'),
            'diluted_eps': row.get("Diluted EPS"),
            'basic_eps': row.get("Basic EPS"),
            'net_income': row.get("Net Income"),
            'net_income_common_stockholders': row.get("Net Income Common Stockholders"),
            'net_income_continuous_operations': row.get("Net Income Continuous Operations"),
            'total_operating_income_as_reported': row.get("Total Operating Income As Reported"),
            'operating_income': row.get("Operating Income"),
            'gross_profit': row.get("Gross Profit"),
            'total_revenue': row.get("Total Revenue"),
            'operating_revenue': row.get("Operating Revenue"),
        })
    logging.info("yfinance income_stmt data:")
    logging.info(f"{json.dumps(earnings_history, indent=2)}")
    return earnings_history

def get_market_data(symbol: str):
    # Fetch market data
    stock = yf.Ticker(symbol)
    info = stock.info

    logging.debug(f"yfinance info: {json.dumps(info, indent=2)}")
    data = {
        'sector': info.get('sector', 'Unknown'),
        'industry': info.get('industry', 'Unknown'),
        'market_cap': info.get('marketCap', 0),
        'beta': info.get('beta', 1.0),
        'pe_ratio': info.get('trailingPE', 0),
        'dividend_yield': info.get('dividendYield', 0),
        'divident_rate': info.get('dividendRate', 0),
        'trailing_eps': info.get('trailingEps', 0),
        'forward_pe': info.get('forwardPE', 0),
        'forward_eps': info.get('forwardEps', 0),
        'peg_ratio': info.get('pegRatio', 0),
        'price_to_book': info.get('priceToBook', 0),
        'price_to_sales': info.get('priceToSalesTrailing12Months', 0),
        'enterprise_value': info.get('enterpriseValue', 0),
        'current_ratio': info.get('currentRatio', 0),
        'quick_ratio': info.get('quickRatio', 0),
        'debt_to_equity': info.get('debtToEquity', 0),
        'revenue_growth': info.get('revenueGrowth', 0),
        'profit_margin': info.get('profitMargins', 0),
        'operating_margin': info.get('operatingMargins', 0),
        'return_on_assets': info.get('returnOnAssets', 0),
        'return_on_equity': info.get('returnOnEquity', 0),
        'revenue_per_share': info.get('revenuePerShare', 0),
        'gross_profit_margin': info.get('grossProfits', 0),
        'operating_cash_flow': info.get('operatingCashflow', 0),
        'free_cash_flow': info.get('freeCashflow', 0),
    }
    logging.info("yfinance market data:")
    logging.info(f"{json.dumps(data, indent=2)}")
    return data

def market_analysis(state: State) -> State:
    """Node for market analysis"""
    symbol = state["symbol"]
    logging.info(f"Starting market analysis for {symbol}...")
    llm = state["llm"]

    data = get_market_data(symbol)
    earnings_history = get_earnings_history(symbol)
    dividend_history = get_dividends(symbol)

    prompt = PromptTemplate.from_template(
        """Analyze the market context for {symbol}:

        Market Data:
        {data}

        Income Statement History:
        {earnings}

        Dividend History:
        {dividends}

        Provide:
        1. Market sentiment
        2. Sector analysis
        3. Risk assessment
        4. Market outlook
        5. Earnings and Revenue Growth: Use the Income Statement History to analyze the following metrics over time.
            a. Total Revenue / Operating Revenue: These represent the top line of a company's income statement and indicate the company's ability to generate sales from its primary operations. Consistent growth in revenue is a fundamental indicator of a healthy and expanding business.
            b. Gross Profit: This shows the profit a company makes after deducting the costs associated with producing its goods or services. It's a key indicator of a company's efficiency in managing its production costs and pricing strategy.
            c. Operating Income / Total Operating Income As Reported: This metric reflects the profit generated from a company's core operations before deducting interest and taxes. It's crucial for understanding the operational efficiency and profitability of the business itself, separate from financing or tax strategies.
            d. Net Income / Net Income Common Stockholders / Net Income From Continuing Operations: These are often considered the "bottom line" and represent the total profit of a company after all expenses, including taxes and interest, have been deducted. It's a comprehensive measure of profitability and what's available to shareholders.
            e. Diluted EPS (Earnings Per Share) / Basic EPS: EPS is a crucial metric for investors, as it indicates how much profit a company makes per outstanding share of stock. Tracking EPS over time reveals the company's ability to generate profits for its shareholders, even as the number of shares may change due to factors like stock options or conversions.
        6. Profitability Ratios:
            a. Net Profit Margin: How much profit does the company make for every dollar of revenue? A higher and consistent margin is desirable.
            b. Return on Equity (ROE): Measures how efficiently a company is using shareholder investments to generate profits. A healthy ROE (often 10-20% or higher, depending on the industry) indicates good management of shareholder capital.
            c. Return on Assets (ROA): Shows how efficiently a company is using its assets to generate earnings.
        7. Valuation Ratios:
            a. Price-to-Earnings (P/E) Ratio: Compares the stock price to its earnings per share. A high P/E might suggest overvaluation or high growth expectations, while a low P/E could indicate undervaluation or challenges. Compare it to industry peers and historical averages.
            c. PEG Ratio (Price/Earnings-to-Growth): This ratio takes into account the company's earnings growth, making it useful for evaluating growth stocks. A PEG ratio of 1 or less is generally considered favorable.
        8. Financial Health and Debt:
            a. Debt-to-Equity (D/E) Ratio: Indicates the proportion of debt a company uses to finance its assets relative to shareholder equity. A lower D/E ratio (e.g., 1 or lower) suggests less financial risk.
            b. Free Cash Flow (FCF): The cash a company generates after covering its operating expenses and capital expenditures. Strong and increasing FCF indicates a company's ability to fund growth, pay dividends, or buy back shares.
        9. Dividend Analysis (if applicable):
            a. Dividend Yield: The annual dividend payment as a percentage of the stock price.
            b. Dividend Payout Ratio: The percentage of earnings paid out as dividends. A sustainable payout ratio (e.g., below 60-70%) is important.
            c. Dividend Growth History: A consistent history of increasing dividends can indicate financial strength and commitment to shareholders.
        """
    )

    chain = prompt | llm
    analysis = chain.invoke({
        "symbol": symbol, 
        "data": json.dumps(data, indent=2), 
        "earnings": json.dumps(earnings_history, indent=2), 
        "dividends": json.dumps(dividend_history, indent=2)})
    update_token_usage("market", analysis.usage_metadata)

    state["results"]["market"] = {
        "data": data,
        "earnings": earnings_history,
        "dividends": dividend_history,
        "analysis": analysis.content
    }
    return state

# News Analysis Node
def get_news(symbol: str):
        # Fetch news
    stock = yf.Ticker(symbol)
    raw_news = stock.news
    logging.debug(f"yfinance news: {json.dumps(raw_news, indent=2)}")
    logging.info(f"yfinance returned {len(raw_news)} news items for {symbol}.")
    news = raw_news[:10]  # Last x news items

    news_data = []
    for item in news:
        content = item.get('content', {})
        news_data.append({
            'title': content.get('title', ''),
            'publisher': content.get('publisher', ''),
            'url': content.get('canonicalUrl', {}).get('url', ''),
            'timestamp': content.get('pubDate', '')
        })

    logging.info("yfinance news data:")
    logging.info(f"{json.dumps(news_data, indent=2)}")
    return news_data

def news_analysis(state: State) -> State:
    """Node for news analysis"""
    symbol = state["symbol"]
    logging.info(f"Fetching news for {symbol}...")
    llm = state["llm"]

    news_data = get_news(symbol)

    prompt = PromptTemplate.from_template(
        """Analyze these recent news items for {symbol}:
        {news}

        Provide:
        1. Overall sentiment
        2. Key developments
        3. Potential impact
        4. Risk factors
        """
    )

    chain = prompt | llm
    analysis = chain.invoke({"symbol": symbol, "news": json.dumps(news_data, indent=2)})
    update_token_usage("news", analysis.usage_metadata)

    state["results"]["news"] = {
        "data": news_data,
        "analysis": analysis.content
    }
    return state

# Final Recommendation Node
def generate_recommendation(state: State) -> State:
    """Node for final recommendation"""
    symbol = state["symbol"]
    logging.info(f"Generating final recommendation for {symbol}...")
    llm = state["llm"]
    results = state["results"]

    prompt = PromptTemplate.from_template(
        """Based on the following analyses for {symbol}, provide a final recommendation:

        Technical Analysis:
        {technical}

        Market Analysis:
        {market}

        News Analysis:
        {news}

        Provide:
        1. Final recommendation (Strong Buy/Buy/Hold/Sell/Strong Sell)
        2. Confidence score (1-10)
        3. Key reasons
        4. Risk factors
        5. Target price range including: low price target, high price target, percent gain from current to high price target
        """
    )

    chain = prompt | llm
    final_recommendation = chain.invoke({
        "symbol": symbol,
        "technical": results["technical"]["analysis"],
        "market": results["market"]["analysis"],
        "news": results["news"]["analysis"]
    })
    update_token_usage("recommendation", final_recommendation.usage_metadata)

    state["results"]["recommendation"] = final_recommendation.content
    return state

def calculate_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
    """Calculate RSI indicator"""
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def create_analysis_graph() -> Runnable:
    """Create the analysis workflow graph"""
    # Create workflow graph
    workflow = StateGraph(State)

    # Add nodes
    workflow.add_node("technical", technical_analysis)
    workflow.add_node("market", market_analysis)
    workflow.add_node("news", news_analysis)
    workflow.add_node("recommendation", generate_recommendation)

    # Define edges
    workflow.add_edge("technical", "market")
    workflow.add_edge("market", "news")
    workflow.add_edge("news", "recommendation")
    workflow.add_edge(START, "technical")

    # Set end node
    workflow.add_edge("recommendation", END)

    return workflow.compile()

class StockAdvisor:
    def __init__(self):
        self.llm = setup_llm()
        self.graph = create_analysis_graph()

    def analyze_stock(self, symbol: str) -> Dict:
        """Run complete stock analysis"""
        logging.info(f"Analyzing {symbol}...")

        # Initialize state
        init_sate: State = {
            "symbol": symbol,
            "llm": self.llm,
            "results": {}
        }

        # Run analysis
        final_state = self.graph.invoke(init_sate)
        return final_state["results"]

    def get_report_str(self, symbol: str, results: Dict) -> str:
        """Creates a formatted stock analysis report as a single string."""
        report = []
        report.append(f"\n=== Stock Analysis Report for {symbol} ===")
        report.append("\n--- Technical Analysis ---")
        report.append(results.get("technical", {}).get("analysis", "N/A"))
        report.append("\n--- Market Analysis ---")
        report.append(results.get("market", {}).get("analysis", "N/A"))
        report.append("\n--- News Analysis ---")
        report.append(results.get("news", {}).get("analysis", "N/A"))
        report.append("\n--- Final Recommendation ---")
        report.append(results.get("recommendation", "N/A"))
        return "\n".join(report)

    def save_report(self, file_basename: str, data: str):
        """Saves the analysis report to a file."""
        today = datetime.now().strftime("%m-%d-%Y")
        filename = f"output/OUTPUT-{file_basename}-{today}.md"
        with open(filename, 'w') as f:
            f.write(data)
        logging.info(f"Report saved to {filename}")

    def compare_stocks(self, symbols: List[str]) -> Dict:
        """Compare multiple stocks and recommend the best one"""
        logging.info(f"Comparing {', '.join(symbols)}...")
        analyses = {}
        for symbol in symbols:
            results = self.analyze_stock(symbol)
            analyses[symbol] = results
            results_str = self.get_report_str(symbol, results)
            print(results_str)

        prompt = PromptTemplate.from_template(
            """Given the following stock analyses:
            {analyses}

            Compare the stocks and recommend the best one to invest in.
            Provide a detailed explanation for your choice.
            """
        )

        chain = prompt | self.llm
        comparison = chain.invoke({"analyses": json.dumps(analyses, indent=2)})
        update_token_usage("comparison", comparison.usage_metadata)

        comparison_result = {
            "comparison": comparison.content,
            "token_usage": token_usage_stats
        }
        return comparison_result

def main(symbols: List[str], div_only: bool, news_only: bool, market_only: bool, tech_only: bool):
    """Run stock analysis and print results"""
    if len(symbols) > 1:
        advisor = StockAdvisor()
        comparison = advisor.compare_stocks(symbols)
        comparison_str = "\n=== Stock Comparison Result ==="
        comparison_str += comparison["comparison"]
        print(comparison_str)
        advisor.save_report('-'.join(symbols), comparison_str)
        print("\n--- Token Usage Statistics ---")
        print(json.dumps(token_usage_stats, indent=2))
    elif news_only:
        news_data = get_news(symbols[0])
    elif market_only:
        market_data = get_market_data(symbols[0])
        earnings_history = get_earnings_history(symbols[0])
    elif tech_only:
        technical_data = get_technical_indicators(symbols[0])
    elif div_only:
        dividends = get_dividends(symbols[0])
    else:
        advisor = StockAdvisor()
        results = advisor.analyze_stock(symbols[0])
        results_str = advisor.get_report_str(symbols[0], results)
        print(results_str)
        advisor.save_report(symbols[0], results_str)
        print("\n--- Token Usage Statistics ---")
        print(json.dumps(token_usage_stats, indent=2))

if __name__ == "__main__":
    examples = """
    Examples:
    
    # Get a full stock analysis for a single stock
    python graph.py AAPL

    # Get a full stock analysis for a single stock with verbose logging
    python graph.py AAPL --verbose

    # Compare multiple stocks
    python graph.py AAPL GOOG

    # Get the yFinance dividend history for a stock
    python graph.py AAPL --div

    # Get the yFinance news for a stock
    python graph.py AAPL --news

    # Get the yFinance market data for a stock
    python graph.py AAPL --market

    # Get the yFinance technical indicator data for a stock
    python graph.py AAPL --tech
    """
    parser = argparse.ArgumentParser(
        description="Gemini Stock Analysis Agent",
        epilog=examples,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("symbol", nargs='+', help="Stock symbol(s) to analyze (e.g., AAPL GOOG)")
    parser.add_argument("--div", action='store_true', help="Show yFinance Dividend History Only")
    parser.add_argument("--news", action='store_true', help="Show yFinance News Only")
    parser.add_argument("--market", action='store_true', help="Show yFinance Market Data Only")
    parser.add_argument("--tech", action='store_true', help="Show yFinance Technical Indicator Data Only")
    parser.add_argument("--verbose", action='store_true', help="Enable verbose (DEBUG) logging")
    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format='%(asctime)s - %(levelname)s - %(message)s')

    main(symbols=args.symbol, news_only=args.news, market_only=args.market, tech_only=args.tech, div_only=args.div)
