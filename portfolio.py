#!/usr/bin/env python3
"""Portfolio Tracker — Textual TUI for tracking investments."""

from datetime import datetime

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Static
from textual import work

from market import get_etf_holdings, get_prices
from storage import Portfolio, Transaction
from ui import (
    APP_CSS,
    EmptyState,
    HelpOverlay,
    PortfolioHeader,
    TransactionModal,
    format_pct,
    format_pnl,
)


class PortfolioScreen(Screen):
    """Main screen — portfolio holdings table."""

    BINDINGS = [
        Binding("b", "buy", "Buy"),
        Binding("s", "sell", "Sell"),
        Binding("t", "transactions", "History"),
    ]

    def compose(self) -> ComposeResult:
        yield PortfolioHeader(id="portfolio-header")
        yield DataTable(id="holdings-table", cursor_type="row")
        yield EmptyState(
            "No holdings yet. Press [bold]b[/] to add your first transaction.",
            id="empty-state",
        )
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#holdings-table", DataTable)
        table.add_columns("Ticker", "Name", "Shares", "Avg Cost", "Price", "Value", "P&L", "P&L %")
        self._tickers: list[str] = []
        self._prices: dict[str, dict] = {}
        self.refresh_data()
        self.set_interval(60, self.refresh_data)

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
        self.app.call_from_thread(self._update_table, holdings, tickers, avg_costs, prices)

    def _show_empty(self, show: bool) -> None:
        self.query_one("#empty-state").display = show
        self.query_one("#holdings-table").display = not show

    def _update_table(
        self,
        holdings: dict[str, float],
        tickers: list[str],
        avg_costs: dict[str, float],
        prices: dict[str, dict],
    ) -> None:
        self._tickers = tickers
        self._prices = prices
        table = self.query_one("#holdings-table", DataTable)
        table.clear()
        self._show_empty(False)

        total_value = 0.0
        total_cost = 0.0

        for ticker in tickers:
            shares = holdings[ticker]
            avg = avg_costs.get(ticker, 0)
            info = prices.get(ticker, {})
            price = info.get("price", 0)
            name = info.get("name", ticker)

            value = shares * price
            cost = shares * avg
            pnl = value - cost
            pnl_pct = (pnl / cost * 100) if cost > 0 else 0.0

            total_value += value
            total_cost += cost

            table.add_row(
                ticker,
                Text(name[:25]),
                Text(f"{shares:.2f}", justify="right"),
                Text(f"{avg:.2f}", justify="right"),
                Text(f"{price:.2f}", justify="right"),
                Text(f"{value:,.2f}", justify="right"),
                format_pnl(pnl),
                format_pct(pnl_pct),
            )

        total_pnl = total_value - total_cost
        total_pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0.0
        now = datetime.now().strftime("%H:%M")
        header = self.query_one("#portfolio-header", PortfolioHeader)
        header.update_stats(total_value, total_pnl, total_pnl_pct, now)

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


class DrillDownScreen(Screen):
    """ETF drill-down — top holdings of a selected ETF."""

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
        yield DataTable(id="etf-holdings-table", cursor_type="row")
        yield EmptyState(
            "Holdings data not available for this ticker.",
            id="empty-state",
        )
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#etf-holdings-table", DataTable)
        table.add_columns("#", "Symbol", "Name", "Weight %", "Price", "Day %")
        self.query_one("#empty-state").display = False
        self.load_holdings()

    @work(thread=True)
    def load_holdings(self) -> None:
        etf_holdings = get_etf_holdings(self.ticker)
        if not etf_holdings:
            self.app.call_from_thread(self._show_empty)
            return

        symbols = [h["symbol"] for h in etf_holdings]
        prices = get_prices(symbols)
        self.app.call_from_thread(self._update_table, etf_holdings, prices)

    def _show_empty(self) -> None:
        self.query_one("#empty-state").display = True
        self.query_one("#etf-holdings-table").display = False

    def _update_table(self, holdings: list[dict], prices: dict[str, dict]) -> None:
        table = self.query_one("#etf-holdings-table", DataTable)
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
        screen = self.screen
        if hasattr(screen, "refresh_data"):
            screen.refresh_data()
        elif hasattr(screen, "load_holdings"):
            screen.load_holdings()

    def action_help(self) -> None:
        self.push_screen(HelpOverlay())


if __name__ == "__main__":
    app = PortfolioApp()
    app.run()
