"""Textual UI — widgets, modals, styles for Portfolio Tracker."""

from datetime import date

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import Button, Footer, Input, Label, Static


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
