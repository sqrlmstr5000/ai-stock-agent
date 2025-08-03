import os
from typing import Dict, List, Optional, Tuple, Annotated
from typing_extensions import TypedDict
import json
import logging
from datetime import datetime, timedelta
from models.marketdata import HistoricalTrackedValues
from models.models import ApiRequestUsage

from langchain_core.prompts import PromptTemplate
from langchain.agents import AgentExecutor, Tool
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.runnables import Runnable
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.output_parsers import StrOutputParser
from langchain_google_genai import ChatGoogleGenerativeAI

from providers.yfinance import YFinanceProvider
from providers.alphavantage import AlphaVantageProvider
from providers.fred import FredProvider
from services.database import DatabaseManager
from utils.prompts import system_message

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

class StockAdvisor:
    def __init__(self, db_manager: DatabaseManager):
        self.llm = self.setup_llm()
        self.graph = self.create_analysis_graph()
        self.db_manager = db_manager
        self.fred_provider = FredProvider()

    def update_token_usage(self, step: str, usage: Dict[any, any]):
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

        # Persist token usage stats
        self.db_manager.save_token_usage(step, input_tokens, output_tokens, total_tokens)

    def update_api_usage(self, provider: str, count: int = 1):
        """Helper function to log API usage for a provider (one record per call, use created_at for daily tracking)"""
        ApiRequestUsage.create(provider=provider, count=count, created_at=datetime.now())




   


