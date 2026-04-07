import os
import json
import asyncio
import aiohttp
from typing import List, Callable, Optional, Any, Dict
from utils.logging import setup_logger
from base.market_data_provider import MarketDataProvider

logger = setup_logger(__name__)

class AlpacaProvider:
    """
    Provider for Alpaca Markets API.
    
    This class provides methods to interact with Alpaca's APIs, including
    market data, trading, and news streams.
    """
    
    BASE_URL = "https://api.alpaca.markets"
    DATA_URL = "https://data.alpaca.markets"
    #NEWS_STREAM_URL = "wss://stream.data.alpaca.markets/v1beta1/news"
    NEWS_STREAM_URL = "wss://stream.data.alpaca.markets/v2/test" 
    
    def __init__(self):
        """
        Initialize the AlpacaProvider with API credentials from environment variables.
        
        Raises:
            ValueError: If API key or secret are not found in environment variables.
        """
        self.api_key = os.environ.get("ALPACA_API_KEY")
        self.api_secret = os.environ.get("ALPACA_API_SECRET")
        
        if not self.api_key or not self.api_secret:
            raise ValueError("Alpaca API key and secret must be set in environment variables.")
        
        self._session = None
    
    async def streamNews(
        self, 
        symbols: List[str], 
        on_message: Callable[[Dict[str, Any]], None], 
        on_error: Optional[Callable[[Any], None]] = None, 
        on_close: Optional[Callable[[], None]] = None,
        stream_url: Optional[str] = None
    ) -> None:
        """
        Connect to Alpaca's real-time news websocket and stream news for specified symbols.
        
        This method establishes a WebSocket connection to Alpaca's news stream,
        authenticates, subscribes to the specified symbols, and calls the provided
        callback functions when events occur.
        
        Args:
            symbols: List of ticker symbols to subscribe to news for
            on_message: Callback function that will be called with each news message
            on_error: Optional callback function called when an error occurs
            on_close: Optional callback function called when the connection closes
            stream_url: Optional custom WebSocket URL (defaults to Alpaca's news stream URL)
        
        Example:
            ```python
            async def handle_news(news_item):
                print(f"Breaking news: {news_item['headline']}")
            
            alpaca = AlpacaProvider()
            await alpaca.streamNews(
                symbols=["AAPL", "MSFT", "GOOG"],
                on_message=handle_news
            )
            ```
        """
        # Use default URL if not provided
        ws_url = stream_url or self.NEWS_STREAM_URL
        
        # Define error handling if not provided
        if on_error is None:
            on_error = lambda err: logger.error(f"WebSocket error: {err}")
        
        try:
            logger.info(f"Connecting to Alpaca news stream at {ws_url}")
            
            # Create a new session if we don't have one
            if not hasattr(self, '_session') or not self._session or self._session.closed:
                self._session = aiohttp.ClientSession()
                
            # Connect to WebSocket
            async with self._session.ws_connect(ws_url) as ws:
                # Authenticate
                auth_message = {
                    "action": "auth",
                    "key": self.api_key,
                    "secret": self.api_secret
                }
                await ws.send_json(auth_message)
                
                # Receive authentication response
                auth_resp = await ws.receive()
                if auth_resp.type == aiohttp.WSMsgType.TEXT:
                    auth_data = json.loads(auth_resp.data)

                    # auth_data may be a dict or a list of dicts; normalize to a list
                    auth_items = auth_data if isinstance(auth_data, list) else [auth_data]

                    # Consider auth successful if any item indicates success/authenticated
                    auth_ok = any(
                        (isinstance(item, dict) and (item.get("T") == "success" or item.get("msg") == "authenticated"))
                        for item in auth_items
                    )

                    if not auth_ok:
                        error_msg = f"Authentication failed: {auth_resp.data}"
                        logger.error(error_msg)
                        if on_error:
                            on_error(error_msg)
                        return

                    logger.info("Authentication successful")

                    # Subscribe to news for the specified symbols
                    subscribe_message = {
                        "action": "subscribe",
                        "news": symbols
                    }
                    await ws.send_json(subscribe_message)

                    # Receive subscription confirmation. The stream may echo auth success or return multiple messages,
                    # so loop until we see a 'subscription' message or timeout.
                    sub_ok = False
                    try:
                        while True:
                            sub_resp = await asyncio.wait_for(ws.receive(), timeout=5)
                            if sub_resp.type == aiohttp.WSMsgType.TEXT:
                                sub_data = json.loads(sub_resp.data)
                                sub_items = sub_data if isinstance(sub_data, list) else [sub_data]

                                # If any item explicitly indicates subscription, we're good
                                if any(isinstance(item, dict) and item.get("T") == "subscription" for item in sub_items):
                                    sub_ok = True
                                    break

                                # If we get an explicit error message, fail fast
                                if any(isinstance(item, dict) and item.get("T") == "error" for item in sub_items):
                                    error_msg = f"Subscription error: {sub_resp.data}"
                                    logger.error(error_msg)
                                    if on_error:
                                        on_error(error_msg)
                                    return

                                # Otherwise (e.g., echoes of auth success), continue waiting until timeout
                                continue
                            elif sub_resp.type == aiohttp.WSMsgType.CLOSED:
                                break
                    except asyncio.TimeoutError:
                        # timed out waiting for explicit subscription confirmation
                        pass

                    if not sub_ok:
                        error_msg = f"Subscription failed: {sub_resp.data if 'sub_resp' in locals() else 'no response'}"
                        logger.error(error_msg)
                        if on_error:
                            on_error(error_msg)
                        return

                    logger.info(f"Successfully subscribed to news for symbols: {symbols}")

                    # Process incoming messages
                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            try:
                                news_data = json.loads(msg.data)
                            except Exception:
                                # Non-JSON message; skip
                                continue

                            # If it's a list of items, iterate safely
                            if isinstance(news_data, list):
                                for item in news_data:
                                    if isinstance(item, dict) and item.get("T") == "n":  # News item
                                        try:
                                            on_message(item)
                                        except Exception as e:
                                            logger.exception(f"Error in on_message callback: {e}")
                            # If it's a single dict message, check for news type
                            elif isinstance(news_data, dict) and news_data.get("T") == "n":
                                try:
                                    on_message(news_data)
                                except Exception as e:
                                    logger.exception(f"Error in on_message callback: {e}")

                        elif msg.type == aiohttp.WSMsgType.ERROR:
                            logger.error(f"WebSocket error: {ws.exception()}")
                            if on_error:
                                on_error(ws.exception())
                            break
                        elif msg.type == aiohttp.WSMsgType.CLOSED:
                            logger.info("WebSocket connection closed")
                            if on_close:
                                on_close()
                            break
                
        except aiohttp.ClientError as e:
            logger.error(f"aiohttp client error: {e}")
            if on_error:
                on_error(e)
        except Exception as e:
            logger.error(f"Error in streamNews: {e}")
            if on_error:
                on_error(e)
            
    async def close(self):
        """Close any open resources when done."""
        if hasattr(self, '_session') and self._session:
            await self._session.close()
            self._session = None
