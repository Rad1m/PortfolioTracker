"""QThread workers for async market data fetching."""

from PySide6.QtCore import QThread, Signal

from market import (
    clear_cache,
    get_etf_holdings,
    get_exchange_rates,
    get_history,
    get_prices,
    get_ticker_info,
)
from storage import Portfolio


class MarketWorker(QThread):
    """Generic worker that runs a callable in a background thread."""

    finished = Signal(object)
    error = Signal(str)

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs

    def run(self):
        try:
            result = self._fn(*self._args, **self._kwargs)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


def _fetch_holdings_data(portfolio: Portfolio, portfolio_name: str | None, display_currency: str, sort_mode: str):
    """Fetch all market data needed for a holdings table. Runs in worker thread."""
    holdings = portfolio.get_holdings(portfolio_name)
    if not holdings:
        return {"empty": True}

    tickers = sorted(holdings.keys())
    prices = get_prices(tickers)
    avg_costs = {t: portfolio.get_avg_cost(t, portfolio_name) for t in tickers}

    native_currencies = [prices.get(t, {}).get("currency", "USD") for t in tickers]
    fx_rates = get_exchange_rates(display_currency, native_currencies)

    histories = {t: get_history(t) for t in tickers}
    ticker_fx = {
        t: fx_rates.get(prices.get(t, {}).get("currency", "USD"), 1.0)
        for t in tickers
    }
    chart_data = _compute_portfolio_history(holdings, histories, ticker_fx)

    closes = chart_data.get("closes", [])
    three_month_pct = ((closes[-1] / closes[0]) - 1) * 100 if len(closes) >= 2 else 0.0

    # Compute rows
    rows = []
    day_change_value = 0.0
    total_value_for_day = 0.0

    for ticker in tickers:
        shares = holdings[ticker]
        avg = avg_costs.get(ticker, 0)
        info = prices.get(ticker, {})
        price = info.get("price", 0)
        name = info.get("name", ticker)
        change_pct = info.get("change_pct", 0) or 0
        native_currency = info.get("currency", "USD")
        fx = fx_rates.get(native_currency, 1.0)

        value = shares * price * fx
        cost = shares * avg * fx
        pnl = value - cost
        pnl_pct = (pnl / cost * 100) if cost > 0 else 0.0

        total_value_for_day += value
        day_change_value += value * (change_pct / 100)

        rows.append({
            "ticker": ticker, "name": name, "shares": shares,
            "avg": avg * fx, "price": price * fx, "value": value,
            "pnl": pnl, "pnl_pct": pnl_pct,
        })

    day_pct = (day_change_value / (total_value_for_day - day_change_value) * 100) if total_value_for_day > day_change_value else 0.0

    return {
        "empty": False,
        "rows": rows,
        "chart_data": chart_data,
        "day_pct": day_pct,
        "three_month_pct": three_month_pct,
        "sort_mode": sort_mode,
        "display_currency": display_currency,
    }


def _compute_portfolio_history(holdings, histories, ticker_fx=None):
    """Compute aggregated portfolio value over time."""
    all_dates = set()
    ticker_data = {}

    for ticker, hist in histories.items():
        dates = hist.get("dates", [])
        closes = hist.get("closes", [])
        if dates and closes:
            ticker_data[ticker] = dict(zip(dates, closes))
            all_dates.update(dates)

    if not all_dates:
        return {"dates": [], "closes": []}

    date_values = {}
    for d in sorted(all_dates):
        total = 0.0
        for ticker, shares in holdings.items():
            td = ticker_data.get(ticker, {})
            if d in td:
                fx = ticker_fx.get(ticker, 1.0) if ticker_fx else 1.0
                total += shares * td[d] * fx
        if total > 0:
            date_values[d] = total

    sorted_dates = sorted(date_values.keys())
    return {
        "dates": sorted_dates,
        "closes": [date_values[d] for d in sorted_dates],
    }


def _fetch_drilldown_data(ticker: str, portfolio: Portfolio):
    """Fetch drill-down data for a ticker."""
    ticker_info = get_ticker_info(ticker)
    quote_type = ticker_info.get("quote_type", "EQUITY")
    history = get_history(ticker)

    result = {
        "ticker_info": ticker_info,
        "quote_type": quote_type,
        "history": history,
    }

    if quote_type == "ETF":
        etf_holdings = get_etf_holdings(ticker)
        if etf_holdings:
            symbols = [h["symbol"] for h in etf_holdings]
            prices = get_prices(symbols)
            result["etf_holdings"] = etf_holdings
            result["etf_prices"] = prices
        else:
            result["etf_holdings"] = []
    else:
        holdings = portfolio.get_holdings()
        result["shares"] = holdings.get(ticker, 0)
        result["avg_cost"] = portfolio.get_avg_cost(ticker)

    return result


def _fetch_allocation_data(portfolio: Portfolio, portfolio_name: str | None, display_currency: str):
    """Fetch allocation and look-through data."""
    holdings = portfolio.get_holdings(portfolio_name)
    if not holdings:
        return {"empty": True}

    tickers = sorted(holdings.keys())
    prices = get_prices(tickers)

    native_currencies = [prices.get(t, {}).get("currency", "USD") for t in tickers]
    fx_rates = get_exchange_rates(display_currency, native_currencies)

    rows = []
    for ticker in tickers:
        info = prices.get(ticker, {})
        price = info.get("price", 0)
        name = info.get("name", ticker)
        native_currency = info.get("currency", "USD")
        fx = fx_rates.get(native_currency, 1.0)
        shares = holdings[ticker]
        value = shares * price * fx
        change_pct = info.get("change_pct", 0) or 0
        rows.append({"ticker": ticker, "name": name, "value": value, "change_pct": change_pct})

    total_value = sum(r["value"] for r in rows)
    rows.sort(key=lambda r: r["value"], reverse=True)

    ticker_types = {}
    etf_holdings_map = {}
    for ticker in tickers:
        tinfo = get_ticker_info(ticker)
        qtype = tinfo.get("quote_type", "EQUITY")
        ticker_types[ticker] = qtype
        if qtype != "EQUITY":
            etf_h = get_etf_holdings(ticker)
            if etf_h:
                etf_holdings_map[ticker] = etf_h

    # Look-through computation
    underlying = {}
    for r in rows:
        ticker = r["ticker"]
        alloc_pct = (r["value"] / total_value * 100) if total_value > 0 else 0
        if ticker in etf_holdings_map:
            for h in etf_holdings_map[ticker]:
                sym = h["symbol"]
                effective_pct = alloc_pct * h["weight"] / 100
                if sym in underlying:
                    underlying[sym]["exposure_pct"] += effective_pct
                    underlying[sym]["sources"].append(ticker)
                else:
                    underlying[sym] = {
                        "name": h.get("name", sym),
                        "exposure_pct": effective_pct,
                        "sources": [ticker],
                    }
        else:
            sym = ticker
            if sym in underlying:
                underlying[sym]["exposure_pct"] += alloc_pct
                underlying[sym]["sources"].append("Direct")
            else:
                underlying[sym] = {
                    "name": r["name"],
                    "exposure_pct": alloc_pct,
                    "sources": ["Direct"],
                }

    top_underlying = sorted(
        underlying.items(), key=lambda x: x[1]["exposure_pct"], reverse=True
    )[:10]

    # Fetch prices for underlying tickers to get daily change
    underlying_symbols = [sym for sym, _ in top_underlying]
    underlying_prices = get_prices(underlying_symbols) if underlying_symbols else {}
    for sym, udata in top_underlying:
        uinfo = underlying_prices.get(sym, {})
        udata["change_pct"] = uinfo.get("change_pct", 0) or 0

    return {
        "empty": False,
        "rows": rows,
        "total_value": total_value,
        "ticker_types": ticker_types,
        "top_underlying": top_underlying,
        "resolved_tickers": set(etf_holdings_map.keys()),
        "display_currency": display_currency,
    }
