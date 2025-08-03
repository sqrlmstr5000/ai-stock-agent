
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

        data = provider.get_technical_indicators()

        prompt = PromptTemplate.from_template(
            """Analyze these technical indicators for {symbol}:
            {data}

            Provide:
            1. Trend analysis (RSI, SMA, Volume Trend)
            2. Support/Resistance levels
            3. Technical rating (Bullish/Neutral/Bearish)
            4. Key signals
            """
        )

        chain = prompt | llm
        analysis = await chain.ainvoke({"symbol": symbol, "data": json.dumps(data.model_dump(), indent=2)})

        state["results"] = {
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
    
    async def export_analysis(self, state: dict) -> dict:
        """Node for exporting the technical analysis to a structured format."""
        symbol = state["symbol"]
        self.logger.info(f"Exporting technical analysis for {symbol}...")
        llm = state["llm"]
        results = state["results"]

        prompt = PromptTemplate.from_template(
            """Based on the following technical analysis for {symbol}, extract the required information and populate the structured output object. Set the report_date to today's date.
            
            Technical Analysis: {analysis}
            """
        )

        chain = prompt | llm.with_structured_output(TechnicalHistoricalTrackedValues)

        structured_data = await chain.ainvoke({
            "symbol": symbol,
            "analysis": results["analysis"]
        })

        state["results"]["structured_data"] = structured_data.model_dump()
        state["usage"]["export_analysis"] = {
            "token_usage": None,
            "api_usage": None
        }
        return state

    def create_graph(self):
        """Create the technical analysis graph with export_analysis node."""
        graph = StateGraph(State)
        graph.add_node("technical_analysis", self.technical_analysis)
        graph.add_node("export_analysis", self.export_analysis)
        graph.add_edge(START, "technical_analysis")
        graph.add_edge("technical_analysis", "export_analysis")
        graph.add_edge("export_analysis", END)
        return graph.compile()

    async def analyze_technical(self, symbol: str, llm, yfinance_provider) -> dict:
        """Run the technical analysis graph for a given stock symbol."""
        graph = self.create_graph()
        initial_state = {
            "messages": [],
            "symbol": symbol,
            "llm": llm,
            "yfinance_provider": yfinance_provider,
            "results": {},
            "usage": {}
        }
        result = await graph.ainvoke(initial_state)
        return result["results"]
