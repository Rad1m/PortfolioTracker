#!/usr/bin/env python3
"""Portfolio Tracker — Textual TUI for tracking investments."""

import re
from datetime import datetime

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Static, TabbedContent, TabPane
from textual import work

from market import clear_cache, get_etf_holdings, get_exchange_rates, get_history, get_prices, get_ticker_info
from storage import Portfolio, Transaction
from ui import (
    APP_CSS,
    ConfirmModal,
    CreatePortfolioModal,
    EmptyState,
    HelpOverlay,
    BigValue,
    ImportModal,
    LoadingIndicator,
    MoveToPortfolioModal,
    PortfolioHeader,
    PriceChart,
    StockDetail,
    TransactionModal,
    format_pct,
    format_pnl,
)


SORT_MODES = ["ticker", "value", "pnl_pct_desc", "pnl_pct_asc"]
SORT_LABELS = {
    "ticker": "Ticker A→Z",
    "value": "Value ↓",
    "pnl_pct_desc": "P&L% ↓",
    "pnl_pct_asc": "P&L% ↑",
}
CURRENCIES = ["USD", "GBP", "EUR", "CHF", "JPY"]


def _safe_id(name: str) -> str:
    """Convert a portfolio name to a valid CSS ID."""
    return "tab-" + re.sub(r"[^a-z0-9-]", "-", name.lower()).strip("-")


class PortfolioView(Vertical):
    """Reusable widget showing holdings for one portfolio (or all)."""

    def __init__(self, portfolio_name: str | None = None, **kwargs):
        super().__init__(**kwargs)
        self.portfolio_name = portfolio_name
        self._tickers: list[str] = []
        self._prices: dict[str, dict] = {}
        self._rows: list[dict] = []
        self._fx_rates: dict[str, float] = {}
        self._day_pct = 0.0
        self._three_month_pct = 0.0

    @property
    def _portfolio(self) -> Portfolio:
        return self.app.portfolio  # type: ignore[attr-defined]

    @property
    def _display_currency(self) -> str:
        return self._portfolio.display_currency

    @property
    def _sort_mode(self) -> str:
        return self._portfolio.sort_mode

    def compose(self) -> ComposeResult:
        yield PortfolioHeader(classes="portfolio-header")
        yield BigValue(classes="big-value")
        yield LoadingIndicator("Fetching market data, please wait...", classes="view-loading")
        yield DataTable(classes="holdings-table", cursor_type="row")
        yield EmptyState(
            "No holdings yet. Press [bold]b[/] to add your first transaction.",
            classes="view-empty",
        )
        yield PriceChart(classes="view-chart")

    def on_mount(self) -> None:
        table = self.query_one(".holdings-table", DataTable)
        table.add_columns("Ticker", "Name", "Shares", "Avg Cost", "Price", "Value", "P&L", "P&L %", "Alloc %")
        table.display = False
        self.query_one(".big-value").display = False
        self.query_one(".view-chart").display = False
        self.query_one(".view-empty").display = False
        self.refresh_data()
        self.set_interval(1800, self.refresh_data)

    @work(thread=True)
    def refresh_data(self) -> None:
        header = self.query_one(".portfolio-header", PortfolioHeader)
        self.app.call_from_thread(header.update_stats, loading=True)

        holdings = self._portfolio.get_holdings(self.portfolio_name)
        if not holdings:
            self.app.call_from_thread(self._show_empty, True)
            self.app.call_from_thread(header.update_stats, loading=False)
            return

        tickers = sorted(holdings.keys())
        prices = get_prices(tickers)
        avg_costs = {t: self._portfolio.get_avg_cost(t, self.portfolio_name) for t in tickers}

        native_currencies = [prices.get(t, {}).get("currency", "USD") for t in tickers]
        fx_rates = get_exchange_rates(self._display_currency, native_currencies)

        histories = {t: get_history(t) for t in tickers}
        chart_data = self._compute_portfolio_history(holdings, histories)
        self.app.call_from_thread(self._update_chart, chart_data)

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
        chart = self.query_one(".view-chart", PriceChart)
        if chart_data["dates"]:
            label = self.portfolio_name or "Portfolio"
            chart.set_data(label, chart_data["dates"], chart_data["closes"])

    def _show_empty(self, show: bool) -> None:
        self.query_one(".view-loading").display = False
        self.query_one(".big-value").display = False
        self.query_one(".view-empty").display = show
        self.query_one(".holdings-table").display = not show
        self.query_one(".view-chart").display = not show

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

        self._rows = []
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

            self._rows.append({
                "ticker": ticker, "name": name, "shares": shares,
                "avg": avg * fx, "price": price * fx, "value": value,
                "pnl": pnl, "pnl_pct": pnl_pct,
            })

        self._day_pct = (day_change_value / (total_value_for_day - day_change_value) * 100) if total_value_for_day > day_change_value else 0.0
        self._render_table()

    def _sorted_rows(self) -> list[dict]:
        rows = list(self._rows)
        mode = self._sort_mode
        if mode == "ticker":
            rows.sort(key=lambda r: r["ticker"])
        elif mode == "value":
            rows.sort(key=lambda r: r["value"], reverse=True)
        elif mode == "pnl_pct_desc":
            rows.sort(key=lambda r: r["pnl_pct"], reverse=True)
        elif mode == "pnl_pct_asc":
            rows.sort(key=lambda r: r["pnl_pct"])
        return rows

    def _render_table(self) -> None:
        self.query_one(".view-loading").display = False
        self.query_one(".big-value").display = True
        self.query_one(".holdings-table").display = True
        self.query_one(".view-chart").display = True
        table = self.query_one(".holdings-table", DataTable)
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
        sort_label = SORT_LABELS[self._sort_mode]
        header = self.query_one(".portfolio-header", PortfolioHeader)
        header.update_stats(total_value, total_pnl, total_pnl_pct, now, sort_hint=sort_label)

        big = self.query_one(".big-value", BigValue)
        big.set_value(
            total_value,
            currency=self._display_currency,
            pnl_pct=total_pnl_pct,
            day_pct=self._day_pct,
            three_month_pct=self._three_month_pct,
        )

    def cycle_sort(self) -> None:
        if not self._rows:
            return
        idx = SORT_MODES.index(self._sort_mode)
        new_mode = SORT_MODES[(idx + 1) % len(SORT_MODES)]
        self._portfolio.sort_mode = new_mode
        self._portfolio.save()
        self._render_table()

    def cycle_currency(self) -> None:
        idx = CURRENCIES.index(self._display_currency)
        self._portfolio.display_currency = CURRENCIES[(idx + 1) % len(CURRENCIES)]
        self._portfolio.save()
        self.refresh_data()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        row_idx = event.cursor_row
        if 0 <= row_idx < len(self._tickers):
            ticker = self._tickers[row_idx]
            name = self._prices.get(ticker, {}).get("name", ticker)
            self.app.push_screen(DrillDownScreen(ticker, name))


class PortfolioScreen(Screen):
    """Main screen with tabbed portfolios."""

    BINDINGS = [
        Binding("b", "buy", "Buy"),
        Binding("s", "sell", "Sell"),
        Binding("t", "transactions", "History"),
        Binding("i", "import_csv", "Import CSV"),
        Binding("o", "cycle_sort", "Sort"),
        Binding("c", "cycle_currency", "Currency"),
        Binding("a", "allocation", "Allocation"),
        Binding("m", "move_ticker", "Move Ticker"),
        Binding("n", "new_portfolio", "New Portfolio"),
        Binding("d", "delete_portfolio", "Delete Portfolio"),
        Binding("1", "tab_1", "Tab 1", show=False),
        Binding("2", "tab_2", "Tab 2", show=False),
        Binding("3", "tab_3", "Tab 3", show=False),
        Binding("4", "tab_4", "Tab 4", show=False),
        Binding("5", "tab_5", "Tab 5", show=False),
        Binding("6", "tab_6", "Tab 6", show=False),
        Binding("7", "tab_7", "Tab 7", show=False),
        Binding("8", "tab_8", "Tab 8", show=False),
        Binding("9", "tab_9", "Tab 9", show=False),
    ]

    def compose(self) -> ComposeResult:
        portfolio: Portfolio = self.app.portfolio  # type: ignore[attr-defined]
        with TabbedContent(id="portfolio-tabs"):
            with TabPane("All", id="tab-all"):
                yield PortfolioView(portfolio_name=None)
            for name in portfolio.portfolios:
                with TabPane(name, id=_safe_id(name)):
                    yield PortfolioView(portfolio_name=name)
        yield Footer()

    def _active_view(self) -> PortfolioView | None:
        tabbed = self.query_one("#portfolio-tabs", TabbedContent)
        pane = tabbed.active_pane
        if pane is not None:
            try:
                return pane.query_one(PortfolioView)
            except Exception:
                return None
        return None

    def _active_portfolio_name(self) -> str:
        view = self._active_view()
        if view is None:
            return ""
        return view.portfolio_name or ""

    def _refresh_all_views(self) -> None:
        for view in self.query(PortfolioView):
            view.refresh_data()

    def _switch_to_tab(self, index: int) -> None:
        tabbed = self.query_one("#portfolio-tabs", TabbedContent)
        panes = list(tabbed.query(TabPane))
        if 0 <= index < len(panes):
            tabbed.active = panes[index].id or ""

    def action_tab_1(self) -> None:
        self._switch_to_tab(0)

    def action_tab_2(self) -> None:
        self._switch_to_tab(1)

    def action_tab_3(self) -> None:
        self._switch_to_tab(2)

    def action_tab_4(self) -> None:
        self._switch_to_tab(3)

    def action_tab_5(self) -> None:
        self._switch_to_tab(4)

    def action_tab_6(self) -> None:
        self._switch_to_tab(5)

    def action_tab_7(self) -> None:
        self._switch_to_tab(6)

    def action_tab_8(self) -> None:
        self._switch_to_tab(7)

    def action_tab_9(self) -> None:
        self._switch_to_tab(8)

    def on_screen_resume(self) -> None:
        self._refresh_all_views()

    def action_buy(self) -> None:
        pname = self._active_portfolio_name()
        self.app.push_screen(TransactionModal("buy", portfolio_name=pname), callback=self._on_transaction)

    def action_sell(self) -> None:
        pname = self._active_portfolio_name()
        self.app.push_screen(TransactionModal("sell", portfolio_name=pname), callback=self._on_transaction)

    def _on_transaction(self, result: dict | None) -> None:
        if result:
            txn = Transaction(**result)
            self.app.portfolio.add_transaction(txn)  # type: ignore[attr-defined]
            self._refresh_all_views()

    def action_transactions(self) -> None:
        pname = self._active_portfolio_name()
        self.app.push_screen(TransactionHistoryScreen(portfolio_name=pname or None))

    def action_import_csv(self) -> None:
        pname = self._active_portfolio_name()
        self.app.push_screen(ImportModal(portfolio_name=pname), callback=self._on_import)

    def _on_import(self, result: dict | None) -> None:
        if result and result.get("imported", 0) > 0:
            self._refresh_all_views()

    def action_cycle_sort(self) -> None:
        view = self._active_view()
        if view:
            view.cycle_sort()
            # Re-render other views too so sort is consistent
            for v in self.query(PortfolioView):
                if v is not view and v._rows:
                    v._render_table()

    def action_cycle_currency(self) -> None:
        view = self._active_view()
        if view:
            view.cycle_currency()
            # All views need refresh since currency changed globally
            for v in self.query(PortfolioView):
                if v is not view:
                    v.refresh_data()

    def action_allocation(self) -> None:
        portfolio: Portfolio = self.app.portfolio  # type: ignore[attr-defined]
        pname = self._active_portfolio_name()
        self.app.push_screen(AllocationScreen(portfolio.display_currency, portfolio_name=pname or None))

    def action_new_portfolio(self) -> None:
        self.app.push_screen(CreatePortfolioModal(), callback=self._on_new_portfolio)

    def _on_new_portfolio(self, name: str | None) -> None:
        if not name:
            return
        portfolio: Portfolio = self.app.portfolio  # type: ignore[attr-defined]
        if not portfolio.add_portfolio(name):
            self.notify(f"Portfolio '{name}' already exists", severity="warning")
            return
        tabbed = self.query_one("#portfolio-tabs", TabbedContent)
        new_pane = TabPane(name, PortfolioView(portfolio_name=name), id=_safe_id(name))
        tabbed.add_pane(new_pane)
        tabbed.active = _safe_id(name)

    def action_delete_portfolio(self) -> None:
        pname = self._active_portfolio_name()
        if not pname:
            self.notify("Cannot delete the 'All' tab", severity="warning")
            return
        self.app.push_screen(
            ConfirmModal(f"Delete portfolio [bold]{pname}[/]?\n\nTransactions will become untagged."),
            callback=self._on_delete_portfolio,
        )

    def _on_delete_portfolio(self, confirmed: bool) -> None:
        if not confirmed:
            return
        pname = self._active_portfolio_name()
        if not pname:
            return
        portfolio: Portfolio = self.app.portfolio  # type: ignore[attr-defined]
        tab_id = _safe_id(pname)
        portfolio.remove_portfolio(pname)
        tabbed = self.query_one("#portfolio-tabs", TabbedContent)
        tabbed.remove_pane(tab_id)
        # Refresh "All" view since untagged transactions changed
        self._refresh_all_views()

    def action_move_ticker(self) -> None:
        view = self._active_view()
        if not view or not view._tickers:
            return
        table = view.query_one(".holdings-table", DataTable)
        row_idx = table.cursor_row
        if row_idx < 0 or row_idx >= len(view._tickers):
            return
        ticker = view._tickers[row_idx]
        portfolio: Portfolio = self.app.portfolio  # type: ignore[attr-defined]
        self._move_ticker = ticker
        self._move_from = view.portfolio_name or ""
        self.app.push_screen(
            MoveToPortfolioModal(portfolio.portfolios, current_portfolio=self._move_from),
            callback=self._on_move_ticker,
        )

    def _on_move_ticker(self, target: str | None) -> None:
        if target is None:
            return
        from_p = self._move_from
        if target == from_p:
            return
        portfolio: Portfolio = self.app.portfolio  # type: ignore[attr-defined]
        # from_p="" means "All" tab — pass None to move from any portfolio
        moved = portfolio.move_ticker(self._move_ticker, None if not from_p else from_p, target)
        if moved:
            self.notify(f"Moved {moved} {self._move_ticker} transaction(s) → {target or '(untagged)'}")
            self._refresh_all_views()


class AllocationScreen(Screen):
    """Allocation breakdown and top 10 look-through underlying holdings."""

    BINDINGS = [
        Binding("escape", "go_back", "Back"),
    ]

    def __init__(self, display_currency: str = "USD", portfolio_name: str | None = None):
        super().__init__()
        self._display_currency = display_currency
        self._portfolio_name = portfolio_name

    def compose(self) -> ComposeResult:
        yield Static(
            "[bold #5b9bd5]Portfolio Allocation & Top Holdings[/]",
            id="allocation-header",
        )
        yield LoadingIndicator("Analyzing portfolio holdings...", id="loading")
        yield Static("", id="allocation-summary")
        yield DataTable(id="allocation-table", cursor_type="row")
        yield Static("", id="allocation-bars")
        yield Static("[bold #5b9bd5]Top 10 Underlying Holdings (Look-Through)[/]", id="lookthrough-title")
        yield DataTable(id="lookthrough-table", cursor_type="row")
        yield Static("", id="lookthrough-bars")
        yield Footer()

    def on_mount(self) -> None:
        alloc_table = self.query_one("#allocation-table", DataTable)
        alloc_table.add_columns("#", "Ticker", "Name", "Value", "Alloc %", "Day %", "Type")
        alloc_table.display = False

        lt_table = self.query_one("#lookthrough-table", DataTable)
        lt_table.add_columns("#", "Stock", "Name", "Exposure %", "Day %", "Via ETFs")
        lt_table.display = False

        self.query_one("#allocation-summary").display = False
        self.query_one("#lookthrough-title").display = False
        self.query_one("#allocation-bars").display = False
        self.query_one("#lookthrough-bars").display = False

        self.load_data()

    @work(thread=True)
    def load_data(self) -> None:
        portfolio: Portfolio = self.app.portfolio  # type: ignore[attr-defined]
        holdings = portfolio.get_holdings(self._portfolio_name)
        if not holdings:
            self.app.call_from_thread(self._show_empty)
            return

        tickers = sorted(holdings.keys())
        prices = get_prices(tickers)

        native_currencies = [prices.get(t, {}).get("currency", "USD") for t in tickers]
        fx_rates = get_exchange_rates(self._display_currency, native_currencies)

        rows = []
        for ticker in tickers:
            info = prices.get(ticker, {})
            price = info.get("price", 0)
            name = info.get("name", ticker)
            change_pct = info.get("change_pct", 0) or 0
            native_currency = info.get("currency", "USD")
            fx = fx_rates.get(native_currency, 1.0)
            shares = holdings[ticker]
            value = shares * price * fx
            rows.append({"ticker": ticker, "name": name, "value": value, "shares": shares, "change_pct": change_pct})

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

        underlying: dict[str, dict] = {}
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

        # Fetch daily change for underlying tickers
        underlying_symbols = [sym for sym, _ in top_underlying]
        underlying_prices = get_prices(underlying_symbols) if underlying_symbols else {}
        for sym, udata in top_underlying:
            uinfo = underlying_prices.get(sym, {})
            udata["change_pct"] = uinfo.get("change_pct", 0) or 0

        resolved_tickers = set(etf_holdings_map.keys())
        self.app.call_from_thread(
            self._update_tables, rows, total_value, ticker_types, top_underlying, resolved_tickers,
        )

    def _show_empty(self) -> None:
        self.query_one("#loading").display = False
        self.query_one("#allocation-summary", Static).update("[dim]No holdings to analyze.[/]")
        self.query_one("#allocation-summary").display = True

    @staticmethod
    def _render_bar_chart(items: list[tuple[str, float, float]], bar_width: int = 30) -> str:
        """Render a horizontal bar chart.

        items: list of (label, weight, change_pct)
        Returns rich markup string.
        """
        if not items:
            return ""
        max_weight = max(w for _, w, _ in items)
        lines = []
        for label, weight, change_pct in items:
            bar_len = int(weight / max_weight * bar_width) if max_weight > 0 else 0
            bar_len = max(1, bar_len)
            color = "#6a9955" if change_pct >= 0 else "#d16969"
            bar = "█" * bar_len
            pct_str = f"{change_pct:+.2f}%"
            lines.append(
                f"  {label:<12} [{color}]{bar}[/] {weight:5.1f}%  [{color}]{pct_str}[/]"
            )
        return "\n".join(lines)

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

        alloc_table = self.query_one("#allocation-table", DataTable)
        alloc_table.display = True
        alloc_table.clear()

        alloc_bar_items = []
        for i, r in enumerate(rows, 1):
            alloc_pct = (r["value"] / total_value * 100) if total_value > 0 else 0
            qtype = ticker_types.get(r["ticker"], "EQUITY")
            resolved = r["ticker"] in resolved_tickers
            type_label = f"{qtype}" + (" *" if resolved else "")
            change_pct = r.get("change_pct", 0)
            alloc_table.add_row(
                str(i),
                r["ticker"],
                Text(r["name"][:30]),
                Text(f"{r['value']:,.0f}", justify="right"),
                Text(f"{alloc_pct:.1f}%", justify="right"),
                format_pct(change_pct),
                type_label,
            )
            alloc_bar_items.append((r["ticker"], alloc_pct, change_pct))

        # Allocation bar chart
        alloc_bars = self.query_one("#allocation-bars", Static)
        alloc_bars.update(self._render_bar_chart(alloc_bar_items))
        alloc_bars.display = True

        self.query_one("#lookthrough-title").display = True
        lt_table = self.query_one("#lookthrough-table", DataTable)
        lt_table.display = True
        lt_table.clear()

        lt_bar_items = []
        for i, (sym, data) in enumerate(top_underlying, 1):
            sources = ", ".join(dict.fromkeys(data["sources"]))
            change_pct = data.get("change_pct", 0)
            lt_table.add_row(
                str(i),
                sym,
                Text(data["name"][:30]),
                Text(f"{data['exposure_pct']:.2f}%", justify="right"),
                format_pct(change_pct),
                Text(sources[:40]),
            )
            lt_bar_items.append((sym, data["exposure_pct"], change_pct))

        # Look-through bar chart
        lt_bars = self.query_one("#lookthrough-bars", Static)
        lt_bars.update(self._render_bar_chart(lt_bar_items))
        lt_bars.display = True

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
        yield StockDetail(id="stock-detail")
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
        ticker_info = get_ticker_info(self.ticker)
        quote_type = ticker_info.get("quote_type", "EQUITY")

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
        Binding("d", "delete_transaction", "Delete"),
        Binding("m", "move_transaction", "Move"),
    ]

    def __init__(self, portfolio_name: str | None = None):
        super().__init__()
        self._portfolio_name = portfolio_name
        self._transactions: list[Transaction] = []

    def compose(self) -> ComposeResult:
        yield Static("Transaction History", id="history-header")
        yield DataTable(id="history-table", cursor_type="row")
        yield EmptyState("No transactions recorded.", id="empty-state")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#history-table", DataTable)
        table.add_columns("Date", "Type", "Ticker", "Shares", "Price", "Total", "Portfolio", "Note")
        self._load_transactions()

    def _load_transactions(self) -> None:
        portfolio: Portfolio = self.app.portfolio  # type: ignore[attr-defined]
        transactions = portfolio.get_transactions(portfolio_name=self._portfolio_name)
        self._transactions = sorted(transactions, key=lambda x: x.date, reverse=True)

        if not self._transactions:
            self.query_one("#empty-state").display = True
            self.query_one("#history-table").display = False
            return

        self.query_one("#empty-state").display = False
        self.query_one("#history-table").display = True

        label = self._portfolio_name or "All"
        header = self.query_one("#history-header", Static)
        header.update(f"[bold #5b9bd5]Transaction History[/] — {label}    {len(self._transactions)} total")

        table = self.query_one("#history-table", DataTable)
        table.clear()

        for t in self._transactions:
            type_color = "green" if t.type == "buy" else "red"
            total = t.shares * t.price
            table.add_row(
                t.date,
                Text(t.type.upper(), style=type_color),
                t.ticker,
                Text(f"{t.shares:.2f}", justify="right"),
                Text(f"{t.price:.2f}", justify="right"),
                Text(f"{total:,.2f}", justify="right"),
                t.portfolio or "—",
                t.note or "",
            )

    def action_delete_transaction(self) -> None:
        table = self.query_one("#history-table", DataTable)
        row_idx = table.cursor_row
        if row_idx < 0 or row_idx >= len(self._transactions):
            return
        txn = self._transactions[row_idx]
        self.app.push_screen(
            ConfirmModal(
                f"Delete transaction?\n\n"
                f"  {txn.type.upper()} {txn.shares:.2f} x {txn.ticker} @ {txn.price:.2f}\n"
                f"  Date: {txn.date}"
            ),
            callback=self._on_delete_confirmed,
        )

    def _on_delete_confirmed(self, confirmed: bool) -> None:
        if not confirmed:
            return
        table = self.query_one("#history-table", DataTable)
        row_idx = table.cursor_row
        if row_idx < 0 or row_idx >= len(self._transactions):
            return
        txn = self._transactions[row_idx]
        portfolio: Portfolio = self.app.portfolio  # type: ignore[attr-defined]
        portfolio.delete_transaction(txn)
        self._load_transactions()

    def action_move_transaction(self) -> None:
        table = self.query_one("#history-table", DataTable)
        row_idx = table.cursor_row
        if row_idx < 0 or row_idx >= len(self._transactions):
            return
        txn = self._transactions[row_idx]
        portfolio: Portfolio = self.app.portfolio  # type: ignore[attr-defined]
        self._move_txn = txn
        self.app.push_screen(
            MoveToPortfolioModal(portfolio.portfolios, current_portfolio=txn.portfolio),
            callback=self._on_move_selected,
        )

    def _on_move_selected(self, target: str | None) -> None:
        if target is None:
            return
        txn = self._move_txn
        if txn.portfolio == target:
            return
        portfolio: Portfolio = self.app.portfolio  # type: ignore[attr-defined]
        portfolio.move_transaction(txn, target)
        self._load_transactions()

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
        if hasattr(screen, "_refresh_all_views"):
            screen._refresh_all_views()
        elif hasattr(screen, "refresh_data"):
            screen.refresh_data()
        elif hasattr(screen, "load_data"):
            screen.load_data()

    def action_help(self) -> None:
        self.push_screen(HelpOverlay())


if __name__ == "__main__":
    app = PortfolioApp()
    app.run()
