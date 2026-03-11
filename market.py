"""Yahoo Finance market data — prices, ETF holdings, caching."""

import time
import yfinance as yf

# Simple in-memory cache: {ticker: (timestamp, data)}
_cache: dict[str, tuple[float, dict]] = {}
CACHE_TTL = 60  # seconds


def _get_cached(key: str) -> dict | None:
    if key in _cache:
        ts, data = _cache[key]
        if time.time() - ts < CACHE_TTL:
            return data
    return None


def _set_cache(key: str, data: dict):
    _cache[key] = (time.time(), data)


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
