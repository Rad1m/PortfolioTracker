"""Textual UI — widgets, modals, styles for Portfolio Tracker."""

from datetime import date

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import Button, Footer, Input, Label, Static
from textual_plotext import PlotextPlot


APP_CSS = """
$background: #1e1e1e;
$surface: #2a2a2a;
$text-primary: #d4d4d4;
$text-secondary: #808080;
$accent: #5b9bd5;
$positive: #6a9955;
$negative: #d16969;
$warning: #d7ba7d;

Screen {
    background: $background;
}

#portfolio-header {
    dock: top;
    height: 3;
    padding: 0 2;
    background: $surface;
    color: $text-primary;
    content-align: left middle;
}

#portfolio-header .label {
    text-style: bold;
    color: $accent;
}

EmptyState {
    width: 1fr;
    height: 1fr;
    content-align: center middle;
    color: $text-secondary;
}

DataTable {
    height: 1fr;
}

DataTable > .datatable--cursor {
    background: #2a4a6b;
    color: $text-primary;
}

DataTable > .datatable--header {
    background: $surface;
    color: $accent;
    text-style: bold;
}

Footer {
    background: $surface;
}

/* Transaction Modal */
TransactionModal {
    align: center middle;
}

#modal-dialog {
    width: 55;
    height: auto;
    max-height: 24;
    background: $surface;
    border: round $accent;
    padding: 1 2;
}

#modal-dialog #modal-title {
    text-align: center;
    text-style: bold;
    color: $accent;
    margin-bottom: 1;
}

#modal-dialog .field-label {
    margin-top: 1;
    color: $text-secondary;
}

#modal-dialog Input {
    margin-bottom: 0;
}

#modal-buttons {
    margin-top: 1;
    height: 3;
    align: center middle;
}

#modal-buttons Button {
    margin: 0 1;
    min-width: 12;
}

#btn-confirm {
    background: $accent;
}

#modal-error {
    color: $negative;
    text-align: center;
    height: 1;
    margin-top: 1;
}

/* Import Modal */
ImportModal {
    align: center middle;
}

#import-dialog {
    width: 60;
    height: auto;
    background: $surface;
    border: round $accent;
    padding: 1 2;
}

#import-dialog #import-title {
    text-align: center;
    text-style: bold;
    color: $accent;
    margin-bottom: 1;
}

#import-dialog .field-label {
    margin-top: 1;
    color: $text-secondary;
}

#import-dialog Input {
    margin-bottom: 0;
}

#import-result {
    margin-top: 1;
    color: $text-primary;
}

#import-error {
    color: $negative;
    text-align: center;
    height: 1;
    margin-top: 1;
}

#import-buttons {
    margin-top: 1;
    height: 3;
    align: center middle;
}

#import-buttons Button {
    margin: 0 1;
    min-width: 12;
}

/* Help Overlay */
HelpOverlay {
    align: center middle;
}

#help-dialog {
    width: 50;
    height: auto;
    background: $surface;
    border: round $accent;
    padding: 1 2;
}

#help-dialog #help-title {
    text-align: center;
    text-style: bold;
    color: $accent;
    margin-bottom: 1;
}

#help-dialog .help-section {
    color: $text-primary;
    margin-bottom: 1;
}

#help-dialog .help-section-title {
    text-style: bold;
    color: $accent;
}

/* Stock detail */
#stock-detail {
    height: auto;
    padding: 1 2;
    background: $surface;
    margin: 0 1;
}

#stock-detail .detail-section-title {
    text-style: bold;
    color: $accent;
    margin-bottom: 1;
}

#stock-detail .detail-row {
    color: $text-primary;
}

/* Price chart */
#price-chart {
    height: 15;
    margin: 0 1;
}

/* Drill-down header */
#drilldown-header {
    dock: top;
    height: 3;
    padding: 0 2;
    background: $surface;
    color: $text-primary;
    content-align: left middle;
}

/* History header */
#history-header {
    dock: top;
    height: 3;
    padding: 0 2;
    background: $surface;
    color: $text-primary;
    content-align: left middle;
}
"""


def format_pnl(value: float) -> Text:
    color = "green" if value >= 0 else "red"
    return Text(f"{value:+,.2f}", style=color)


def format_pct(value: float) -> Text:
    color = "green" if value >= 0 else "red"
    return Text(f"{value:+.1f}%", style=color)


class PortfolioHeader(Static):
    """Header showing portfolio total, P&L, and last update time."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._total = 0.0
        self._pnl = 0.0
        self._pnl_pct = 0.0
        self._last_update = ""
        self._loading = False

    def update_stats(
        self,
        total_value: float = 0.0,
        total_pnl: float = 0.0,
        total_pnl_pct: float = 0.0,
        last_update: str = "",
        loading: bool = False,
    ):
        self._total = total_value
        self._pnl = total_pnl
        self._pnl_pct = total_pnl_pct
        self._last_update = last_update
        self._loading = loading
        self._render_content()

    def _render_content(self):
        pnl_color = "green" if self._pnl >= 0 else "red"
        status = "Refreshing..." if self._loading else f"Last update: {self._last_update}"
        self.update(
            f"[bold #5b9bd5]PORTFOLIO TRACKER[/]    "
            f"Total: [bold]{self._total:,.2f}[/]  "
            f"P&L: [{pnl_color}]{self._pnl:+,.2f} ({self._pnl_pct:+.1f}%)[/]"
            f"    [dim]{status}[/]"
        )


class EmptyState(Static):
    """Centered message for empty states."""
    pass


class PriceChart(PlotextPlot):
    """3-month price chart using plotext."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._dates: list[str] = []
        self._closes: list[float] = []
        self._ticker = ""

    def set_data(self, ticker: str, dates: list[str], closes: list[float]) -> None:
        self._ticker = ticker
        self._dates = dates
        self._closes = closes
        self._draw()

    def on_resize(self) -> None:
        self._draw()

    def _draw(self) -> None:
        plt = self.plt
        plt.clear_figure()
        plt.canvas_color((30, 30, 30))
        plt.axes_color((30, 30, 30))
        plt.ticks_color((128, 128, 128))

        if not self._closes:
            plt.title("Loading price data...")
            self.refresh()
            return

        plt.plot(self._closes, color=(91, 155, 213))
        plt.title(f"{self._ticker} — 3 Month Price")

        # Show ~6 date labels on x-axis
        n = len(self._dates)
        if n > 1:
            step = max(1, n // 6)
            tick_indices = list(range(0, n, step))
            if tick_indices[-1] != n - 1:
                tick_indices.append(n - 1)
            # plotext uses 1-based x for sequential plots
            plt.xticks(
                [i + 1 for i in tick_indices],
                [self._dates[i][5:] for i in tick_indices],
            )

        plt.ylabel("Price")
        self.refresh()


class StockDetail(Static):
    """Panel showing stock key stats and position summary."""

    def set_data(
        self,
        ticker_info: dict,
        shares: float = 0,
        avg_cost: float = 0,
    ) -> None:
        price = ticker_info.get("price", 0)
        currency = ticker_info.get("currency", "")
        value = shares * price
        cost = shares * avg_cost
        pnl = value - cost
        pnl_pct = (pnl / cost * 100) if cost > 0 else 0.0
        pnl_color = "green" if pnl >= 0 else "red"

        # Position
        lines = []
        if shares > 0:
            lines.append("[bold #5b9bd5]Your Position[/]")
            lines.append(
                f"  Shares: [bold]{shares:.2f}[/]    "
                f"Avg Cost: {avg_cost:.2f}    "
                f"Value: [bold]{value:,.2f}[/] {currency}"
            )
            lines.append(
                f"  P&L: [{pnl_color}]{pnl:+,.2f} ({pnl_pct:+.1f}%)[/]"
            )
            lines.append("")

        # Key stats
        lines.append("[bold #5b9bd5]Key Stats[/]")

        def _fmt(val, fmt=".2f", suffix=""):
            if val is None:
                return "N/A"
            return f"{val:{fmt}}{suffix}"

        def _fmt_cap(val):
            if val is None:
                return "N/A"
            if val >= 1e12:
                return f"{val/1e12:.2f}T"
            if val >= 1e9:
                return f"{val/1e9:.2f}B"
            if val >= 1e6:
                return f"{val/1e6:.1f}M"
            return f"{val:,.0f}"

        stats = [
            ("Market Cap", _fmt_cap(ticker_info.get("market_cap"))),
            ("P/E Ratio", _fmt(ticker_info.get("pe_ratio"))),
            ("Forward P/E", _fmt(ticker_info.get("forward_pe"))),
            ("Div Yield", _fmt(ticker_info.get("dividend_yield"), ".2%") if ticker_info.get("dividend_yield") is not None else "N/A"),
            ("52W High", _fmt(ticker_info.get("high_52w"))),
            ("52W Low", _fmt(ticker_info.get("low_52w"))),
            ("Beta", _fmt(ticker_info.get("beta"))),
        ]

        # Two-column layout
        mid = (len(stats) + 1) // 2
        for i in range(mid):
            left = stats[i]
            right = stats[i + mid] if i + mid < len(stats) else None
            line = f"  {left[0]:<14} [bold]{left[1]:>10}[/]"
            if right:
                line += f"     {right[0]:<14} [bold]{right[1]:>10}[/]"
            lines.append(line)

        sector = ticker_info.get("sector")
        industry = ticker_info.get("industry")
        if sector or industry:
            lines.append(f"  {'Sector':<14} [bold]{sector or 'N/A':>10}[/]"
                         f"     {'Industry':<14} [bold]{(industry or 'N/A')[:20]:>10}[/]")

        self.update("\n".join(lines))


class HelpOverlay(ModalScreen):
    """Modal showing keyboard shortcuts."""

    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
        Binding("question_mark", "dismiss", "Close"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="help-dialog"):
            yield Static("Keyboard Shortcuts", id="help-title")
            yield Static(
                "[bold #5b9bd5]Global[/]\n"
                "  q  Quit    r  Refresh    ?  Help",
                classes="help-section",
            )
            yield Static(
                "[bold #5b9bd5]Portfolio View[/]\n"
                "  ↑↓  Navigate    Enter  Drill into ETF\n"
                "  b   Buy         s      Sell\n"
                "  t   Transactions",
                classes="help-section",
            )
            yield Static(
                "[bold #5b9bd5]Drill-Down / History[/]\n"
                "  Esc  Back    ↑↓  Scroll",
                classes="help-section",
            )
            yield Static(
                "[bold #5b9bd5]Transaction Form[/]\n"
                "  Tab/Shift+Tab  Navigate fields\n"
                "  Enter          Confirm    Esc  Cancel",
                classes="help-section",
            )


class TransactionModal(ModalScreen[dict | None]):
    """Modal form for adding a buy/sell transaction."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, txn_type: str = "buy"):
        super().__init__()
        self.txn_type = txn_type

    def compose(self) -> ComposeResult:
        title = f"Add Transaction — {self.txn_type.upper()}"
        with Vertical(id="modal-dialog"):
            yield Static(title, id="modal-title")
            yield Label("Ticker", classes="field-label")
            yield Input(placeholder="e.g. IUIT.L", id="input-ticker")
            yield Label("Shares", classes="field-label")
            yield Input(placeholder="10", id="input-shares", type="number")
            yield Label("Price per share", classes="field-label")
            yield Input(placeholder="45.50", id="input-price", type="number")
            yield Label("Date", classes="field-label")
            yield Input(value=date.today().isoformat(), id="input-date")
            yield Label("Note (optional)", classes="field-label")
            yield Input(placeholder="", id="input-note")
            yield Static("", id="modal-error")
            with Horizontal(id="modal-buttons"):
                yield Button("Confirm", id="btn-confirm", variant="primary")
                yield Button("Cancel", id="btn-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel":
            self.dismiss(None)
        elif event.button.id == "btn-confirm":
            self._submit()

    def _submit(self):
        error_widget = self.query_one("#modal-error", Static)
        ticker = self.query_one("#input-ticker", Input).value.strip().upper()
        shares_str = self.query_one("#input-shares", Input).value.strip()
        price_str = self.query_one("#input-price", Input).value.strip()
        date_str = self.query_one("#input-date", Input).value.strip()
        note = self.query_one("#input-note", Input).value.strip()

        if not ticker:
            error_widget.update("[bold]Ticker is required[/]")
            return
        try:
            shares = float(shares_str)
            if shares <= 0:
                raise ValueError
        except ValueError:
            error_widget.update("[bold]Shares must be a positive number[/]")
            return
        try:
            price = float(price_str)
            if price <= 0:
                raise ValueError
        except ValueError:
            error_widget.update("[bold]Price must be a positive number[/]")
            return
        # Validate date format
        try:
            from datetime import datetime
            datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            error_widget.update("[bold]Date must be YYYY-MM-DD[/]")
            return

        self.dismiss({
            "ticker": ticker,
            "type": self.txn_type,
            "shares": shares,
            "price": price,
            "date": date_str,
            "note": note,
        })

    def action_cancel(self):
        self.dismiss(None)


class ImportModal(ModalScreen[dict | None]):
    """Modal for importing transactions from a broker CSV file."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="import-dialog"):
            yield Static("Import CSV", id="import-title")
            yield Label("File path", classes="field-label")
            yield Input(placeholder="/path/to/portfolio.csv", id="input-filepath")
            yield Static("", id="import-error")
            yield Static("", id="import-result")
            with Horizontal(id="import-buttons"):
                yield Button("Import", id="btn-import", variant="primary")
                yield Button("Cancel", id="btn-import-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-import-cancel":
            self.dismiss(None)
        elif event.button.id == "btn-import":
            self._do_import()

    def _do_import(self):
        from pathlib import Path
        error_widget = self.query_one("#import-error", Static)
        result_widget = self.query_one("#import-result", Static)
        filepath = self.query_one("#input-filepath", Input).value.strip()

        if not filepath:
            error_widget.update("[bold]File path is required[/]")
            return

        path = Path(filepath).expanduser()
        if not path.exists():
            error_widget.update(f"[bold]File not found: {path}[/]")
            return

        if not path.suffix.lower() == ".csv":
            error_widget.update("[bold]File must be a .csv file[/]")
            return

        error_widget.update("")
        from storage import Portfolio
        portfolio: Portfolio = self.app.portfolio  # type: ignore[attr-defined]
        result = portfolio.import_csv(path)

        imported = result["imported"]
        skipped = result["skipped"]
        errors = result["errors"]

        parts = []
        if imported:
            parts.append(f"[#6a9955]{imported} imported[/]")
        if skipped:
            parts.append(f"[#d7ba7d]{skipped} duplicates skipped[/]")
        if errors:
            parts.append(f"[#d16969]{len(errors)} errors[/]")
            error_widget.update(f"[bold]{errors[0]}[/]")

        if parts:
            result_widget.update("  ".join(parts))

        if imported > 0:
            # Auto-dismiss after successful import
            self.dismiss({"imported": imported, "skipped": skipped})
        elif not errors:
            result_widget.update("[#d7ba7d]Nothing new to import[/]")

    def action_cancel(self):
        self.dismiss(None)
