"""Yahoo Finance market data — prices, ETF holdings, caching."""

import time
import yfinance as yf

# Simple in-memory cache: {ticker: (timestamp, data)}
_cache: dict[str, tuple[float, dict]] = {}
CACHE_TTL = 300  # 5 minutes


def _get_cached(key: str) -> dict | None:
    if key in _cache:
        ts, data = _cache[key]
        if time.time() - ts < CACHE_TTL:
            return data
    return None


def _set_cache(key: str, data: dict):
    _cache[key] = (time.time(), data)


def clear_cache():
    """Clear all cached data. Used for manual refresh."""
    _cache.clear()


def get_price(ticker: str) -> dict:
    """Fetch current price info for a single ticker.

    Returns dict with keys: price, currency, name, change_pct
    """
    cached = _get_cached(f"price:{ticker}")
    if cached:
        return cached

    try:
        t = yf.Ticker(ticker)
        info = t.info
        result = {
            "price": info.get("regularMarketPrice") or info.get("previousClose", 0),
            "currency": info.get("currency", ""),
            "name": info.get("shortName", ticker),
            "change_pct": info.get("regularMarketChangePercent", 0) or 0,
        }
    except Exception:
        result = {"price": 0, "currency": "", "name": ticker, "change_pct": 0}

    _set_cache(f"price:{ticker}", result)
    return result


def get_prices(tickers: list[str]) -> dict[str, dict]:
    """Fetch prices for multiple tickers."""
    results = {}
    to_fetch = []

    for ticker in tickers:
        cached = _get_cached(f"price:{ticker}")
        if cached:
            results[ticker] = cached
        else:
            to_fetch.append(ticker)

    if to_fetch:
        # Try batch fetch
        try:
            batch = yf.Tickers(" ".join(to_fetch))
            for ticker in to_fetch:
                try:
                    info = batch.tickers[ticker].info
                    result = {
                        "price": info.get("regularMarketPrice") or info.get("previousClose", 0),
                        "currency": info.get("currency", ""),
                        "name": info.get("shortName", ticker),
                        "change_pct": info.get("regularMarketChangePercent", 0) or 0,
                    }
                except Exception:
                    result = {"price": 0, "currency": "", "name": ticker, "change_pct": 0}
                results[ticker] = result
                _set_cache(f"price:{ticker}", result)
        except Exception:
            # Fallback to individual fetches
            for ticker in to_fetch:
                results[ticker] = get_price(ticker)

    return results


def get_history(ticker: str, period: str = "3mo") -> dict:
    """Fetch historical price data for a ticker.

    Returns dict with keys: dates (list[str]), closes (list[float])
    """
    cached = _get_cached(f"history:{ticker}:{period}")
    if cached:
        return cached

    try:
        t = yf.Ticker(ticker)
        df = t.history(period=period)
        if df is None or df.empty:
            return {"dates": [], "closes": []}

        result = {
            "dates": [d.strftime("%Y-%m-%d") for d in df.index],
            "closes": [float(c) for c in df["Close"]],
        }
    except Exception:
        result = {"dates": [], "closes": []}

    _set_cache(f"history:{ticker}:{period}", result)
    return result


def get_exchange_rate(from_currency: str, to_currency: str) -> float:
    """Get exchange rate from one currency to another. Returns multiplier."""
    if from_currency == to_currency:
        return 1.0

    cached = _get_cached(f"fx:{from_currency}{to_currency}")
    if cached:
        return cached.get("rate", 1.0)

    try:
        pair = f"{from_currency}{to_currency}=X"
        t = yf.Ticker(pair)
        rate = t.info.get("regularMarketPrice") or t.info.get("previousClose", 1.0)
        result = {"rate": float(rate)}
    except Exception:
        result = {"rate": 1.0}

    _set_cache(f"fx:{from_currency}{to_currency}", result)
    return result["rate"]


def get_exchange_rates(to_currency: str, from_currencies: list[str]) -> dict[str, float]:
    """Get exchange rates from multiple currencies to a target currency.

    Returns {from_currency: rate} where rate converts from_currency to to_currency.
    """
    rates = {}
    for fc in set(from_currencies):
        rates[fc] = get_exchange_rate(fc, to_currency)
    return rates


def get_ticker_info(ticker: str) -> dict:
    """Fetch detailed info for a ticker.

    Returns dict with keys: quote_type, market_cap, pe_ratio, forward_pe,
    dividend_yield, high_52w, low_52w, beta, sector, industry, name, price, currency
    """
    cached = _get_cached(f"info:{ticker}")
    if cached:
        return cached

    try:
        t = yf.Ticker(ticker)
        info = t.info
        result = {
            "quote_type": info.get("quoteType", "EQUITY"),
            "name": info.get("shortName", ticker),
            "price": info.get("regularMarketPrice") or info.get("previousClose", 0),
            "currency": info.get("currency", ""),
            "market_cap": info.get("marketCap"),
            "pe_ratio": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "dividend_yield": info.get("dividendYield"),
            "high_52w": info.get("fiftyTwoWeekHigh"),
            "low_52w": info.get("fiftyTwoWeekLow"),
            "beta": info.get("beta"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
        }
    except Exception:
        result = {"quote_type": "EQUITY", "name": ticker, "price": 0, "currency": ""}

    _set_cache(f"info:{ticker}", result)
    return result


def get_etf_holdings(ticker: str) -> list[dict]:
    """Get top holdings for an ETF.

    Returns list of dicts with keys: symbol, name, weight
    """
    cached = _get_cached(f"holdings:{ticker}")
    if cached:
        return cached.get("holdings", [])

    try:
        t = yf.Ticker(ticker)
        fd = t.funds_data
        df = fd.top_holdings
        if df is None or df.empty:
            return []

        holdings = []
        for symbol, row in df.iterrows():
            holdings.append({
                "symbol": str(symbol),
                "name": row.get("Name", str(symbol)),
                "weight": float(row.get("Holding Percent", 0)) * 100,
            })

        _set_cache(f"holdings:{ticker}", {"holdings": holdings})
        return holdings
    except Exception:
        return []
