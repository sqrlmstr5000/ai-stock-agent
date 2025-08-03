
import json
from typing import Dict, List
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Annotated
from typing_extensions import TypedDict
from langchain_core.prompts import PromptTemplate
from langgraph.graph import StateGraph, START, END
from langchain_core.runnables import Runnable
from langgraph.graph.message import add_messages
from langchain_google_genai import ChatGoogleGenerativeAI

from server.src.utils.logging import setup_logger
from providers.yfinance import YFinanceProvider
from providers.alphavantage import AlphaVantageProvider
from models.marketdata import HistoricalTrackedValues
from utils.prompts import system_message

class State(TypedDict):
    # Messages have the type "list". The `add_messages` function
    # in the annotation defines how this state key should be updated
    # (in this case, it appends messages to the list, rather than overwriting them)
    messages: Annotated[list, add_messages]
    symbol: str
    llm: ChatGoogleGenerativeAI
    results: Dict
    yfinance_provider: YFinanceProvider
    alphavantage_provider: AlphaVantageProvider
    technical_analysis: str
    usage: Dict[str, dict]  # For per-node usage and API tracking

class FundamentalGraph:
    def __init__(self, llm,):
        self.logger = setup_logger(self.__class__.__name__)
        self.llm = llm

    # Market Analysis Node (without dividend analysis)
    async def market_analysis(self, state: State) -> State:
        """Node for market analysis (excluding dividend analysis)"""
        symbol = state["symbol"]
        self.logger.info(f"Starting market analysis for {symbol}...")
        llm = state["llm"]
        alphavantage_provider = state["alphavantage_provider"]

        data, market_request_count = alphavantage_provider.get_market_data()
        earnings_history, earnings_request_count = alphavantage_provider.get_earnings_history()

        prompt = PromptTemplate.from_template(
            """Analyze the market context for {symbol}:

            Market Data:
            {data}

            Earnings and Income Statement History:
            {earnings}

            Provide:
            1. Market sentiment
            2. Sector analysis
                Durable Competitive Advantage ("Economic Moat"): He seeks businesses with a sustainable advantage that protects them from competition. This "moat" allows the company to consistently generate high returns on capital.
            3. Risk assessment
            4. Market outlook
            5. Earnings and Revenue Growth: Use the Earnings and Income Statement History to analyze the following metrics over time.
                Total Revenue / Operating Revenue: These represent the top line of a company's income statement and indicate the company's ability to generate sales from its primary operations. Consistent growth in revenue is a fundamental indicator of a healthy and expanding business.
                Gross Profit: This shows the profit a company makes after deducting the costs associated with producing its goods or services. It's a key indicator of a company's efficiency in managing its production costs and pricing strategy.
                Operating Income / Total Operating Income As Reported: This metric reflects the profit generated from a company's core operations before deducting interest and taxes. It's crucial for understanding the operational efficiency and profitability of the business itself, separate from financing or tax strategies.
                Net Income / Net Income Common Stockholders / Net Income From Continuing Operations: These are often considered the "bottom line" and represent the total profit of a company after all expenses, including taxes and interest, have been deducted. It's a comprehensive measure of profitability and what's available to shareholders.
                Diluted EPS (Earnings Per Share) / Basic EPS: EPS is a crucial metric for investors, as it indicates how much profit a company makes per outstanding share of stock. Tracking EPS over time reveals the company's ability to generate profits for its shareholders, even as the number of shares may change due to factors like stock options or conversions.
                Return on Capital Employed (ROCE): A higher ROCE indicates better capital efficiency. It's a strong indicator of a company's ability to generate returns from its investments.
                Capital Efficiency Ratio: A higher ratio means the company is more effective at using its capital to generate revenue. This can vary significantly by industry.
            6. Profitability Ratios:
                Net Profit Margin: How much profit does the company make for every dollar of revenue? A higher and consistent margin is desirable.
                Return on Equity (ROE): Measures how efficiently a company is using shareholder investments to generate profits. A healthy ROE (often 10-20% or higher, depending on the industry) indicates good management of shareholder capital.
                Return on Assets (ROA): Shows how efficiently a company is using its assets to generate earnings.
            7. Valuation Ratios:
                Price-to-Earnings (P/E) Ratio: Compares the stock price to its earnings per share. A high P/E might suggest overvaluation or high growth expectations, while a low P/E could indicate undervaluation or challenges. Compare it to industry peers and historical averages.
                PEG Ratio (Price/Earnings-to-Growth): This ratio takes into account the company's earnings growth, making it useful for evaluating growth stocks. A PEG ratio of 1 or less is generally considered favorable.
            8. Financial Health and Debt:
                Debt-to-Equity (D/E) Ratio: Indicates the proportion of debt a company uses to finance its assets relative to shareholder equity. A lower D/E ratio (e.g., 1 or lower) suggests less financial risk.
                Free Cash Flow (FCF): The cash a company generates after covering its operating expenses and capital expenditures. Strong and increasing FCF indicates a company's ability to fund growth, pay dividends, or buy back shares.
            """
        )

        chain = prompt | llm
        analysis = await chain.ainvoke({
            "symbol": symbol, 
            "data": json.dumps(data.model_dump(), indent=2), 
            "earnings": json.dumps(earnings_history.model_dump(), indent=2)})

        state["results"]["market"] = {
            "data": data.model_dump(),
            "earnings": earnings_history.model_dump(),
            "analysis": analysis.content
        }
        # Store usage metadata and api usage in state["usage"]
        total_request_count = market_request_count + earnings_request_count
        state["usage"]["market_analysis"] = {
            "token_usage": getattr(analysis, "usage_metadata", None),
            "api_usage": {"alphavantage": total_request_count}
        }
        return state

    # Dividend Analysis Node
    async def dividend_analysis(self, state: State) -> State:
        """Node for dividend analysis"""
        symbol = state["symbol"]
        self.logger.info(f"Starting dividend analysis for {symbol}...")
        llm = state["llm"]
        yfinance_provider = state["yfinance_provider"]

        dividend_history = yfinance_provider.get_dividend_history()

        prompt = PromptTemplate.from_template(
            """Analyze the dividend history for {symbol}:

            Dividend History:
            {dividends}

            Provide:
            1. Dividend Yield: The annual dividend payment as a percentage of the stock price.
            2. Dividend Payout Ratio: The percentage of earnings paid out as dividends. A sustainable payout ratio (e.g., below 60-70%) is important.
            3. Dividend Growth History: A consistent history of increasing dividends can indicate financial strength and commitment to shareholders.
            4. Any notable trends or risks in the dividend policy.
            """
        )

        chain = prompt | llm
        analysis = await chain.ainvoke({
            "symbol": symbol,
            "dividends": json.dumps(dividend_history.model_dump(), indent=2)
        })

        state["results"]["dividend"] = {
            "dividends": dividend_history.model_dump(),
            "analysis": analysis.content
        }
        state["usage"]["dividend_analysis"] = {
            "token_usage": getattr(analysis, "usage_metadata", None),
            "api_usage": None
        }
        return state

    # News Analysis Node
    async def news_analysis(self, state: State) -> State:
        """Node for news analysis"""
        symbol = state["symbol"]
        self.logger.info(f"Fetching news for {symbol}...")
        llm = state["llm"]
        provider = state["yfinance_provider"]

        news_data = provider.get_news()

        prompt = PromptTemplate.from_template(
            """Analyze these recent news items for {symbol}:
            {news}

            Provide:
            1. Overall sentiment
            2. Key developments
            3. Potential impact
            4. Risk factors
            5. Sentiment Score (0-100, where 100 is very positive)
            """
        )

        chain = prompt | llm
        analysis = await chain.ainvoke({"symbol": symbol, "news": json.dumps(news_data.model_dump(), indent=2)})

        state["results"]["news"] = {
            "data": news_data.model_dump(),
            "analysis": analysis.content
        }
        state["usage"]["news_analysis"] = {
            "token_usage": getattr(analysis, "usage_metadata", None),
            "api_usage": None
        }
        return state

    # Final Recommendation Node
    async def generate_recommendation(self, state: State) -> State:
        """Node for final recommendation"""
        symbol = state["symbol"]
        technical_analysis = state["technical_analysis"]
        self.logger.info(f"Generating final recommendation for {symbol}...")
        llm = state["llm"]
        results = state["results"]

        prompt = PromptTemplate.from_template(
            """Based on the following analyses for {symbol}, provide a final recommendation:

            Technical Analysis:
            {technical}

            Market Analysis:
            {market}

            Dividend Analysis:
            {dividend}

            News Analysis:
            {news}

            Provide:
            1. Final recommendation (Strong Buy/Buy/Hold/Sell/Strong Sell)
            3. Confidence score (1-10)
            4. Key reasons
            5. Risk factors
            6. Target price range including: low price target, high price target, percent gain from current to high price target
            """
        )

        chain = prompt | llm
        final_recommendation = await chain.ainvoke({
            "symbol": symbol,
            "technical": technical_analysis,
            "market": results["market"]["analysis"],
            "dividend": results["dividend"]["analysis"],
            "news": results["news"]["analysis"]
        })

        state["results"]["recommendation"] = final_recommendation.content
        state["usage"]["generate_recommendation"] = {
            "token_usage": getattr(final_recommendation, "usage_metadata", None),
            "api_usage": None
        }
        return state

    async def export_analysis(self, state: dict) -> dict:
        """Node for exporting the analysis to a structured format. Accepts output_type as a parameter."""
        symbol = state["symbol"]
        if self.logger:
            self.logger.info(f"Exporting analysis for {symbol}...")
        llm = state["llm"]
        results = state["results"]

        prompt = PromptTemplate.from_template(
            """Based on the following analysis for {symbol}, extract the required information.

            Market Analysis:
            {market}

            News Analysis:
            {news}

            Final Recommendation:
            {recommendation}

            Extract the information and populate the structured output object.
            Set the report_date to today's date.
            """
        )

        chain = prompt | llm.with_structured_output(HistoricalTrackedValues)

        structured_data = await chain.ainvoke({
            "symbol": symbol,
            "market": results["market"]["analysis"],
            "news": results["news"]["analysis"],
            "recommendation": results["recommendation"]
        })

        state["results"]["structured_data"] = structured_data.model_dump()
        state["usage"]["export_analysis"] = {
            "token_usage": None,
            "api_usage": None
        }
        return state

    def create_analysis_graph(self) -> Runnable:
        """Create the analysis workflow graph with dividend analysis as its own node (no technical node)"""
        workflow = StateGraph(State)

        workflow.add_node("market", self.market_analysis)
        workflow.add_node("dividend", self.dividend_analysis)
        workflow.add_node("news", self.news_analysis)
        workflow.add_node("recommendation", self.generate_recommendation)
        workflow.add_node("export_analysis", self.export_analysis)

        # Define edges
        workflow.add_edge(START, "market")
        workflow.add_edge("market", "dividend")
        workflow.add_edge("dividend", "news")
        workflow.add_edge("news", "recommendation")
        workflow.add_edge("recommendation", "export_analysis")
        workflow.add_edge("export_analysis", END)
        return workflow.compile()

    async def analyze_stock(self, symbol: str, technical_analysis: str) -> Dict:
        """Run complete stock analysis"""
        self.logger.info(f"Analyzing {symbol}...")

        yfinance_provider = YFinanceProvider(symbol)
        alphavantage_provider = AlphaVantageProvider(symbol)

        # Initialize state
        init_state: State = {
            "messages": [
                {"role": "system", "content": system_message}
            ],
            "symbol": symbol,
            "llm": self.llm,
            "results": {},
            "yfinance_provider": yfinance_provider,
            "alphavantage_provider": alphavantage_provider,
            "technical_analysis": technical_analysis,
            "usage": {}  # Explicitly initialize usage dict
        }

        # Run analysis
        final_state = await self.graph.ainvoke(init_state)
        return {
            "results": final_state["results"],
            "usage": final_state.get("usage", {})
        }

    def get_report_str(self, symbol: str, results: Dict) -> str:
        """Creates a formatted stock analysis report as a single string"""
        report = []
        report.append(f"\n=== Stock Analysis Report for {symbol} ===")
        report.append("\n--- Technical Analysis ---")
        report.append(results.get("technical", {}).get("analysis", "N/A"))
        report.append("\n--- Market Analysis ---")
        report.append(results.get("market", {}).get("analysis", "N/A"))
        report.append("\n--- Dividend Analysis ---")
        report.append(results.get("dividend", {}).get("analysis", "N/A"))
        report.append("\n--- News Analysis ---")
        report.append(results.get("news", {}).get("analysis", "N/A"))
        report.append("\n--- Final Recommendation ---")
        report.append(results.get("recommendation", "N/A"))
        return "\n".join(report)

    def save_report(self, file_basename: str, data: any, report_type: str = 'str'):
        """Saves the analysis report to a file."""
        today = datetime.now().strftime("%m-%d-%Y")
        ext = "md" if report_type == 'str' else 'json'
        filename = f"output/OUTPUT-{file_basename}-{today}.{ext}"
        self.logger.debug(f"Report contents: {data}")
        with open(filename, 'w') as f:
            if report_type == 'str':
                f.write(data)
            else:
                json.dump(data, f, indent=2, default=str)
        self.logger.info(f"Report saved to {filename}")

    async def compare_stocks(self, symbols: List[str]) -> Dict:
        """Compare multiple stocks and recommend the best one"""
        self.logger.info(f"Comparing {', '.join(symbols)}...")
        analyses = {}
        for symbol in symbols:
            results = await self.analyze_stock(symbol)
            analyses[symbol] = results
            results_str = self.get_report_str(symbol, results)
            print(results_str)
            self.save_report(symbol, results_str)
            self.save_report(symbol, results.get("structured_data", {}), report_type='json')

        prompt = PromptTemplate.from_template(
            """Given the following stock analyses:
            {analyses}

            Compare the stocks and recommend the best one to invest in.
            Provide a detailed explanation for your choice.
            """
        )

        chain = prompt | self.llm
        comparison = await chain.ainvoke({"analyses": json.dumps(analyses, indent=2)})
        #self.update_token_usage("comparison", comparison.usage_metadata)

        comparison_result = {
            "comparison": comparison.content
        }
        return comparison_result