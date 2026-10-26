import socket

_orig_getaddrinfo = socket.getaddrinfo

def _ipv4_only(host, port, family=0, type=0, proto=0, flags=0):
    return _orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)

socket.getaddrinfo = _ipv4_only



import os
import time
import warnings
import json
from pathlib import Path
import httpx
import requests
import yfinance as yf
import subprocess
import matplotlib
matplotlib.use("Agg")  # draws to a file, no pop-up window
import matplotlib.pyplot as plt
from dotenv import load_dotenv
from google import genai
from google.genai import errors, types


#for ignoring warnings that came in the result 
warnings.filterwarnings("ignore", module="yfinance")


# ---------- Setup ----------
load_dotenv()  # reads GEMINI_API_KEY and GEMINI_MODELS from the .env file

client = genai.Client(
    api_key=os.environ["GEMINI_API_KEY"],
    http_options=types.HttpOptions(timeout=30000),  # 30 seconds, so it never hangs forever
)

# Models to try in order. Set GEMINI_MODELS in .env, for example:
# GEMINI_MODELS=gemini-3.1-flash-lite,gemini-flash-latest,gemini-3-flash-preview
MODELS = [m.strip() for m in os.getenv("GEMINI_MODELS", "gemini-3.1-flash-lite").split(",")]

COIN_IDS = {}  # remembers CoinPaprika ids so repeat lookups skip the search request
# ---------- Tool 1: crypto prices (CoinPaprika, no API key needed) ----------
def get_crypto_price(coin_name: str, currency: str = "usd") -> str:
    
    try:
        # 1. Find CoinPaprika's id for the coin (for example "eth-ethereum")
        search = requests.get(
            "https://api.coinpaprika.com/v1/search",
            params={"q": coin_name, "c": "currencies", "limit": 1},
            timeout=10,
        )
        search.raise_for_status()
        found = search.json().get("currencies", [])
        if not found:
            return f"Coin '{coin_name}' not found."
        coin_id = found[0]["id"]

        # 2. Get its current price
        quote_currency = currency.upper()
        r = requests.get(
            f"https://api.coinpaprika.com/v1/tickers/{coin_id}",
            params={"quotes": quote_currency},
            timeout=10,
        )
        r.raise_for_status()
        quote = r.json()["quotes"][quote_currency]
        return (
            f"{coin_id}: {quote['price']:.2f} {quote_currency} "
            f"(24h change: {quote['percent_change_24h']:.2f}%)"
        )
    except Exception as e:
            print("DEBUG crypto error:", e)
            return f"Error fetching {coin_name}: {e}"


# ---------- Tool 2: stock prices (Yahoo Finance via yfinance) ----------
def get_stock_price(ticker: str) -> str:
    """Get the latest price of a stock.

    Args:
        ticker: Stock ticker symbol, e.g. "AAPL", "TSLA", or "RELIANCE.NS" for Indian NSE stocks.
    """
    try:
        data = yf.Ticker(ticker).history(period="5d")
        if data.empty:
            return f"No data found for '{ticker}'."
        latest = data["Close"].iloc[-1]
        previous = data["Close"].iloc[-2]
        change = (latest - previous) / previous * 100
        return f"{ticker}: {latest:.2f} (change since previous close: {change:.2f}%)"
    except Exception as e:
        print("DEBUG stock error:", e)
        return f"Error fetching {ticker}: {e}"

def convert_currency(amount:float, from_currency:str, to_currency:str) -> float:
    try:
        r = requests.get(
                "https://api.frankfurter.dev/v1/latest",
                params={"base": from_currency.upper(), "symbols": to_currency.upper()},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        rate = data["rates"][to_currency.upper()]
        return f"{amount:,.2f} {from_currency.upper()} = {amount * rate:,.2f} {to_currency.upper()}"
    except Exception as e:
        print("DEBUG currency error:", e)
        return f"Error converting: {e}"

WATCHLIST_FILE = Path(__file__).parent / "watchlist.json"


def _load_watchlist() -> dict:
    try:
        return json.loads(WATCHLIST_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {"crypto": [], "stocks": []}


def _save_watchlist(data: dict) -> None:
    WATCHLIST_FILE.write_text(json.dumps(data, indent=2))


def add_to_watchlist(name: str, kind: str) -> str:
    """Add a coin or stock to the user's watchlist.

    Args:
        name: Coin name like "bitcoin", or stock ticker like "TSLA" or "RELIANCE.NS".
        kind: Either "crypto" or "stock".
    """
    data = _load_watchlist()
    if kind == "crypto":
        group, item = "crypto", name.lower()
    elif kind == "stock":
        group, item = "stocks", name.upper()
    else:
        return "kind must be 'crypto' or 'stock'."
    if item in data[group]:
        return f"{item} is already in your watchlist."
    data[group].append(item)
    _save_watchlist(data)
    return f"Added {item} to your watchlist."


def remove_from_watchlist(name: str) -> str:
    """Remove a coin or stock from the user's watchlist.

    Args:
        name: Coin name like "bitcoin", or stock ticker like "TSLA".
    """
    data = _load_watchlist()
    for group in ("crypto", "stocks"):
        for item in data[group]:
            if item.lower() == name.lower():
                data[group].remove(item)
                _save_watchlist(data)
                return f"Removed {item} from your watchlist."
    return f"{name} is not in your watchlist."


def show_watchlist() -> str:
    """Show every item in the user's watchlist with its current price."""
    data = _load_watchlist()
    if not data["crypto"] and not data["stocks"]:
        return "Your watchlist is empty."
    lines = [get_crypto_price(c) for c in data["crypto"]]
    lines += [get_stock_price(s) for s in data["stocks"]]
    return "\n".join(lines)


PORTFOLIO_FILE = Path(__file__).parent / "portfolio.json"


def _load_portfolio() -> dict:
    try:
        return json.loads(PORTFOLIO_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {"crypto": {}, "stocks": {}}


def _save_portfolio(data: dict) -> None:
    PORTFOLIO_FILE.write_text(json.dumps(data, indent=2))


# --- helpers that return plain numbers (not text) so we can do math ---
def _crypto_price_usd(coin_name: str) -> float:
    key = coin_name.lower()
    if key not in COIN_IDS:
        search = requests.get(
            "https://api.coinpaprika.com/v1/search",
            params={"q": coin_name, "c": "currencies", "limit": 1},
            timeout=10,
        )
        search.raise_for_status()
        found = search.json().get("currencies", [])
        if not found:
            raise ValueError(f"Coin '{coin_name}' not found")
        COIN_IDS[key] = found[0]["id"]
    r = requests.get(
        f"https://api.coinpaprika.com/v1/tickers/{COIN_IDS[key]}",
        params={"quotes": "USD"},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()["quotes"]["USD"]["price"]


def _stock_price(ticker: str) -> float:
    data = yf.Ticker(ticker).history(period="5d")
    if data.empty:
        raise ValueError(f"No data for '{ticker}'")
    return float(data["Close"].iloc[-1])


def _fx_rate(from_code: str, to_code: str) -> float:
    if from_code == to_code:
        return 1.0
    r = requests.get(
        "https://api.frankfurter.dev/v1/latest",
        params={"base": from_code, "symbols": to_code},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()["rates"][to_code]

def get_price_history(symbol: str, period: str = "1mo") -> str:
    """Get how a stock's or crypto's price changed over a past period.

    Args:
        symbol: Yahoo Finance symbol. Stocks: "AAPL", "TSLA", "RELIANCE.NS".
            Crypto: "BTC-USD", "ETH-USD", "SOL-USD" (coin symbol plus -USD).
        period: One of "5d", "1mo", "3mo", "6mo", "1y", "5y".
    """
    try:
        data = yf.Ticker(symbol).history(period=period)
        if data.empty:
            return f"No data found for '{symbol}'."
        start = data["Close"].iloc[0]
        end = data["Close"].iloc[-1]
        change = (end - start) / start * 100
        return (
            f"{symbol} over {period}: started at {start:.2f}, now {end:.2f} "
            f"({change:+.2f}%). High {data['High'].max():.2f}, low {data['Low'].min():.2f}."
        )
    except Exception as e:
        print("DEBUG history error:", e)
        return f"Error fetching history for {symbol}: {e}"

    
# --- the tools the agent can call ---
def add_holding(name: str, kind: str, quantity: float) -> str:
    """Add coins or shares to the user's portfolio. Adds to the amount already held.

    Args:
        name: Coin name like "bitcoin", or stock ticker like "TSLA" or "RELIANCE.NS".
        kind: Either "crypto" or "stock".
        quantity: How many coins or shares the user holds, e.g. 0.5 or 10.
    """
    if quantity <= 0:
        return "Quantity must be greater than zero."
    data = _load_portfolio()
    if kind == "crypto":
        group, item = "crypto", name.lower()
    elif kind == "stock":
        group, item = "stocks", name.upper()
    else:
        return "kind must be 'crypto' or 'stock'."
    data[group][item] = data[group].get(item, 0) + quantity
    _save_portfolio(data)
    return f"You now hold {data[group][item]} {item}."


def remove_holding(name: str, quantity: float = 0) -> str:
    """Remove coins or shares from the user's portfolio.

    Args:
        name: Coin name like "bitcoin", or stock ticker like "TSLA".
        quantity: How many to remove. Use 0 to remove the whole holding.
    """
    data = _load_portfolio()
    for group in ("crypto", "stocks"):
        for item in list(data[group]):
            if item.lower() == name.lower():
                if quantity <= 0 or quantity >= data[group][item]:
                    del data[group][item]
                    _save_portfolio(data)
                    return f"Removed all {item} from your portfolio."
                data[group][item] -= quantity
                _save_portfolio(data)
                return f"You now hold {data[group][item]} {item}."
    return f"{name} is not in your portfolio."


def show_portfolio(currency: str = "USD") -> str:
    """Show the user's portfolio with the current value of each holding and the total.

    Args:
        currency: 3-letter currency code for the values, e.g. "USD" or "INR".
    """
    data = _load_portfolio()
    if not data["crypto"] and not data["stocks"]:
        return "Your portfolio is empty."
    target = currency.upper()
    lines, total = [], 0.0
    try:
        holdings = [(n, q, "crypto") for n, q in data["crypto"].items()]
        holdings += [(n, q, "stock") for n, q in data["stocks"].items()]
        for name, qty, kind in holdings:
            try:
                if kind == "crypto":
                    price, native = _crypto_price_usd(name), "USD"
                else:
                    price = _stock_price(name)
                    native = "INR" if name.endswith((".NS", ".BO")) else "USD"
                value = qty * price * _fx_rate(native, target)
                total += value
                lines.append(f"{name}: {qty} x {price:,.2f} {native} = {value:,.2f} {target}")
            except Exception as e:
                print("DEBUG portfolio error:", name, e)
                lines.append(f"{name}: could not get price ({e})")
    except Exception as e:
        return f"Error building portfolio: {e}"
    lines.append(f"TOTAL: {total:,.2f} {target}")
    return "\n".join(lines)

CHARTS_DIR = Path(__file__).parent / "charts"


def plot_price_chart(symbols: str, period: str = "1mo") -> str:
    """Draw a price chart image for one or more stocks or cryptos and save it.

    Args:
        symbols: One or more Yahoo Finance symbols separated by commas.
            Stocks: "TSLA", "RELIANCE.NS". Crypto: "BTC-USD", "ETH-USD".
            Example: "BTC-USD,TSLA".
        period: One of "5d", "1mo", "3mo", "6mo", "1y", "5y".
    """
    try:
        names = [s.strip() for s in symbols.split(",") if s.strip()]
        if not names:
            return "No symbols given."
        compare = len(names) > 1
        CHARTS_DIR.mkdir(exist_ok=True)

        fig, ax = plt.subplots(figsize=(9, 5))
        for sym in names:
            data = yf.Ticker(sym).history(period=period)
            if data.empty:
                plt.close(fig)
                return f"No data found for '{sym}'."
            close = data["Close"]
            if compare:  # put different prices on the same scale
                close = close / close.iloc[0] * 100 - 100
            ax.plot(close.index, close.values, label=sym, linewidth=2)

        ax.set_title(f"{', '.join(names)} - last {period}")
        ax.set_ylabel("Change since start (%)" if compare else "Price")
        ax.grid(alpha=0.3)
        if compare:
            ax.legend()
        fig.autofmt_xdate()

        path = CHARTS_DIR / f"{'_'.join(names).replace('.', '-')}_{period}.png"
        fig.savefig(path, dpi=120, bbox_inches="tight")
        plt.close(fig)

        try:  # open the image on Linux
            subprocess.Popen(["xdg-open", str(path)],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass
        return f"Chart saved to {path}"
    except Exception as e:
        print("DEBUG chart error:", e)
        return f"Error drawing chart: {e}"

# ---------- Agent configuration ----------
config = types.GenerateContentConfig(
    tools=[get_crypto_price, get_stock_price, convert_currency,
       add_to_watchlist, remove_from_watchlist, show_watchlist,
       add_holding, remove_holding, show_portfolio,
       get_price_history, plot_price_chart],  # the SDK turns these functions into tools
    system_instruction=(
        "You are a price assistant. Use the tools for any price question, "
        "never guess prices. Keep answers short. This is not financial advice."
        "Use add_to_watchlist, remove_from_watchlist and show_watchlist to manage the user's watchlist. "
        "Use add_holding, remove_holding and show_portfolio to manage what the user owns. "
        "Pass the currency the user asks for to show_portfolio. "
        "Use get_price_history for questions about past performance. "
        "For crypto, use symbols like BTC-USD. Crypto history is in USD. "
        "Use plot_price_chart when the user wants a chart or graph, and tell them the file path it returns. "
    ),
)

model_index = 0
chat = client.chats.create(model=MODELS[model_index], config=config)


def ask(question: str) -> str:
    """Send a question to Gemini. Retries when busy and falls back to the next model."""
    global chat, model_index
    for attempt in range(6):
        try:
            return chat.send_message(question).text
        except (errors.APIError, httpx.TimeoutException, httpx.ConnectError) as e:
            code = getattr(e, "code", None)
            temporary = code in (429, 500, 503, 504) or isinstance(
                e, (httpx.TimeoutException, httpx.ConnectError)
            )
            if not temporary:
                return f"Error: {e}"  # wrong model name, bad key, etc.
            if attempt % 2 == 1 and model_index < len(MODELS) - 1:
                model_index += 1
                print(f"[switching to {MODELS[model_index]}]")
                chat = client.chats.create(model=MODELS[model_index], config=config)
            else:
                wait = 2 ** (attempt // 2 + 1)
                print(f"[slow or busy ({type(e).__name__}), retrying in {wait}s]")
                time.sleep(wait)
    return "All models are busy right now. Please try again in a few minutes."


# ---------- Chat loop ----------
if __name__ == "__main__":
    print(f"Price agent ready (model: {MODELS[model_index]}). Type 'quit' to exit.")
    while True:
        question = input("\nAsk about a stock or crypto (or 'quit'): ").strip()
        if not question:
            continue
        if question.lower() == "quit":
            break
        print(ask(question))