#!/usr/bin/env python3
"""Portfolio Tracker — Textual TUI for tracking investments."""

from datetime import datetime

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Static
from textual import work

from market import clear_cache, get_etf_holdings, get_exchange_rates, get_history, get_prices, get_ticker_info
from storage import Portfolio, Transaction
from ui import (
    APP_CSS,
    EmptyState,
    HelpOverlay,
    BigValue,
    ImportModal,
    LoadingIndicator,
    PortfolioHeader,
    PriceChart,
    StockDetail,
    TransactionModal,
    format_pct,
    format_pnl,
)


class PortfolioScreen(Screen):
    """Main screen — portfolio holdings table."""

    SORT_MODES = ["ticker", "value", "pnl_pct_desc", "pnl_pct_asc"]
    SORT_LABELS = {
        "ticker": "Ticker A→Z",
        "value": "Value ↓",
        "pnl_pct_desc": "P&L% ↓",
        "pnl_pct_asc": "P&L% ↑",
    }
    CURRENCIES = ["USD", "GBP", "EUR", "CHF", "JPY"]

    BINDINGS = [
        Binding("b", "buy", "Buy"),
        Binding("s", "sell", "Sell"),
        Binding("t", "transactions", "History"),
        Binding("i", "import_csv", "Import CSV"),
        Binding("o", "cycle_sort", "Sort"),
        Binding("c", "cycle_currency", "Currency"),
        Binding("a", "allocation", "Allocation"),
    ]

    def compose(self) -> ComposeResult:
        yield PortfolioHeader(id="portfolio-header")
        yield BigValue(id="big-value")
        yield LoadingIndicator("Fetching market data, please wait...", id="loading")
        yield DataTable(id="holdings-table", cursor_type="row")
        yield EmptyState(
            "No holdings yet. Press [bold]b[/] to add your first transaction.",
            id="empty-state",
        )
        yield PriceChart(id="price-chart")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#holdings-table", DataTable)
        table.add_columns("Ticker", "Name", "Shares", "Avg Cost", "Price", "Value", "P&L", "P&L %", "Alloc %")
        table.display = False
        self.query_one("#big-value").display = False
        self.query_one("#price-chart").display = False
        self.query_one("#empty-state").display = False
        self._tickers: list[str] = []
        self._prices: dict[str, dict] = {}
        self._rows: list[dict] = []
        self._sort_mode = "ticker"
        self._display_currency = self.app.portfolio.display_currency  # type: ignore[attr-defined]
        self._fx_rates: dict[str, float] = {}
        self.refresh_data()
        self.set_interval(1800, self.refresh_data)

    def on_screen_resume(self) -> None:
        self.refresh_data()

    @work(thread=True)
    def refresh_data(self) -> None:
        portfolio: Portfolio = self.app.portfolio  # type: ignore[attr-defined]
        header = self.query_one("#portfolio-header", PortfolioHeader)

        self.app.call_from_thread(header.update_stats, loading=True)

        holdings = portfolio.get_holdings()
        if not holdings:
            self.app.call_from_thread(self._show_empty, True)
            self.app.call_from_thread(header.update_stats, loading=False)
            return

        tickers = sorted(holdings.keys())
        prices = get_prices(tickers)
        avg_costs = {t: portfolio.get_avg_cost(t) for t in tickers}

        # Fetch exchange rates for currency conversion
        native_currencies = [prices.get(t, {}).get("currency", "USD") for t in tickers]
        fx_rates = get_exchange_rates(self._display_currency, native_currencies)

        # Fetch history for all tickers and compute aggregate portfolio value
        histories = {t: get_history(t) for t in tickers}
        chart_data = self._compute_portfolio_history(holdings, histories)
        self.app.call_from_thread(self._update_chart, chart_data)

        # Compute 3-month change from chart data
        closes = chart_data.get("closes", [])
        three_month_pct = ((closes[-1] / closes[0]) - 1) * 100 if len(closes) >= 2 else 0.0

        self.app.call_from_thread(
            self._update_table, holdings, tickers, avg_costs, prices, fx_rates, three_month_pct,
        )

    @staticmethod
    def _compute_portfolio_history(
        holdings: dict[str, float],
        histories: dict[str, dict],
    ) -> dict:
        """Aggregate per-ticker history into total portfolio value per day."""
        # Collect all dates with per-ticker close prices
        date_values: dict[str, float] = {}
        all_dates: set[str] = set()
        ticker_data: dict[str, dict[str, float]] = {}

        for ticker, hist in histories.items():
            dates = hist.get("dates", [])
            closes = hist.get("closes", [])
            if dates and closes:
                ticker_data[ticker] = dict(zip(dates, closes))
                all_dates.update(dates)

        if not all_dates:
            return {"dates": [], "closes": []}

        for d in sorted(all_dates):
            total = 0.0
            for ticker, shares in holdings.items():
                td = ticker_data.get(ticker, {})
                if d in td:
                    total += shares * td[d]
            if total > 0:
                date_values[d] = total

        sorted_dates = sorted(date_values.keys())
        return {
            "dates": sorted_dates,
            "closes": [date_values[d] for d in sorted_dates],
        }

    def _update_chart(self, chart_data: dict) -> None:
        chart = self.query_one("#price-chart", PriceChart)
        if chart_data["dates"]:
            chart.set_data("Portfolio", chart_data["dates"], chart_data["closes"])

    def _show_empty(self, show: bool) -> None:
        self.query_one("#loading").display = False
        self.query_one("#big-value").display = False
        self.query_one("#empty-state").display = show
        self.query_one("#holdings-table").display = not show
        self.query_one("#price-chart").display = not show

    def _update_table(
        self,
        holdings: dict[str, float],
        tickers: list[str],
        avg_costs: dict[str, float],
        prices: dict[str, dict],
        fx_rates: dict[str, float],
        three_month_pct: float = 0.0,
    ) -> None:
        self._prices = prices
        self._fx_rates = fx_rates
        self._three_month_pct = three_month_pct
        self._show_empty(False)

        # Build row data for sorting
        self._rows = []
        self._day_change_value = 0.0
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

            # Track weighted day change
            total_value_for_day += value
            self._day_change_value += value * (change_pct / 100)

            self._rows.append({
                "ticker": ticker, "name": name, "shares": shares,
                "avg": avg * fx, "price": price * fx, "value": value,
                "pnl": pnl, "pnl_pct": pnl_pct,
            })

        # Compute day change as % of total
        self._day_pct = (self._day_change_value / (total_value_for_day - self._day_change_value) * 100) if total_value_for_day > self._day_change_value else 0.0

        self._render_table()

    def _sorted_rows(self) -> list[dict]:
        """Return rows sorted by current sort mode."""
        rows = list(self._rows)
        if self._sort_mode == "ticker":
            rows.sort(key=lambda r: r["ticker"])
        elif self._sort_mode == "value":
            rows.sort(key=lambda r: r["value"], reverse=True)
        elif self._sort_mode == "pnl_pct_desc":
            rows.sort(key=lambda r: r["pnl_pct"], reverse=True)
        elif self._sort_mode == "pnl_pct_asc":
            rows.sort(key=lambda r: r["pnl_pct"])
        return rows

    def _render_table(self) -> None:
        """Sort and render rows into the DataTable."""
        self.query_one("#loading").display = False
        self.query_one("#big-value").display = True
        self.query_one("#holdings-table").display = True
        self.query_one("#price-chart").display = True
        table = self.query_one("#holdings-table", DataTable)
        table.clear()

        sorted_rows = self._sorted_rows()
        self._tickers = [r["ticker"] for r in sorted_rows]

        total_value = sum(r["value"] for r in sorted_rows)
        total_cost = 0.0

        for r in sorted_rows:
            total_cost += r["shares"] * r["avg"]
            alloc_pct = (r["value"] / total_value * 100) if total_value > 0 else 0.0
            table.add_row(
                r["ticker"],
                Text(r["name"][:25]),
                Text(f"{r['shares']:.2f}", justify="right"),
                Text(f"{r['avg']:.2f}", justify="right"),
                Text(f"{r['price']:.2f}", justify="right"),
                Text(f"{r['value']:,.2f}", justify="right"),
                format_pnl(r["pnl"]),
                format_pct(r["pnl_pct"]),
                Text(f"{alloc_pct:.1f}%", justify="right"),
            )

        total_pnl = total_value - total_cost
        total_pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0.0
        now = datetime.now().strftime("%H:%M")
        sort_label = self.SORT_LABELS[self._sort_mode]
        header = self.query_one("#portfolio-header", PortfolioHeader)
        header.update_stats(total_value, total_pnl, total_pnl_pct, now, sort_hint=sort_label)

        big = self.query_one("#big-value", BigValue)
        big.set_value(
            total_value,
            currency=self._display_currency,
            pnl_pct=total_pnl_pct,
            day_pct=getattr(self, "_day_pct", 0.0),
            three_month_pct=getattr(self, "_three_month_pct", 0.0),
        )

    def action_cycle_sort(self) -> None:
        """Cycle through sort modes."""
        if not self._rows:
            return
        idx = self.SORT_MODES.index(self._sort_mode)
        self._sort_mode = self.SORT_MODES[(idx + 1) % len(self.SORT_MODES)]
        self._render_table()

    def action_cycle_currency(self) -> None:
        """Cycle display currency and refetch exchange rates."""
        idx = self.CURRENCIES.index(self._display_currency)
        self._display_currency = self.CURRENCIES[(idx + 1) % len(self.CURRENCIES)]
        # Persist preference
        portfolio: Portfolio = self.app.portfolio  # type: ignore[attr-defined]
        portfolio.display_currency = self._display_currency
        portfolio.save()
        # Refetch with new currency
        self.refresh_data()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Drill into ETF when Enter is pressed on a row."""
        row_idx = event.cursor_row
        if 0 <= row_idx < len(self._tickers):
            ticker = self._tickers[row_idx]
            name = self._prices.get(ticker, {}).get("name", ticker)
            self.app.push_screen(DrillDownScreen(ticker, name))

    def action_buy(self) -> None:
        self.app.push_screen(TransactionModal("buy"), callback=self._on_transaction)

    def action_sell(self) -> None:
        self.app.push_screen(TransactionModal("sell"), callback=self._on_transaction)

    def _on_transaction(self, result: dict | None) -> None:
        if result:
            txn = Transaction(**result)
            self.app.portfolio.add_transaction(txn)  # type: ignore[attr-defined]
            self.refresh_data()

    def action_transactions(self) -> None:
        self.app.push_screen(TransactionHistoryScreen())

    def action_import_csv(self) -> None:
        self.app.push_screen(ImportModal(), callback=self._on_import)

    def _on_import(self, result: dict | None) -> None:
        if result and result.get("imported", 0) > 0:
            self.refresh_data()

    def action_allocation(self) -> None:
        self.app.push_screen(AllocationScreen(self._display_currency))


class AllocationScreen(Screen):
    """Allocation breakdown and top 10 look-through underlying holdings."""

    BINDINGS = [
        Binding("escape", "go_back", "Back"),
    ]

    def __init__(self, display_currency: str = "USD"):
        super().__init__()
        self._display_currency = display_currency

    def compose(self) -> ComposeResult:
        yield Static(
            "[bold #5b9bd5]Portfolio Allocation & Top Holdings[/]",
            id="allocation-header",
        )
        yield LoadingIndicator("Analyzing portfolio holdings...", id="loading")
        yield Static("", id="allocation-summary")
        yield DataTable(id="allocation-table", cursor_type="row")
        yield Static("[bold #5b9bd5]Top 10 Underlying Holdings (Look-Through)[/]", id="lookthrough-title")
        yield DataTable(id="lookthrough-table", cursor_type="row")
        yield Footer()

    def on_mount(self) -> None:
        alloc_table = self.query_one("#allocation-table", DataTable)
        alloc_table.add_columns("#", "Ticker", "Name", "Value", "Alloc %", "Type")
        alloc_table.display = False

        lt_table = self.query_one("#lookthrough-table", DataTable)
        lt_table.add_columns("#", "Stock", "Name", "Exposure %", "Via ETFs")
        lt_table.display = False

        self.query_one("#allocation-summary").display = False
        self.query_one("#lookthrough-title").display = False

        self.load_data()

    @work(thread=True)
    def load_data(self) -> None:
        portfolio: Portfolio = self.app.portfolio  # type: ignore[attr-defined]
        holdings = portfolio.get_holdings()
        if not holdings:
            self.app.call_from_thread(self._show_empty)
            return

        tickers = sorted(holdings.keys())
        prices = get_prices(tickers)

        # Get FX rates
        native_currencies = [prices.get(t, {}).get("currency", "USD") for t in tickers]
        fx_rates = get_exchange_rates(self._display_currency, native_currencies)

        # Compute values in display currency
        rows = []
        for ticker in tickers:
            info = prices.get(ticker, {})
            price = info.get("price", 0)
            name = info.get("name", ticker)
            native_currency = info.get("currency", "USD")
            fx = fx_rates.get(native_currency, 1.0)
            shares = holdings[ticker]
            value = shares * price * fx
            rows.append({"ticker": ticker, "name": name, "value": value, "shares": shares})

        total_value = sum(r["value"] for r in rows)
        rows.sort(key=lambda r: r["value"], reverse=True)

        # Get ticker info to determine types and fetch ETF holdings for look-through
        # Try get_etf_holdings for all fund types (ETF, MUTUALFUND, etc.) — not just ETFs
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

        # Build look-through: aggregate underlying stock exposure
        underlying: dict[str, dict] = {}  # symbol -> {name, exposure_pct, sources}
        for r in rows:
            ticker = r["ticker"]
            alloc_pct = (r["value"] / total_value * 100) if total_value > 0 else 0
            if ticker in etf_holdings_map:
                # ETF: distribute its allocation to underlying stocks
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
                # Individual stock: counts as direct exposure
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

        # Sort underlying by exposure, take top 10
        top_underlying = sorted(
            underlying.items(), key=lambda x: x[1]["exposure_pct"], reverse=True
        )[:10]

        resolved_tickers = set(etf_holdings_map.keys())
        self.app.call_from_thread(
            self._update_tables, rows, total_value, ticker_types, top_underlying, resolved_tickers,
        )

    def _show_empty(self) -> None:
        self.query_one("#loading").display = False
        self.query_one("#allocation-summary", Static).update("[dim]No holdings to analyze.[/]")
        self.query_one("#allocation-summary").display = True

    def _update_tables(
        self,
        rows: list[dict],
        total_value: float,
        ticker_types: dict[str, str],
        top_underlying: list[tuple[str, dict]],
        resolved_tickers: set[str] | None = None,
    ) -> None:
        resolved_tickers = resolved_tickers or set()
        self.query_one("#loading").display = False

        # Update summary
        summary = self.query_one("#allocation-summary", Static)
        n_funds = sum(1 for t in ticker_types.values() if t != "EQUITY")
        n_resolved = len(resolved_tickers)
        n_stocks = len(ticker_types) - n_funds
        summary.update(
            f"[bold]{len(rows)}[/] holdings    "
            f"[#5b9bd5]{n_funds}[/] Funds ({n_resolved} resolved)    "
            f"[#5b9bd5]{n_stocks}[/] Stocks    "
            f"Total: [bold]{total_value:,.0f}[/] {self._display_currency}"
        )
        summary.display = True

        # Fill allocation table
        alloc_table = self.query_one("#allocation-table", DataTable)
        alloc_table.display = True
        alloc_table.clear()

        for i, r in enumerate(rows, 1):
            alloc_pct = (r["value"] / total_value * 100) if total_value > 0 else 0
            qtype = ticker_types.get(r["ticker"], "EQUITY")
            resolved = r["ticker"] in resolved_tickers
            type_label = f"{qtype}" + (" *" if resolved else "")
            alloc_table.add_row(
                str(i),
                r["ticker"],
                Text(r["name"][:30]),
                Text(f"{r['value']:,.0f}", justify="right"),
                Text(f"{alloc_pct:.1f}%", justify="right"),
                type_label,
            )

        # Fill look-through table
        self.query_one("#lookthrough-title").display = True
        lt_table = self.query_one("#lookthrough-table", DataTable)
        lt_table.display = True
        lt_table.clear()

        for i, (sym, data) in enumerate(top_underlying, 1):
            sources = ", ".join(dict.fromkeys(data["sources"]))  # deduplicate, preserve order
            lt_table.add_row(
                str(i),
                sym,
                Text(data["name"][:30]),
                Text(f"{data['exposure_pct']:.2f}%", justify="right"),
                Text(sources[:40]),
            )

    def action_go_back(self) -> None:
        self.app.pop_screen()


class DrillDownScreen(Screen):
    """Smart drill-down — ETF holdings or stock detail depending on quote type."""

    BINDINGS = [
        Binding("escape", "go_back", "Back"),
    ]

    def __init__(self, ticker: str, ticker_name: str):
        super().__init__()
        self.ticker = ticker
        self.ticker_name = ticker_name

    def compose(self) -> ComposeResult:
        yield Static(
            f"[bold #5b9bd5]{self.ticker}[/] — {self.ticker_name}",
            id="drilldown-header",
        )
        yield LoadingIndicator("Fetching data, please wait...", id="loading")
        # Stock detail (hidden by default, shown for stocks)
        yield StockDetail(id="stock-detail")
        # ETF holdings table (hidden by default, shown for ETFs)
        yield DataTable(id="etf-holdings-table", cursor_type="row")
        yield EmptyState(id="empty-state")
        yield PriceChart(id="price-chart")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#etf-holdings-table", DataTable)
        table.add_columns("#", "Symbol", "Name", "Weight %", "Price", "Day %")
        self.query_one("#stock-detail").display = False
        self.query_one("#etf-holdings-table").display = False
        self.query_one("#empty-state").display = False
        self.query_one("#price-chart").display = False
        self.load_data()

    @work(thread=True)
    def load_data(self) -> None:
        # Fetch ticker info to determine type
        ticker_info = get_ticker_info(self.ticker)
        quote_type = ticker_info.get("quote_type", "EQUITY")

        # Fetch price history for chart
        history = get_history(self.ticker)
        if history["dates"]:
            self.app.call_from_thread(self._update_chart, history)

        if quote_type == "ETF":
            self._load_etf(ticker_info)
        else:
            self._load_stock(ticker_info)

    def _load_etf(self, ticker_info: dict) -> None:
        etf_holdings = get_etf_holdings(self.ticker)
        if not etf_holdings:
            self.app.call_from_thread(self._show_etf_empty)
            return

        symbols = [h["symbol"] for h in etf_holdings]
        prices = get_prices(symbols)
        self.app.call_from_thread(self._update_etf_table, etf_holdings, prices)

    def _load_stock(self, ticker_info: dict) -> None:
        portfolio: Portfolio = self.app.portfolio  # type: ignore[attr-defined]
        holdings = portfolio.get_holdings()
        shares = holdings.get(self.ticker, 0)
        avg_cost = portfolio.get_avg_cost(self.ticker)
        self.app.call_from_thread(self._update_stock_detail, ticker_info, shares, avg_cost)

    def _update_chart(self, history: dict) -> None:
        self.query_one("#loading").display = False
        chart = self.query_one("#price-chart", PriceChart)
        chart.display = True
        chart.set_data(self.ticker, history["dates"], history["closes"])

    def _show_etf_empty(self) -> None:
        self.query_one("#loading").display = False
        empty = self.query_one("#empty-state", EmptyState)
        empty.update("Holdings data not available for this ticker.")
        empty.display = True

    def _update_etf_table(self, holdings: list[dict], prices: dict[str, dict]) -> None:
        self.query_one("#loading").display = False
        table = self.query_one("#etf-holdings-table", DataTable)
        table.display = True
        table.clear()

        total_weight = sum(h["weight"] for h in holdings)
        header = self.query_one("#drilldown-header", Static)
        header.update(
            f"[bold #5b9bd5]{self.ticker}[/] — {self.ticker_name}"
            f"    Weight coverage: {total_weight:.0f}%"
        )

        for i, h in enumerate(holdings, 1):
            symbol = h["symbol"]
            info = prices.get(symbol, {})
            price = info.get("price", 0)
            name = info.get("name", h.get("name", symbol))
            change = info.get("change_pct", 0)

            chg_color = "green" if change >= 0 else "red"
            table.add_row(
                str(i),
                symbol,
                Text(name[:30]),
                Text(f"{h['weight']:.1f}%", justify="right"),
                Text(f"{price:.2f}" if price else "N/A", justify="right"),
                Text(f"{change:+.2f}%", style=chg_color) if price else Text("N/A"),
            )

    def _update_stock_detail(self, ticker_info: dict, shares: float, avg_cost: float) -> None:
        self.query_one("#loading").display = False
        price = ticker_info.get("price", 0)
        currency = ticker_info.get("currency", "")
        header = self.query_one("#drilldown-header", Static)
        header.update(
            f"[bold #5b9bd5]{self.ticker}[/] — {self.ticker_name}"
            f"    Price: [bold]{price:.2f}[/] {currency}"
        )

        detail = self.query_one("#stock-detail", StockDetail)
        detail.set_data(ticker_info, shares, avg_cost)
        detail.display = True

    def action_go_back(self) -> None:
        self.app.pop_screen()


class TransactionHistoryScreen(Screen):
    """Full-screen transaction history."""

    BINDINGS = [
        Binding("escape", "go_back", "Back"),
    ]

    def compose(self) -> ComposeResult:
        yield Static("Transaction History", id="history-header")
        yield DataTable(id="history-table", cursor_type="row")
        yield EmptyState("No transactions recorded.", id="empty-state")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#history-table", DataTable)
        table.add_columns("Date", "Type", "Ticker", "Shares", "Price", "Total", "Note")
        self._load_transactions()

    def _load_transactions(self) -> None:
        portfolio: Portfolio = self.app.portfolio  # type: ignore[attr-defined]
        transactions = portfolio.get_transactions()

        if not transactions:
            self.query_one("#empty-state").display = True
            self.query_one("#history-table").display = False
            return

        self.query_one("#empty-state").display = False
        self.query_one("#history-table").display = True

        header = self.query_one("#history-header", Static)
        header.update(f"[bold #5b9bd5]Transaction History[/]    {len(transactions)} total")

        table = self.query_one("#history-table", DataTable)
        table.clear()

        for t in sorted(transactions, key=lambda x: x.date, reverse=True):
            type_color = "green" if t.type == "buy" else "red"
            total = t.shares * t.price
            table.add_row(
                t.date,
                Text(t.type.upper(), style=type_color),
                t.ticker,
                Text(f"{t.shares:.2f}", justify="right"),
                Text(f"{t.price:.2f}", justify="right"),
                Text(f"{total:,.2f}", justify="right"),
                t.note or "",
            )

    def action_go_back(self) -> None:
        self.app.pop_screen()


class PortfolioApp(App):
    """Portfolio Tracker — terminal TUI for tracking investments."""

    CSS = APP_CSS
    TITLE = "Portfolio Tracker"

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("question_mark", "help", "Help"),
    ]

    def __init__(self):
        super().__init__()
        self.portfolio = Portfolio()

    def on_mount(self) -> None:
        self.push_screen(PortfolioScreen())

    def action_refresh(self) -> None:
        clear_cache()
        screen = self.screen
        if hasattr(screen, "refresh_data"):
            screen.refresh_data()
        elif hasattr(screen, "load_data"):
            screen.load_data()

    def action_help(self) -> None:
        self.push_screen(HelpOverlay())


if __name__ == "__main__":
    app = PortfolioApp()
    app.run()
