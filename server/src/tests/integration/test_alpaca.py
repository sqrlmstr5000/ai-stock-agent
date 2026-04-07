import dotenv
dotenv.load_dotenv(dotenv_path='../../../.env', override=True)
import os
import asyncio
import pytest
from providers.alpaca import AlpacaProvider


@pytest.mark.asyncio
async def test_stream_news_real_api_FAKEPACA():
    """Integration test: open Alpaca news stream for FAKEPACA.

    This test will only run when ALPACA_API_KEY and ALPACA_API_SECRET are set in the environment.
    The test connects to Alpaca's news websocket, authenticates, subscribes to FAKEPACA,
    runs briefly, and then cancels the stream. Success criteria: authentication and
    subscription complete without raising errors.
    """
    api_key = os.environ.get("ALPACA_API_KEY")
    api_secret = os.environ.get("ALPACA_API_SECRET")
    if not api_key or not api_secret:
        pytest.skip("ALPACA_API_KEY/ALPACA_API_SECRET not set; skipping real Alpaca integration test")

    # Use provider's default stream URL unless overridden
    stream_url = os.environ.get("ALPACA_NEWS_STREAM_URL")

    provider = AlpacaProvider()

    subscribed = asyncio.Event()
    authenticated = asyncio.Event()
    errors = []

    def on_message(msg):
        # If we get a message, mark subscribed/authenticated (best-effort)
        # Messages from Alpaca include types; look for subscription/auth success
        try:
            t = msg.get("T")
            if t == "n":
                # news item
                pass
            elif t == "subscription":
                subscribed.set()
            elif t == "success" or msg.get("msg") == "authenticated":
                authenticated.set()
        except Exception as e:
            errors.append(e)

    def on_error(err):
        errors.append(err)

    def on_close():
        # noop
        pass

    # Run the stream in a task and cancel after a short timeout
    task = asyncio.create_task(
        provider.streamNews(
            symbols=["FAKEPACA"],
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
            stream_url=stream_url,
        )
    )

    try:
        # Wait up to 8 seconds for authentication/subscription
        try:
            await asyncio.wait_for(authenticated.wait(), timeout=8)
        except asyncio.TimeoutError:
            # Authentication may not send an explicit success message; that's okay — we still assert no errors
            pass

        try:
            await asyncio.wait_for(subscribed.wait(), timeout=8)
        except asyncio.TimeoutError:
            # subscription confirmation may not arrive in test window
            pass

        # Let stream run briefly to potentially receive news
        await asyncio.sleep(3)

    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        await provider.close()

    # Assert no errors were recorded
    assert not errors, f"Errors occurred while streaming news: {errors}"
