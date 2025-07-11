# ai-stock-agent

This project is an AI-powered stock analysis agent that uses Google's Gemini model to provide a comprehensive analysis of a given stock. Please note that this agent only supports the Gemini family of models.

## Getting Started

## Getting Started

### Prerequisites

- Python 3.x
- An environment variable named `GEMINI_API_KEY` must be set with a valid Google Gemini API Key.

### Setting the API Key

You can set the `GEMINI_API_KEY` environment variable in your shell like this:

```bash
export GEMINI_API_KEY="YOUR_API_KEY"
```

Replace `"YOUR_API_KEY"` with your actual Google Gemini API key. To make this permanent, you can add this line to your shell's startup file (e.g., `~/.bashrc`, `~/.zshrc`).

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

## Tools Used

This project utilizes the following key libraries and frameworks:

- **Langchain:** A framework for developing applications powered by language models.
- **Langgraph:** A library for building stateful, multi-actor applications with LLMs, built on top of LangChain.
- **yfinance:** A popular open-source library that provides an easy way to download historical market data from Yahoo Finance.

## Graph Agents

The stock analysis is performed by a series of agents, each with a specific role:

- **Technical Analysis Agent:** This agent analyzes technical indicators such as SMA, RSI, and volume trends to provide a technical rating and identify key signals.
- **Market Analysis Agent:** This agent analyzes market data, including sector performance, risk assessment, and overall market sentiment, to provide a broader market context.
- **News Analysis Agent:** This agent analyzes news for sentiment, key developments, and potential impact.
- **Recommendation Agent:** This agent takes the analysis from all other agents and generates a final recommendation, including a buy/sell rating, confidence score, and price targets.

## Credits

This project was inspired by and adapted from the following notebook:

- [https://github.com/2manoj1/g-colab/blob/main/deepseek_AI_Agent.ipynb](https://github.com/2manoj1/g-colab/blob/main/deepseek_AI_Agent.ipynb)