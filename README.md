# Stock & Crypto Price Agent

A beginner-friendly AI agent built in Python. You chat with it in the terminal, and it decides which tool to use, fetches live data from free APIs, and explains the result in plain language.

> **Not financial advice.** This is a learning project. Free data can be delayed or inaccurate, so don't use it for real trading decisions.

## What it can do

- Get current **crypto prices** and **stock prices**
- **Convert currencies** (for example, Ethereum in INR)
- Keep a **watchlist** of coins and stocks saved between sessions
- Track a **portfolio** (how much you hold) and show its current value in any currency
- Show **price history** over a period (1 month, 1 year, and so on)
- Draw **price charts** and save them as images, including comparison charts
- Retry automatically and **fall back to another Gemini model** when a model is busy

## Example questions

```
What's the price of Bitcoin?
How is TSLA doing?
What's Ethereum in INR?
Convert 250 USD to INR.
Compare Bitcoin and Apple stock today.
Add Bitcoin and Tesla to my watchlist.
Show my watchlist.
I hold 0.5 bitcoin and 10 shares of TSLA.
Show my portfolio in INR.
How has Bitcoin done this month?
Show me a chart of Tesla for the last 3 months.
Compare Bitcoin and Ethereum on a chart for 6 months.
```

## How it works

```
You ask a question
      |
      v
Gemini decides which tool to call
      |
      v
Your Python code calls the API and returns the data
      |
      v
Gemini reads the result and writes the answer
```

This is the basic agent loop: **LLM -> tool call -> result -> LLM -> answer**. The Gemini SDK turns each Python function (using its docstring as the description) into a tool automatically.

## Tools

| Tool | What it does | Data source |
|------|--------------|-------------|
| `get_crypto_price` | Current crypto price in USD, with 24h change | CoinPaprika |
| `get_stock_price` | Latest stock price, with change since previous close | Yahoo Finance (`yfinance`) |
| `convert_currency` | Converts an amount between currencies | Frankfurter |
| `add_to_watchlist` / `remove_from_watchlist` / `show_watchlist` | Manage and view a saved watchlist | `watchlist.json` |
| `add_holding` / `remove_holding` / `show_portfolio` | Manage holdings and show their current value | `portfolio.json` |
| `get_price_history` | Start, end, high, low and % change over a period | Yahoo Finance (`yfinance`) |
| `plot_price_chart` | Saves a price chart as a PNG in `charts/` | Yahoo Finance (`yfinance`) + matplotlib |

Only the Gemini API needs a key. CoinPaprika, Frankfurter and Yahoo Finance are used without keys.

## Project structure

```
price_agent/
├── price_agent.py      # the agent and all tools
├── .env                # your secrets (never commit this)
├── .env.example        # template showing which variables are needed
├── .gitignore
├── requirements.txt
├── README.md
├── watchlist.json      # created automatically
├── portfolio.json      # created automatically
└── charts/             # chart images, created automatically
```

## Setup (Linux)

**1. Get a free Gemini API key** from [Google AI Studio](https://aistudio.google.com/apikey).

**2. Create a virtual environment and install packages**

```bash
cd price_agent
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**3. Create your `.env` file** (copy the template, then fill in your key)

```bash
cp .env.example .env
```

```
GEMINI_API_KEY=your-gemini-key
GEMINI_MODELS=gemini-3.1-flash-lite,gemini-flash-latest,gemini-3-flash-preview
```

Rules for `.env`: one `NAME=value` per line, no quotes, no spaces around `=`. The file must be named exactly `.env` and sit in the same folder as `price_agent.py`.

`GEMINI_MODELS` is a comma-separated list. The agent tries the first model and moves to the next one if a model is busy or timing out. Gemini model names change over time, so update this list if you get a "model not found" (404) error.

**4. Run it**

```bash
python price_agent.py
```

Type `quit` to exit.

## Requirements

`requirements.txt`:

```
google-genai
requests
yfinance
python-dotenv
matplotlib
```

## Notes and limitations

- **Crypto prices are in USD.** For other currencies the agent gets the USD price first, then converts it with `convert_currency`.
- **Exchange rates are daily reference rates** (European Central Bank data through Frankfurter), not live market rates.
- **Stock and crypto history use Yahoo Finance symbols.** Stocks: `TSLA`, `RELIANCE.NS` (Indian NSE stocks, priced in INR). Crypto: `BTC-USD`, `ETH-USD`.
- **Stock change vs crypto change:** stocks show the change since the previous market close; crypto shows the 24-hour change.
- **The portfolio tracks quantity and current value**, not the price you paid, so it doesn't calculate profit or loss yet.
- **`yfinance` is unofficial** and can break if Yahoo changes something. Run `pip install --upgrade yfinance` if stock lookups start failing.
- **Free tiers have limits.** Gemini and the price APIs can rate-limit you, and free models can be slow at busy times.

## Troubleshooting

| Problem | Likely fix |
|---------|-----------|
| `KeyError: 'GEMINI_API_KEY'` | The `.env` file is missing, misnamed, or in the wrong folder. Check the name and location. |
| `404` model not found | A model in `GEMINI_MODELS` was retired or renamed. Update the list. |
| Very slow replies or `ReadTimeout` | The model is busy, or IPv6 is stalling on your network. Put the fastest model first, and try forcing IPv4 (see below). |
| `COIN_IDS is not defined` | Make sure the line `COIN_IDS = {}` is near the top of the file, outside any function. |
| A `DEBUG ... error:` line in the terminal | It shows the real error from a tool. The agent's own message is only a summary. |
| Underline on `matplotlib` in VS Code | Select the venv interpreter (Ctrl+Shift+P, then Python: Select Interpreter). |

**Force IPv4** (if replies are randomly slow): put this at the very top of `price_agent.py`, above the other imports.

```python
import socket

_orig_getaddrinfo = socket.getaddrinfo

def _ipv4_only(host, port, family=0, type=0, proto=0, flags=0):
    return _orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)

socket.getaddrinfo = _ipv4_only
```

## Security

- Keep API keys in `.env` only, never in the code.
- `.gitignore` should contain:

```
.env
venv/
watchlist.json
portfolio.json
charts/
__pycache__/
```

- Run `git status` before every commit and confirm `.env` is not listed.
- If a key is ever pushed to GitHub, revoke it and create a new one. Deleting the file in a later commit is not enough, because it stays in the git history.

## Ideas for next steps

- Streamlit web interface, so charts show inside the chat
- Profit and loss tracking (save the buy price with each holding)
- Price alerts ("tell me when Bitcoin drops below X")
- A news tool ("why is Tesla down today?")
- Price caching to make portfolio lookups faster

## Built with

Python, the Google Gemini API (`google-genai`), `requests`, `yfinance`, `matplotlib`, and `python-dotenv`. Data from CoinPaprika, Yahoo Finance and Frankfurter.
## Author

Made by [wildfoxmeowww-create]Yashraj & Jyothika (https://github.com/wildfoxmeowww-create)
