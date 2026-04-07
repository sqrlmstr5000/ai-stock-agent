
import json
from typing import Dict, Annotated
from typing_extensions import TypedDict
from langchain_core.prompts import PromptTemplate
from langgraph.graph import StateGraph, START, END
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langchain_google_genai import ChatGoogleGenerativeAI

from utils.langchain_handler import VerboseFileCallbackHandler
from utils.logging import setup_logger
logger = setup_logger(__name__)
from providers.yfinance import YFinanceProvider
from providers.alphavantage import AlphaVantageProvider
from models.marketdata import TechnicalHistoricalTrackedValues

# State object for TechnicalAnalysisGraph
class State(TypedDict):
    messages: Annotated[list, add_messages]
    symbol: str
    results: Dict
    usage: Dict[str, dict]
    period: str  # Added period to the state

class TechnicalAnalysisGraph:
    def __init__(self, llm: ChatGoogleGenerativeAI, yfinance_provider: YFinanceProvider, alphavantage_provider: AlphaVantageProvider):
        # Use module-level logger
        self.llm = llm
        self.yfinance_provider = yfinance_provider
        self.alphavantage_provider = alphavantage_provider
        self.handler = VerboseFileCallbackHandler(graph_name=self.__class__.__name__)

    async def technical_analysis(self, state: State) -> State:
        """Node for technical analysis (standalone graph)"""
        symbol = state["symbol"]
        logger.info(f"Starting technical analysis for {symbol}...")
        llm = self.llm
        provider = self.yfinance_provider
        period = state.get("period", "1d")

        data = provider.get_technical_indicators(symbol, period=period)
        if data is None:
            logger.error(f"No technical indicator data available for {symbol} with period '{period}'. Stopping graph execution.")
            state["results"]["technical"] = {
                "data": None,
                "analysis": "No technical indicator data available. Analysis aborted."
            }
            state["usage"] = {
                "technical_analysis": {
                    "token_usage": None,
                    "api_usage": None
                }
            }
            return state

        prompt = PromptTemplate.from_template(
            """Analyze these technical indicators for {symbol} over the last {period}:
            {data}

            Provide:
            1.  **Current Price:** The most recent price provided.
            2.  **Trend Analysis:**
                * **Short-term (20-day SMA):** Is the price above/below, and what does it suggest?
                * **Medium-term (50-day SMA):** Is the price above/below, and what does it suggest?
                * **Long-term (200-day SMA):** Is the price above/below, and what does it suggest?
                * **RSI Interpretation:** Is it overbought, oversold, or neutral? What momentum does it indicate?
                * **Volume Trend Interpretation:** Is volume confirming or diverging from price trends?
                * **MACD Interpretation:** Analyze the MACD, signal line, and histogram. Is there a bullish or bearish crossover? What does the MACD suggest about momentum and trend strength?
                * **Bollinger Bands Interpretation:** Is the price near the upper or lower band? Is volatility increasing or decreasing? Are there any squeeze or breakout signals?
                * **OBV Interpretation:** Analyze the On-Balance Volume. Is OBV rising or falling? Is it confirming price trends or diverging? What does it suggest about buying/selling pressure?
                * **ATR Interpretation:** Analyze the Average True Range. Is volatility increasing or decreasing? What does the ATR suggest about risk and potential price movement?
            3.  **Support and Resistance Levels:** Identify key levels based on the provided historical OHLCV data. Provide 1-2 immediate support levels and 1-2 immediate resistance levels with brief explanations.
            4.  **Technical Rating:** A single, clear rating (e.g., "Strong Bullish", "Bullish", "Neutral", "Bearish", "Strong Bearish") based on the combined analysis.
            5.  **Key Signals & Actionable Insights:** Summarize significant technical patterns, potential breakouts/breakdowns, or other critical signals derived from the indicators. Suggest potential short-term implications.
            """
        )

        chain = prompt | llm
        analysis = await chain.ainvoke({
            "symbol": symbol, 
            "data": json.dumps(data.model_dump(), indent=2), 
            "period": period
        })

        state["results"]["technical"] = {
            "data": data.model_dump(),
            "analysis": analysis.content
        }
        state["usage"] = {
            "technical_analysis": {
                "token_usage": getattr(analysis, "usage_metadata", None),
                "api_usage": None
            }
        }
        return state
    
    def create_graph(self):
        """Create the technical analysis graph (no export_analysis node)."""
        graph = StateGraph(State)
        graph.add_node("technical_analysis", self.technical_analysis)
        graph.add_edge(START, "technical_analysis")
        graph.add_edge("technical_analysis", END)
        return graph.compile()

    async def analyze_technical(self, symbol: str, period: str = "1d") -> dict:
        """Run the technical analysis graph for a given stock symbol."""
        graph = self.create_graph()
        initial_state = {
            "messages": [],
            "symbol": symbol,
            "results": {},
            "usage": {},
            "period": period # Set period to "1d" by default
        }
        result = await graph.ainvoke(initial_state, config={"callbacks": [self.handler]})
        return result["results"]
