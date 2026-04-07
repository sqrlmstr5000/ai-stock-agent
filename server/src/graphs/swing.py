import json
from typing import Dict, Annotated
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.prompts import PromptTemplate
from utils.logging import setup_logger
from utils.langchain_handler import VerboseFileCallbackHandler
from graphs.technical import TechnicalAnalysisGraph
from models.marketdata import SwingTradePlan
from models.models import Research
from providers.yfinance import YFinanceProvider
from providers.alphavantage import AlphaVantageProvider

logger = setup_logger(__name__)

# State object for SwingTradeGraph
class State(TypedDict):
    messages: Annotated[list, add_messages]
    symbol: str
    research: Research
    results: Dict
    usage: Dict[str, dict]
    period: str

class SwingTradeGraph:
    def __init__(self, llm, yfinance_provider: YFinanceProvider, alphavantage_provider: AlphaVantageProvider):
        self.llm = llm
        self.yfinance_provider = yfinance_provider
        self.alphavantage_provider = alphavantage_provider
        self.technical_graph = TechnicalAnalysisGraph(llm=self.llm, yfinance_provider=self.yfinance_provider, alphavantage_provider=self.alphavantage_provider)
        self.handler = VerboseFileCallbackHandler(graph_name=self.__class__.__name__)

    async def pattern_analysis(self, state: State) -> State:
        symbol = state["symbol"]
        provider = self.yfinance_provider
        llm = self.llm
        logger.info(f"Running pattern_analysis node for {symbol} (fetching 1d technical indicators)")
        data_1d = provider.get_technical_indicators(symbol, period="5d")
        if data_1d is None:
            logger.error(f"No technical indicator data available for {symbol} with period '1d'. Stopping pattern analysis.")
            state["results"]["pattern_analysis"] = {
                "data": None,
                "analysis": "No technical indicator data available. Analysis aborted."
            }
            return state

        prompt = PromptTemplate.from_template(
            """Analyze the data for these chart patterns for {symbol} over the last {period}:
            {data}

            Guidelines:
                - Only include potential or identified patterns found. 
                - Provide a brief explanation of each pattern identified and what data was relevant to this determination. 

            **Candlestick Patterns**
            1. **Bullish Reversal Patterns:**
                - Appear after a downtrend and suggest buying pressure is taking over.
                - **Hammer:** Single candlestick with a small body (red or green) and a long lower wick (at least twice the body). Little/no upper wick. Indicates sellers pushed price down, but buyers brought it back up. Strong bullish signal at support or after a downtrend.
                - **Bullish Engulfing:** Two-candlestick pattern. First is small bearish (red), second is large bullish (green) that engulfs the first. Shows buyers overpowering sellers. Reliable at the bottom of a downtrend.
                - **Morning Star:** Three-candlestick reversal pattern:
                    - First: Long bearish (red), continues downtrend.
                    - Second: Small-bodied (Doji/Spinning Top), gaps down, shows indecision.
                    - Third: Long bullish (green), gaps up, closes well into first candle. Bulls take control.
            2. **Bearish Reversal Patterns:**
                - Appear after an uptrend and suggest selling pressure is taking over.
                - **Shooting Star:** Bearish equivalent of inverted hammer. Small body (red/green), long upper wick. Buyers push price up, sellers push it back down. Strong reversal signal at resistance or after uptrend.
                - **Bearish Engulfing:** Inverse of bullish engulfing. First is small bullish (green), second is large bearish (red) that engulfs the first. Sellers take over.
                - **Evening Star:** Three-candlestick reversal pattern:
                    - First: Long bullish (green), continues uptrend.
                    - Second: Small-bodied, gaps up, indecision.
                    - Third: Long bearish (red), gaps down, closes well into first candle. Uptrend likely over.
            3. **Indecision and Continuation Patterns:**
                - **Doji:** Open and close nearly identical, very small body. Wick length varies. Represents indecision. Not strong alone, but at trend tops/bottoms can signal reversal. Most effective as part of a larger pattern (e.g., Morning/Evening Star).
                - **Spinning Top:** Like a Doji but with a slightly larger body. Also signals indecision. Series after a strong trend can mean trend is losing momentum.

            **Chart Patterns**
            1. **Head and Shoulders (Reversal Pattern):**
                - Reliable bearish reversal. Uptrend may be ending. Inverse pattern is bullish.
                - **How to Identify:**
                    - **Left Shoulder:** Price rises to a peak, then declines.
                    - **Head:** Price rises to a higher peak, then declines to first trough.
                    - **Right Shoulder:** Price rises again, forms lower peak, then declines.
                    - **Neckline:** Connects two lowest points between peaks. Break below (with volume) confirms pattern and signals down move.
            2. **Double Top and Double Bottom (Reversal Patterns):**
                - Signal strong reversal after price fails to break support/resistance twice.
                - **Double Top (Bearish):**
                    - **Uptrend:** Pattern forms after uptrend.
                    - **First Top:** Price rises to new high, faces resistance, pulls back.
                    - **Second Top:** Price rallies to same resistance, fails, declines.
                    - **Neckline:** Support at low point between peaks. Break below (high volume) signals downtrend.
                - **Double Bottom (Bullish):**
                    - **Downtrend:** Pattern forms after downtrend.
                    - **First Bottom:** Price declines to new low, finds support, rallies.
                    - **Second Bottom:** Price falls to same support, fails to break lower, rises.
                    - **Neckline:** Resistance at high point between troughs. Break above (high volume) signals uptrend. Pattern resembles 'W'.
            3. **Cup and Handle (Continuation Pattern):**
                - Bullish continuation. Brief pause in uptrend before price continues higher. Reliable pattern.
                - **How to Identify:**
                    - **Cup:** "U" shaped curve as price declines, then recovers. Bottom should be broad/rounded, not sharp/V-shaped.
                    - **Handle:** After cup, price consolidates in short, downward-sloping channel/flag in top half of cup.
                    - **Breakout:** Confirmed when price breaks above handle resistance on volume. Target = cup depth + breakout point.
            4. **Flags and Pennants (Continuation Patterns):**
                - Short-term continuation patterns, pause in strong trend. Characterized by sharp price move, then consolidation.
                - **Bull Flag/Pennant:**
                    - **Flagpole:** Sharp, vertical rally on high volume.
                    - **Flag/Pennant:** Price consolidates in tight range. Flag = rectangular channel sloping against trend; pennant = small symmetrical triangle.
                    - **Breakout:** Confirmed when price breaks out in direction of trend, on volume.
                - **Bear Flag/Pennant:**
                    - **Flagpole:** Sharp, rapid decline on high volume.
                    - **Flag/Pennant:** Price consolidates in tight range. Flag = channel sloping against trend; pennant = small triangle.
                    - **Breakout:** Confirmed when price breaks out downward, on volume.
            """
        )

        chain = prompt | llm
        analysis = await chain.ainvoke({
            "symbol": symbol,
            "data": json.dumps(data_1d.model_dump(), indent=2),
            "period": "5d"
        })

        state["results"]["pattern_analysis"] = {
            "data": data_1d.model_dump() if hasattr(data_1d, 'model_dump') else data_1d,
            "analysis": analysis.content
        }
        return state

    async def generate_trade_recommendation(self, state: State) -> State:
        """Use an LLM prompt to generate a trade recommendation based on previous node results."""
        pattern = state["results"].get("pattern_analysis", {})
        research = state["research"]["recommendation"]
        llm = self.llm
        if not pattern:
            state["results"]["trade_recommendation"] = {
                "recommendation": "Insufficient data from previous nodes to generate a trade recommendation."
            }
            return state

        prompt = PromptTemplate.from_template(
            """
            You are a swing trading expert. Given the following technical analysis and pattern analysis, generate a clear, actionable trade recommendation for the stock {symbol}.

            ---
            Pattern Analysis (1D):
            {pattern_analysis}

            --- 
            Financial Analyst Recommendation:
            {research}

            Guide:
                **How to Use These Patterns in Swing Trading**
                    - Context is Key: A candlestick pattern is rarely a definitive signal on its own. It's most powerful when it appears in the right context (e.g., a Bullish Engulfing at a major support level on the daily chart).
                    - Confirmation is Crucial: Always wait for confirmation. For example, after spotting a Hammer, wait for the next candle to be bullish before entering a long position. If a Hammer is followed by a bearish candle, it's not a valid setup.
                    - Use Multiple Timeframes: Look for these patterns on the daily chart for trading signals and use the weekly chart to confirm the broader trend. This reduces the risk of false signals.
                    - Combine with Other Indicators: Use these patterns with other technical tools. A bullish reversal pattern supported by an oversold RSI and a MACD crossover is a much higher-probability trade.

                **The "Top-Down" Approach**
                    - This is a widely used and effective method. Start with a longer-term chart to determine the overall trend, then move to a shorter-term chart for trading signals and execution.
                    1. **Longer Timeframes (Weekly and Daily Charts):**
                        - Purpose: "Big picture" view. Identify the primary trend and significant support/resistance levels.
                    2. **Shorter Timeframes (4-Hour or Hourly Charts):**
                        - Purpose: Used for precise timing of entries and exits.

            ---
            Instructions:
                - I am only concerned with bullish patterns and long positions. Timeline is weeks to months.
                - Consider both the long-term technicals and the short-term chart/candlestick patterns.
                - If the analyses are aligned, state this and provide a confident recommendation.
                - If the analyses are mixed, explain the conflict and suggest a cautious or neutral approach.
                - Include a brief rationale for your recommendation.
                - Include the following in your recommendation:
                    - Action: (e.g., "Buy", "Sell", "Hold", or "Wait for confirmation").
                    - Direction: (e.g., "Short" or "Long")
                    - Entry price: the price at which to enter the trade.
                    - Stop loss price: the price at which to exit the trade if it moves against you.
                    - Take profit price: the price at which to exit the trade if it moves in your favor.
                    - Risk per trade: The maximum amount of capital to risk on this trade.
                    - Position size: The number of shares to buy/sell. Show the calculation based on a $10,000 account size and 1% risk per trade.
                    - Risk reward ratio: The calculated risk/reward ratio for the trade.
                    - Potential profit: The potential profit in dollars if the trade hits the take profit target.
                    - Potential loss: The potential loss in dollars if the trade hits the stop loss.
                    - Entry reason: A brief explanation for the entry signal (e.g., 'Breakout of Bull Flag on high volume').
                    - Exit reason: A brief explanation of the exit strategy (e.g., 'Target based on pattern measurement, Stop Loss below key support').
                    - Execution plan: the step-by-step plan for executing the trade.
            """
        )

        chain = prompt | llm
        research_recommendation = getattr(research, "recommendation", None)
        if research_recommendation is None:
            research_recommendation = "No financial analyst recommendation available."
        analysis = await chain.ainvoke({
            "symbol": state["symbol"],
            "pattern_analysis": pattern.get("analysis", ""),
            "research": research_recommendation
        })

        state["results"]["trade_recommendation"] = {
            "data": None,
            "analysis": analysis.content
        }
        return state
    
    async def export_recommendation(self, state: dict) -> dict:
        """Node for exporting the trade recommendation to a structured SwingTradePlan object."""
        symbol = state["symbol"]
        llm = self.llm
        results = state["results"]

        prompt = PromptTemplate.from_template(
            """
            Based on the following trade recommendation for {symbol}, extract and populate the SwingTradePlan object.

            Trade Recommendation:
            {trade_recommendation}

            Extract all required fields for the SwingTradePlan, including direction, entry/stop/take profit prices, pattern names, risk management, rationale, and execution plan.
            """
        )

        chain = prompt | llm.with_structured_output(SwingTradePlan)
        swing_plan = await chain.ainvoke({
            "symbol": symbol,
            "trade_recommendation": results["trade_recommendation"]
        })

        state["results"]["swing_trade_plan"] = swing_plan.model_dump()
        return state
    
    def create_graph(self):
        graph = StateGraph(State)
        graph.add_node("pattern_analysis", self.pattern_analysis)
        graph.add_node("generate_trade_recommendation", self.generate_trade_recommendation)
        graph.add_node("export_recommendation", self.export_recommendation)
        graph.add_edge(START, "pattern_analysis")
        graph.add_edge("pattern_analysis", "generate_trade_recommendation")
        graph.add_edge("generate_trade_recommendation", "export_recommendation")
        graph.add_edge("export_recommendation", END)
        return graph.compile()

    async def analyze_swing_trade(self, symbol: str, research: Research) -> dict:
        graph = self.create_graph()
        initial_state = {
            "messages": [],
            "symbol": symbol,
            "research": research,
            "results": {},
            "usage": {},
        }
        final_state = await graph.ainvoke(initial_state, config={"callbacks": [self.handler]})
        return {
            "results": final_state["results"],
            "usage": final_state.get("usage", {})
        }
