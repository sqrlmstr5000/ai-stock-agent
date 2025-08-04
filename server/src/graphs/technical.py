
import json
from typing import Dict, Annotated
from typing_extensions import TypedDict
from langchain_core.prompts import PromptTemplate
from langgraph.graph import StateGraph, START, END
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from server.src.utils.logging import setup_logger
from server.src.models.marketdata import TechnicalHistoricalTrackedValues

# State object for TechnicalAnalysisGraph
class State(TypedDict):
    messages: Annotated[list, add_messages]
    symbol: str
    llm: any
    yfinance_provider: any
    results: Dict
    usage: Dict[str, dict]
    period: str  # Added period to the state

class TechnicalAnalysisGraph:
    def __init__(self, llm):
        self.logger = setup_logger(self.__class__.__name__)
        self.llm = llm

    async def technical_analysis(self, state: State) -> State:
        """Node for technical analysis (standalone graph)"""
        symbol = state["symbol"]
        self.logger.info(f"Starting technical analysis for {symbol}...")
        llm = state["llm"]
        provider = state["yfinance_provider"]
        period = state.get("period", "1d")

        data = provider.get_technical_indicators(period=period)
        if data is None:
            self.logger.error(f"No technical indicator data available for {symbol} with period '{period}'. Stopping graph execution.")
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
            1. Trend analysis (RSI, SMA, Volume Trend)
            2. Support/Resistance levels
            3. Technical rating (Bullish/Neutral/Bearish)
            4. Key signals
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

    async def analyze_technical(self, symbol: str, llm, yfinance_provider, period: str = "1d") -> dict:
        """Run the technical analysis graph for a given stock symbol."""
        graph = self.create_graph()
        initial_state = {
            "messages": [],
            "symbol": symbol,
            "llm": llm,
            "yfinance_provider": yfinance_provider,
            "results": {},
            "usage": {},
            "period": period # Set period to "1d" by default
        }
        result = await graph.ainvoke(initial_state)
        return result["results"]
