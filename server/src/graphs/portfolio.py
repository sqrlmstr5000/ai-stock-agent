


import json
from typing import Dict, List, Annotated
from datetime import datetime, timedelta
from typing_extensions import TypedDict
from langchain_core.prompts import PromptTemplate
from langgraph.graph import StateGraph, START, END
from langchain_core.runnables import Runnable
from langgraph.graph.message import add_messages
from server.src.utils.logging import setup_logger

# State object for PortfolioGraph
class State(TypedDict):
    messages: Annotated[list, add_messages]
    summaries: List[str]
    portfolio: List[dict]
    cash_balance: float
    llm: any
    results: Dict
    usage: Dict[str, dict]

class PortfolioGraph:
    def __init__(self, llm):
        self.logger = setup_logger(self.__class__.__name__)
        self.llm = llm

    # Portfolio Analysis Nodes
    async def dca_analysis(self, state: State) -> State:
        """Node for portfolio-level analysis"""
        llm = state["llm"]
        summaries = state["summaries"]
        cash_balance = state.get("cash_balance", 0)
        self.logger.info(f"Running portfolio analysis on {len(summaries)} summaries with cash balance ${cash_balance}...")
        prompt = PromptTemplate.from_template(
            """Given the following reports from our stock analyst:
            {summaries}

            Use these guiding priciples:
            - I have implemented a monthly Dollar Cost Averaging (DCA) plan in my brokerage account. 
            - I have budgeted for $2000-$5000 per month in potential buys but that's not a hard limit.
            - It's perfectly fine to not buy anything this month. Patience. 
            - Limit your recommendations to no more than 3 stocks.
            - I have the potential buying power of ${cash_balance} in my brokerage account. That cash is dedicated to this plan and is separate from my retirement accounts.
            - Your investment time horizons to consider are 1, 5 and 10 years.

            Please provide a short report containing the following:
            Make a recommendation of up to 3 stocks that I should invest more money in. If market conditions indicate I wait, be sure to consider that. Explain your detailed reasoning behind each recommendation.
            """
        )
        chain = prompt | llm
        analysis = await chain.ainvoke({"summaries": json.dumps(summaries, indent=2), "cash_balance": cash_balance})
        state["results"]["dca_analysis"] = analysis.content
        state["usage"]["dca_analysis"] = {
            "token_usage": getattr(analysis, "usage_metadata", None),
            "api_usage": None
        }
        return state
    
    # Economic Analysis Node (Portfolio-level, macroeconomic context)
    async def economic_analysis(self, state: State) -> State:
        """Node for macroeconomic/economic analysis using FRED data"""
        self.logger.info("Running economic (macro) analysis using FRED data...")
        llm = state["llm"]
        # Use last 30 days for FRED data
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        fred_trends = self.fred_provider.get_series_trend(start_date=start_date, end_date=end_date)

        prompt = PromptTemplate.from_template(
            """
            Given the following recent US macroeconomic indicators (with trend statistics), provide an analysis of the current economic environment and its potential impact on stock market investing and portfolio strategy. Highlight any notable trends, risks, or opportunities.

            GDP: {gdp}
            CPI (Inflation): {cpi}
            Unemployment Rate: {unemployment}
            Interest Rate (Fed Funds): {interest_rate}
            Consumer Confidence: {consumer_confidence}
            Business Confidence (PMI): {business_confidence}
            Retail Sales: {retail_sales}
            Industrial Production: {industrial_production}
            VIX (Volatility): {vix}
            Yield Curve (10Y-2Y): {yield_curve}
            Housing Starts: {housing_starts}
            PMI: {pmi}

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
            "business_confidence": json.dumps(fred_trends.get("business_confidence", {})),
            "retail_sales": json.dumps(fred_trends.get("retail_sales", {})),
            "industrial_production": json.dumps(fred_trends.get("industrial_production", {})),
            "vix": json.dumps(fred_trends.get("vix", {})),
            "yield_curve": json.dumps(fred_trends.get("yield_curve", {})),
            "housing_starts": json.dumps(fred_trends.get("housing_starts", {})),
            "pmi": json.dumps(fred_trends.get("pmi", {}))
        })
        state["results"]["economic_analysis"] = analysis.content
        state["usage"]["economic_analysis"] = {
            "token_usage": getattr(analysis, "usage_metadata", None),
            "api_usage": None
        }
        return state

    async def portfolio_analysis(self, state: State) -> State:
        """Node for portfolio-level analysis"""
        llm = state["llm"]
        portfolio = state["portfolio"]
        dca_result = state["results"].get("dca_analysis", "")
        economic_analysis = state["results"].get("economic_analysis", "")
        cash_balance = state.get("cash_balance", 0)
        self.logger.info(f"Running portfolio analysis on {len(portfolio)} portfolio with cash balance ${cash_balance}...")
        prompt = PromptTemplate.from_template(
            """Given the following stock portfolio:
            {portfolio}

            Here is the most recent DCA (Dollar Cost Averaging) analysis and recommendations:
            {dca_analysis}

            Here is the most recent macroeconomic analysis:
            {economic_analysis}

            Cash available for investment: ${cash_balance}

            Use these guiding priciples:
            - This account is a separate account from my retirement accounts so I have a higher tolerance for risk. This also means I'm not as worried about diversification but it is still something that I want to consider. 
            - The goal is to increase my yields and maximixe my returns.
            - I OK with holding underperforming assets if there is potential for future recovery. The stock showing signs of financial strength.
            - Your investment time horizons to consider are 1, 5 and 10 years.

            Please provide a report containing the following:
            1. With your years of experience and expert long-term technical guidance, please review my portfolio. Provide recommendations as to how I can optimize my portfolio. Make smart, analyitical, data-driven, investment decisions regarding selling off underperforming assets (with little future potential) and/or reinvesting in existing ones considering the DCA analysis, economic analysis, and available cash.

            2. As a separate section, create a list of 5 potential stocks, NOT in my portfolio, I should consider investing in based on your knowledge of my portfolio, the DCA recommendations, the economic analysis, and my goals. Explain your reasoning behind each.
            """
        )
        chain = prompt | llm
        analysis = await chain.ainvoke({
            "portfolio": json.dumps(portfolio, indent=2),
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

    async def analyze_portfolio(self, summaries: List[str], portfolio: List[dict], cash_balance: float = 0) -> Dict:
        """Run portfolio analysis on a list of stock summaries and portfolio holdings, including cash balance"""
        self.logger.info(f"Analyzing portfolio with {len(summaries)} summaries, {len(portfolio)} holdings, and cash balance ${cash_balance}...")
        portfolio_graph = self.create_portfolio_graph()
        init_state: State = {
            "messages": [],
            "summaries": summaries,
            "portfolio": portfolio,
            "cash_balance": cash_balance,
            "llm": self.llm,
            "results": {},
            "usage": {}
        }
        final_state = await portfolio_graph.ainvoke(init_state)
        return final_state["results"]