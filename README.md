# ai-stock-agent

## Getting Started

### Prerequisites

- Python 3.x
- An environment variable named `GEMINI_API_KEY` must be set with a valid Google Gemini API Key.

### Setup

1.  **Create and activate a virtual environment:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

2.  **Install the required packages:**
    ```bash
    pip install -r requirements.txt
    ```

### Usage

Here are some examples of how to run the agent:

**Get a full stock analysis for a single stock:**
```bash
python graph.py AAPL
```

**Get a full stock analysis for a single stock with verbose logging:**
```bash
python graph.py AAPL --verbose
```

**Compare multiple stocks:**
```bash
python graph.py AAPL GOOG
```

**Get the yFinance dividend history for a stock:**
```bash
python graph.py AAPL --div
```

**Get the yFinance news for a stock:**
```bash
python graph.py AAPL --news
```

**Get the yFinance market data for a stock:**
```bash
python graph.py AAPL --market
```

**Get the yFinance technical indicator data for a stock:**
```bash
python graph.py AAPL --tech
```