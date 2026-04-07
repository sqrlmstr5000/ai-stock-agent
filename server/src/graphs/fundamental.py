import json
from typing import Dict, List
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Annotated
from typing_extensions import TypedDict
import operator
from langchain_core.prompts import PromptTemplate
from langgraph.graph import StateGraph, START, END
from langchain_core.runnables import Runnable
from langgraph.graph.message import add_messages
from langchain_google_genai import ChatGoogleGenerativeAI

from utils.langchain_handler import VerboseFileCallbackHandler
from utils.logging import setup_logger
logger = setup_logger(__name__)
from providers.yfinance import YFinanceProvider
from providers.alphavantage import AlphaVantageProvider
from models.marketdata import HistoricalTrackedValues
from utils.prompts import system_message
from utils.common import merge_dict_results, take_latest_value
from graphs.technical import TechnicalAnalysisGraph

class State(TypedDict):
    # Messages have the type "list". The `add_messages` function
    # in the annotation defines how this state key should be updated
    # (in this case, it appends messages to the list, rather than overwriting them)
    messages: Annotated[list, add_messages]
    symbol: Annotated[str, take_latest_value]  # Symbol will use the latest value in concurrent updates
    # Use our custom merge function for results dict to handle concurrent updates
    results: Annotated[Dict, merge_dict_results]
    # Also use our custom merge function for usage dict
    usage: Annotated[Dict[str, dict], merge_dict_results]  # For per-node usage and API tracking
    period: Annotated[str, take_latest_value]  # For technical analysis - will use latest value

class FundamentalGraph:
    def __init__(self, llm: ChatGoogleGenerativeAI, yfinance_provider: YFinanceProvider, alphavantage_provider: AlphaVantageProvider):
        # Use module-level logger
        self.llm = llm
        self.handler = VerboseFileCallbackHandler(graph_name=self.__class__.__name__)
        self.technical_graph = TechnicalAnalysisGraph(llm=llm, yfinance_provider=yfinance_provider, alphavantage_provider=alphavantage_provider)
        self.yfinance_provider = yfinance_provider
        self.alphavantage_provider = alphavantage_provider
        self.graph = self.create_analysis_graph()

    # Market Analysis Node (without dividend analysis)

    async def market_analysis(self, state: State) -> State:
        """Node for market analysis (excluding dividend analysis)"""
        symbol = state["symbol"]
        logger.info(f"Starting market analysis for {symbol}...")
        llm = self.llm
        alphavantage_provider = self.alphavantage_provider

        data, market_request_count = alphavantage_provider.get_market_data(symbol)
        earnings_history, earnings_request_count = alphavantage_provider.get_earnings_history(symbol)

        if data is None:
            logger.error(f"No market data available for {symbol}. Stopping graph execution.")
            raise RuntimeError(f"No market data available for {symbol}. Stopping graph execution.")
        
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
            "data": {
                "market": data.model_dump(),
                "earnings": earnings_history.model_dump(),
            },
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
        logger.info(f"Starting dividend analysis for {symbol}...")
        llm = self.llm
        yfinance_provider = self.yfinance_provider

        dividend_history = yfinance_provider.get_dividend_history(symbol)

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
            "data": dividend_history.model_dump(),
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
        logger.info(f"Fetching news for {symbol}...")
        llm = self.llm
        provider = self.yfinance_provider

        news_data = provider.get_news(symbol)

        prompt = PromptTemplate.from_template(
            """Analyze these recent news items for {symbol}:
            {news}

            Provide a report including:
            1. Overall sentiment
            2. Key developments
            3. Potential impact 
                a. Positive Catalysts: Upcoming earnings beats, product launches, or favorable macroeconomic shifts (e.g., interest rate cuts).
                b. Volume Expansion: Identifying if big institutional buyers are entering the stock.
            4. Risk factors inc as
                a. Macro Headwinds: Analyzing sector-wide weakness or geopolitical risks that could override individual stock strength.
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

    # Validate Section Node
    async def validate_section(self, state: State, section: str) -> State:
        """Reusable node to validate a specific section against its raw data."""
        symbol = state["symbol"]
        logger.info(f"Validating {section} section for {symbol}...")
        llm = self.llm
        results = state["results"]

        prompt = PromptTemplate.from_template(
            """You are a senior financial analyst and fact-checker. Your task is to meticulously review a research report section and the raw data it was based on to ensure 100% accuracy.

            **Section to validate:** {section_text}

            **Raw API data:** {raw_data}

            Instructions:
            1. Carefully compare every numerical value and key statement in the section against the raw data.
            2. Identify and list any and all inconsistencies, factual errors, misinterpretations or assumptions not supported by the raw data.
            3. For each error found, state the incorrect information from the report and the correct information from the raw data.
            4. If the section is completely accurate, state "No errors found."
            5. Format your output as a bulleted list of findings.
                **Example Output:**
                - **Error:** Report states "Net income was $50 million."
                - **Correction:** Raw data shows "Net income was $45 million."
            """
        )

        section_text = results.get(section, {}).get("analysis", "")
        raw_data = results.get(section, {}).get("data", "")

        chain = prompt | llm
        validation = await chain.ainvoke({
            "section_text": section_text,
            "raw_data": raw_data
        })

        # Store the validation result under a section-specific key
        state["results"][f"validate_{section}"] = validation.content
        state["usage"][f"validate_{section}"] = {
            "token_usage": getattr(validation, "usage_metadata", None),
            "api_usage": None
        }
        return state

    async def revise_section(self, state: State, section: str) -> State:
        """Reusable node to revise a specific section based on fact-checker corrections."""
        symbol = state["symbol"]
        logger.info(f"Revising {section} section for {symbol} based on fact-checker corrections...")
        llm = self.llm
        results = state["results"]

        prompt = PromptTemplate.from_template(
            """You are a financial writer and editor. Your task is to revise a research report section based on a list of specific corrections.
           
            Instructions:
                1. Read the **corrections from the fact-checker** carefully.
                2. Directly apply each correction to the **original section**.
                3. Do not add new information or remove accurate information.
                4. Ensure the final revised section is a coherent and well-written document.
                5. Provide the final, corrected section as your output. If no corrections are needed, provide the original section unchanged.
                6. Do not include the Original Section in the output. Only the revised report section with revisions incorporated.
            
            **Corrections from Fact-Checker:** {validation_notes}

            **Original Section:** {original_section}
            """
        )

        original_section = results.get(section, {}).get("analysis", "")
        validation_notes = results.get(f"validate_{section}", "")

        chain = prompt | llm
        revised_section = await chain.ainvoke({
            "original_section": original_section,
            "validation_notes": validation_notes
        })

        state["results"][f"revised_{section}"] = {
            "analysis": revised_section.content,
        }
        state["usage"][f"revised_{section}"] = {
            "token_usage": getattr(revised_section, "usage_metadata", None),
            "api_usage": None
        }
        return state

    # Final Recommendation Node

    async def generate_recommendation(self, state: State) -> State:
        """Node for final recommendation"""
        symbol = state["symbol"]
        logger.info(f"Generating final recommendation for {symbol}...")
        llm = self.llm
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
            2. One year target price range including: low price target, high price target, percent gain from current to high price target
            3. Confidence score (1-10)
            4. Write a bull case theory focused on momentum and catalysts. Look for reasons why the price will move significantly higher over the next few weeks to months. Consider the following factors:
                Trend Confirmation: Looking for "Higher Highs" and "Higher Lows" on daily/weekly charts.
                Positive Catalysts: Upcoming earnings beats, product launches, or favorable macroeconomic shifts (e.g., interest rate cuts).
                Volume Expansion: Identifying if big institutional buyers are entering the stock.
                Mean Reversion: Checking if the stock is "oversold" on the RSI but showing a hidden bullish divergence.
            5. Write a bear case theory focused on risks and potential pitfalls. Look for the "Hidden Trap" that could cause the trade to fail. Consider the following factors:
                Resistance Levels: Identifying "heavy" supply zones where sellers historically take control.
                Macro Headwinds: Analyzing sector-wide weakness or geopolitical risks that could override individual stock strength.
                Valuation Fatigue: Flagging if a stock is trading at historical extremes (e.g., an unsustainably high P/E ratio).
                Technical Breakdowns: Looking for "Head and Shoulders" patterns or momentum exhaustion (RSI overbought).
            """
        )

        def get_section(section_name, default=None):
            # Prefer revised_{section} if available, else fall back to original analysis
            revised = results.get(f"revised_{section_name}")
            if revised:
                return revised
            return results.get(section_name, {}).get("analysis", default)

        chain = prompt | llm
        final_recommendation = await chain.ainvoke({
            "symbol": symbol,
            "technical": get_section("technical", ""),
            "market": get_section("market", ""),
            "dividend": get_section("dividend", ""),
            "news": get_section("news", "")
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
        logger.info(f"Exporting analysis for {symbol}...")
        llm = self.llm
        results = state["results"]


        prompt = PromptTemplate.from_template(
            """Based on the following analysis for {symbol}, extract the required information.

            Technical Analysis:
            {technical}

            Market Analysis:
            {market}

            News Analysis:
            {news}

            Final Recommendation:
            {recommendation}

            Extract the information and populate the structured output object.
            """
        )

        def get_section(section_name, default=None):
            # Prefer revised_{section} if available, else fall back to original analysis
            revised = results.get(f"revised_{section_name}")
            if revised:
                return revised
            return results.get(section_name, {}).get("analysis", default)

        chain = prompt | llm.with_structured_output(HistoricalTrackedValues)

        structured_data = await chain.ainvoke({
            "symbol": symbol,
            "technical": get_section("technical", ""),
            "market": get_section("market", ""),
            "news": get_section("news", ""),
            "recommendation": results.get("recommendation", "")
        })

        state["results"]["structured_data"] = structured_data.model_dump()
        state["usage"]["export_analysis"] = {
            "token_usage": None, # usage_metadata is not available when using llm.with_structured_output
            "api_usage": None
        }
        return state

    def create_analysis_graph(self) -> Runnable:
        """Create the analysis workflow graph with technical analysis node included."""
        graph = StateGraph(State)
        graph.add_node("technical", self.technical_graph.technical_analysis)
        graph.add_node("market", self.market_analysis)
        graph.add_node("dividend", self.dividend_analysis)
        graph.add_node("news", self.news_analysis)
        # Add per-section validation nodes using async functions
        async def validate_technical(state):
            return await self.validate_section(state, "technical")
        async def validate_market(state):
            return await self.validate_section(state, "market")
        async def validate_dividend(state):
            return await self.validate_section(state, "dividend")
        async def validate_news(state):
            return await self.validate_section(state, "news")

        graph.add_node("validate_technical", validate_technical)
        graph.add_node("validate_market", validate_market)
        graph.add_node("validate_dividend", validate_dividend)
        graph.add_node("validate_news", validate_news)

        # Add per-section revise nodes using async functions
        async def revise_technical(state):
            return await self.revise_section(state, "technical")
        async def revise_market(state):
            return await self.revise_section(state, "market")
        async def revise_dividend(state):
            return await self.revise_section(state, "dividend")
        async def revise_news(state):
            return await self.revise_section(state, "news")

        graph.add_node("revise_technical", revise_technical)
        graph.add_node("revise_market", revise_market)
        graph.add_node("revise_dividend", revise_dividend)
        graph.add_node("revise_news", revise_news)
        graph.add_node("recommendation", self.generate_recommendation)
        graph.add_node("export_analysis", self.export_analysis)

        # Define edges for the sequential first part of the analysis
        graph.add_edge(START, "technical")
        graph.add_edge("technical", "market")
        graph.add_edge("market", "dividend")
        graph.add_edge("dividend", "news")

        # Fan out from news to validation nodes (parallelization)
        graph.add_edge("news", "validate_technical")
        graph.add_edge("news", "validate_market")
        graph.add_edge("news", "validate_dividend")
        graph.add_edge("news", "validate_news")
        
        # Connect each validation node to its corresponding revision node
        graph.add_edge("validate_technical", "revise_technical")
        graph.add_edge("validate_market", "revise_market")
        graph.add_edge("validate_dividend", "revise_dividend")
        graph.add_edge("validate_news", "revise_news")
        
        # Add a join node to wait for all revisions before proceeding
        async def join_revisions(state):
            # Only proceed if all revised sections are present
            required = ["technical", "market", "dividend", "news"]
            if all(f"revised_{section}" in state["results"] for section in required):
                logger.info(f"All {len(required)} sections validated and revised. Proceeding to recommendation.")
                return state
            # Count how many are done
            completed = sum(1 for section in required if f"revised_{section}" in state["results"])
            logger.info(f"Waiting for all sections to be revised. Progress: {completed}/{len(required)}")
            # Otherwise, do nothing (graph will wait)
            return None

        graph.add_node("join_revisions", join_revisions)
        graph.add_edge("revise_technical", "join_revisions")
        graph.add_edge("revise_market", "join_revisions")
        graph.add_edge("revise_dividend", "join_revisions")
        graph.add_edge("revise_news", "join_revisions")
        graph.add_edge("join_revisions", "recommendation")
        graph.add_edge("recommendation", "export_analysis")
        graph.add_edge("export_analysis", END)
        return graph.compile()

    async def analyze_stock(self, symbol: str) -> Dict:
        """Run complete stock analysis"""
        logger.info(f"Analyzing {symbol}...")

        # Initialize state
        init_state: State = {
            "messages": [
                {"role": "system", "content": system_message}
            ],
            "symbol": symbol,
            "results": {},
            "usage": {},  # Explicitly initialize usage dict
            "period": "1y"  # Set period to 1y for technical analysis
        }

        # Run analysis
        final_state = await self.graph.ainvoke(init_state, config={"callbacks": [self.handler]})
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
        logger.debug(f"Report contents: {data}")
        with open(filename, 'w') as f:
            if report_type == 'str':
                f.write(data)
            else:
                json.dump(data, f, indent=2, default=str)
        logger.info(f"Report saved to {filename}")

    async def compare_stocks(self, symbols: List[str]) -> Dict:
        """Compare multiple stocks and recommend the best one"""
        logger.info(f"Comparing {', '.join(symbols)}...")
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