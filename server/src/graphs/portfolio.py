


import json
from typing import Dict, List, Annotated
from datetime import datetime, timedelta
from typing_extensions import TypedDict
from langchain_core.prompts import PromptTemplate
from langgraph.graph import StateGraph, START, END
from langchain_core.runnables import Runnable
from langgraph.graph.message import add_messages

from utils.langchain_handler import VerboseFileCallbackHandler
from utils.logging import setup_logger
logger = setup_logger(__name__)
from providers.fred import FredProvider
from models.models import Portfolio

# State object for PortfolioGraph
class State(TypedDict):
    messages: Annotated[list, add_messages]
    summaries: List[str]
    portfolio: Portfolio
    holdings: List[dict]
    cash_balance: float
    llm: any
    fred_provider: FredProvider
    results: Dict
    usage: Dict[str, dict]

class PortfolioGraph:
    def __init__(self, llm):
        # Use module-level logger
        self.llm = llm
        self.handler = VerboseFileCallbackHandler(graph_name=self.__class__.__name__)

    # Portfolio Analysis Nodes
    async def dca_analysis(self, state: State) -> State:
        """Node for portfolio-level analysis"""
        llm = state["llm"]
        summaries = state["summaries"]
        portfolio = state["portfolio"]
        cash_balance = state.get("cash_balance", 0)
        logger.info(f"Running DCA analysis on {len(summaries)} summaries with cash balance ${cash_balance}...")
        prompt = PromptTemplate.from_template(
            """Given the following reports from our stock analyst:
            {summaries}

            Using these rules and guidelines in your analysis:
            {rules}
            - I have the potential buying power of ${cash_balance} in my brokerage account, which is dedicated to this plan and is separate from my retirement accounts.

            Please provide a short report containing the following:
            Make a recommendation of up to 3 stocks that I should invest more money in. 
            Explain your detailed reasoning behind each recommendation. 
            """
        )
        chain = prompt | llm
        analysis = await chain.ainvoke({
            "summaries": json.dumps(summaries, indent=2), 
            "rules": portfolio.rules,
            "cash_balance": cash_balance
        })

        state["results"]["dca_analysis"] = analysis.content
        state["usage"]["dca_analysis"] = {
            "token_usage": getattr(analysis, "usage_metadata", None),
            "api_usage": None
        }
        return state
    
    # Economic Analysis Node (Portfolio-level, macroeconomic context)
    async def economic_analysis(self, state: State) -> State:
        """Node for macroeconomic/economic analysis using FRED data"""
        logger.info("Running economic (macro) analysis using FRED data...")
        llm = state["llm"]
        # Use last 180 days for FRED data
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d")
        fred_provider = state.get("fred_provider")
        fred_trends, request_count = fred_provider.get_series_trend(start_date=start_date, end_date=end_date) if fred_provider else {}

        prompt = PromptTemplate.from_template(
            """
            Given the following recent US macroeconomic indicators (with trend statistics), provide an analysis of the current economic environment and its potential impact on stock market investing and portfolio strategy. Highlight any notable trends, risks, or opportunities.

            GDP: {gdp}
            Consumer Price Index for All Urban Consumers: All Items in U.S. City Average: {cpi}
            Unemployment Rate: {unemployment}
            Federal Funds Effective Rate: {interest_rate}
            University of Michigan: Consumer Sentiment: {consumer_confidence}
            Advance Retail Sales: Retail Trade and Food Services: {retail_sales}
            Industrial Production: Total Index: {industrial_production}
            CBOE Volatility Index: VIX: {vix}
            10-Year Treasury Constant Maturity Minus 2-Year Treasury Constant Maturity: {yield_curve}
            New Privately-Owned Housing Units Started: Total Units: {housing_starts}
            Producer Price Index by Commodity: All Commodities: {ppi}

            Each indicator is a JSON summary with start/end values, trend, rate_of_change, min/max, mean, and std_dev.

            Provide:
            1. Summary of the current macroeconomic environment
            2. Key risks and opportunities for investors
            3. How these factors might influence portfolio allocation or stock selection
            4. Any notable trends or signals to watch
            """
        )

        chain = prompt | llm
        analysis = await chain.ainvoke({
            "gdp": json.dumps(fred_trends.get("gdp", {})),
            "cpi": json.dumps(fred_trends.get("cpi", {})),
            "unemployment": json.dumps(fred_trends.get("unemployment", {})),
            "interest_rate": json.dumps(fred_trends.get("interest_rate", {})),
            "consumer_confidence": json.dumps(fred_trends.get("consumer_confidence", {})),
            "retail_sales": json.dumps(fred_trends.get("retail_sales", {})),
            "industrial_production": json.dumps(fred_trends.get("industrial_production", {})),
            "vix": json.dumps(fred_trends.get("vix", {})),
            "yield_curve": json.dumps(fred_trends.get("yield_curve", {})),
            "housing_starts": json.dumps(fred_trends.get("housing_starts", {})),
            "ppi": json.dumps(fred_trends.get("ppi", {}))
        })
        state["results"]["economic_analysis"] = analysis.content
        state["usage"]["economic_analysis"] = {
            "token_usage": getattr(analysis, "usage_metadata", None),
            "api_usage": {"fred": request_count}
        }
        return state

    async def portfolio_analysis(self, state: State) -> State:
        """Node for portfolio-level analysis"""
        llm = state["llm"]
        portfolio = state["portfolio"]
        holdings = state["holdings"]
        dca_result = state["results"].get("dca_analysis", "")
        economic_analysis = state["results"].get("economic_analysis", "")
        cash_balance = state.get("cash_balance", 0)
        logger.info(f"Running portfolio analysis on {len(holdings)} symbols with cash balance ${cash_balance}...")
        prompt = PromptTemplate.from_template(
            """Given the following stock portfolio holdings:
            {holdings}

            Here is the most recent DCA (Dollar Cost Averaging) analysis and recommendations:
            {dca_analysis}

            Here is the most recent macroeconomic analysis:
            {economic_analysis}

            Cash available for investment: ${cash_balance}

            Use these rules and guidelines in your analysis:
            {rules}

            Please provide a report containing the following:
            {report}
            """
        )
        chain = prompt | llm
        analysis = await chain.ainvoke({
            "rules": portfolio.rules,
            "report": portfolio.report,
            "holdings": json.dumps(holdings, indent=2),
            "dca_analysis": dca_result,
            "economic_analysis": economic_analysis,
            "cash_balance": cash_balance
        })
        state["results"]["portfolio_analysis"] = analysis.content
        state["usage"]["portfolio_analysis"] = {
            "token_usage": getattr(analysis, "usage_metadata", None),
            "api_usage": None
        }
        return state

    # Portfolio Graph
    def create_portfolio_graph(self) -> Runnable:
        workflow = StateGraph(State)
        workflow.add_node("economic_analysis", self.economic_analysis)
        workflow.add_node("dca_analysis", self.dca_analysis)
        workflow.add_node("portfolio_analysis", self.portfolio_analysis)
        workflow.add_edge(START, "economic_analysis")
        workflow.add_edge("economic_analysis", "dca_analysis")
        workflow.add_edge("dca_analysis", "portfolio_analysis")
        workflow.add_edge("portfolio_analysis", END)
        return workflow.compile()

    async def analyze_portfolio(self, summaries: List[str], holdings: List[dict], portfolio: Portfolio, cash_balance: float = 0) -> Dict:
        """Run portfolio analysis on a list of stock summaries and holdings, including cash balance"""
        logger.info(f"Analyzing portfolio with {len(summaries)} summaries, {len(holdings)} holdings, and cash balance ${cash_balance}...")
        portfolio_graph = self.create_portfolio_graph()
        fred_provider = FredProvider()  # Initialize FRED provider
        init_state: State = {
            "messages": [],
            "summaries": summaries,
            "portfolio": portfolio,
            "holdings": holdings,
            "cash_balance": cash_balance,
            "llm": self.llm,
            "fred_provider": fred_provider,
            "results": {},
            "usage": {}
        }
        final_state = await portfolio_graph.ainvoke(init_state, config={"callbacks": [self.handler]})
        return {
            "results": final_state["results"],
            "usage": final_state.get("usage", {})
        }