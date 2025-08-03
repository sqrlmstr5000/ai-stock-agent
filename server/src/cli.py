import argparse
import json
import logging
from typing import List
from providers.yfinance import YFinanceProvider
from providers.alphavantage import AlphaVantageProvider
from graph import StockAdvisor

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
        print(json.dumps(comparison["token_usage"], indent=2))
    elif news_only:
        provider = YFinanceProvider(symbols[0])
        news_data = provider.get_news()
        #print(json.dumps(news_data.model_dump(), indent=2))
    elif market_only:
        alphavantage_provider = AlphaVantageProvider(symbols[0])
        yfinance_provider = YFinanceProvider(symbols[0])
        market_data = yfinance_provider.get_market_data()
        earnings_history = alphavantage_provider.get_earnings_history()
        #print(json.dumps({
        #    "market_data": market_data.model_dump(),
        #    "earnings_history": earnings_history.model_dump()
        #}, indent=2))
    elif tech_only:
        provider = YFinanceProvider(symbols[0])
        technical_data = provider.get_technical_indicators()
        #print(json.dumps(technical_data.model_dump(), indent=2))
    elif div_only:
        provider = YFinanceProvider(symbols[0])
        dividends = provider.get_dividend_history()
        print(json.dumps(dividends.model_dump(), indent=2))
    else:
        advisor = StockAdvisor()
        results = advisor.analyze_stock(symbols[0])
        results_str = advisor.get_report_str(symbols[0], results)
        print(results_str)
        advisor.save_report(symbols[0], results_str)
        advisor.save_report(symbols[0], results.get("structured_data", {}), report_type='json')
        print("\n--- Token Usage Statistics ---")
        print(json.dumps(results.get("token_usage", {}), indent=2))

if __name__ == "__main__":
    examples = """
    Examples:
    
    # Get a full stock analysis for a single stock
    python cli.py AAPL

    # Get a full stock analysis for a single stock with verbose logging
    python cli.py AAPL --verbose

    # Compare multiple stocks
    python cli.py AAPL GOOG

    # Get the yFinance dividend history for a stock
    python cli.py AAPL --div

    # Get the yFinance news for a stock
    python cli.py AAPL --news

    # Get the yFinance market data for a stock
    python cli.py AAPL --market

    # Get the yFinance technical indicator data for a stock
    python cli.py AAPL --tech
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
