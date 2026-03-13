"""Textual UI — widgets, modals, styles for Portfolio Tracker."""

from datetime import date

from rich.console import Group
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import Button, DataTable, Footer, Input, Label, Static
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

.portfolio-header {
    height: 3;
    padding: 0 2;
    background: $surface;
    color: $text-primary;
    content-align: left middle;
}

.portfolio-header .label {
    text-style: bold;
    color: $accent;
}

EmptyState {
    width: 1fr;
    height: 1fr;
    content-align: center middle;
    color: $text-secondary;
}

LoadingIndicator {
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

/* Big value display */
.big-value {
    height: 9;
    padding: 0 2;
    content-align: center middle;
    color: $text-primary;
}

/* Price chart inside PortfolioView */
.view-chart {
    height: 15;
    margin: 0 1;
}

.view-loading {
    width: 1fr;
    height: 1fr;
    content-align: center middle;
    color: $text-secondary;
}

.view-empty {
    width: 1fr;
    height: 1fr;
    content-align: center middle;
    color: $text-secondary;
}

/* PortfolioView container */
PortfolioView {
    height: 1fr;
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

/* ETF drill-down row */
#etf-row {
    height: 1fr;
}

#etf-holdings-table {
    width: 1fr;
}

#etf-treemap {
    width: 1fr;
    min-height: 8;
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

/* Allocation screen */
#allocation-header {
    dock: top;
    height: 3;
    padding: 0 2;
    background: $surface;
    color: $text-primary;
    content-align: left middle;
}

#allocation-summary {
    height: 2;
    padding: 0 2;
    color: $text-primary;
}

#alloc-row {
    height: 1fr;
}

#allocation-table {
    width: 1fr;
}

#allocation-treemap {
    width: 1fr;
    min-height: 8;
}

#lookthrough-treemap {
    width: 1fr;
    min-height: 8;
}

#etf-treemap {
    width: 1fr;
    min-height: 8;
}

#lt-row {
    height: 1fr;
}

#lt-left {
    width: 1fr;
}

#lookthrough-title {
    height: 2;
    padding: 0 2;
    color: $accent;
    text-style: bold;
}

#lookthrough-table {
    height: 1fr;
}


/* Tabbed portfolios */
TabbedContent {
    height: 1fr;
}

TabPane {
    height: 1fr;
    padding: 0;
}

Tabs {
    dock: top;
    height: 3;
    background: $surface;
}

Tab {
    color: $text-secondary;
    padding: 0 2;
}

Tab.-active {
    color: $accent;
    text-style: bold;
}

/* Create Portfolio Modal — reuses modal-dialog styles */
CreatePortfolioModal {
    align: center middle;
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
        self._sort_hint = ""

    def update_stats(
        self,
        total_value: float = 0.0,
        total_pnl: float = 0.0,
        total_pnl_pct: float = 0.0,
        last_update: str = "",
        loading: bool = False,
        sort_hint: str = "",
    ):
        self._total = total_value
        self._pnl = total_pnl
        self._pnl_pct = total_pnl_pct
        self._last_update = last_update
        self._loading = loading
        self._sort_hint = sort_hint
        self._render_content()

    def _render_content(self):
        if self._loading and not self._last_update:
            # First load — no data yet, show minimal header
            self.update("[bold #5b9bd5]PORTFOLIO TRACKER[/]    [dim]Loading...[/]")
            return
        pnl_color = "green" if self._pnl >= 0 else "red"
        status = "Refreshing..." if self._loading else f"Last update: {self._last_update}"
        sort_part = f"  Sort: {self._sort_hint}" if self._sort_hint else ""
        self.update(
            f"[bold #5b9bd5]PORTFOLIO TRACKER[/]    "
            f"Total: [bold]{self._total:,.2f}[/]  "
            f"P&L: [{pnl_color}]{self._pnl:+,.2f} ({self._pnl_pct:+.1f}%)[/]"
            f"    [dim]{status}{sort_part}[/]"
        )


class EmptyState(Static):
    """Centered message for empty states."""
    pass


class LoadingIndicator(Static):
    """Centered loading message shown while fetching data."""
    pass


# 5-line tall ASCII digits
_DIGITS = {
    "0": ["  ██████  ", " ██    ██ ", " ██    ██ ", " ██    ██ ", "  ██████  "],
    "1": ["    ██    ", "  ████    ", "    ██    ", "    ██    ", "  ██████  "],
    "2": ["  ██████  ", " ██    ██ ", "     ██   ", "   ██     ", " ████████ "],
    "3": ["  ██████  ", "       ██ ", "   █████  ", "       ██ ", "  ██████  "],
    "4": [" ██    ██ ", " ██    ██ ", " ████████ ", "       ██ ", "       ██ "],
    "5": [" ████████ ", " ██       ", " ███████  ", "       ██ ", " ███████  "],
    "6": ["  ██████  ", " ██       ", " ███████  ", " ██    ██ ", "  ██████  "],
    "7": [" ████████ ", "      ██  ", "     ██   ", "    ██    ", "    ██    "],
    "8": ["  ██████  ", " ██    ██ ", "  ██████  ", " ██    ██ ", "  ██████  "],
    "9": ["  ██████  ", " ██    ██ ", "  ███████ ", "       ██ ", "  ██████  "],
    ",": ["          ", "          ", "          ", "    ██    ", "   ██     "],
    ".": ["          ", "          ", "          ", "          ", "    ██    "],
    " ": ["     ", "     ", "     ", "     ", "     "],
}


_CURRENCY_SYMBOLS = {
    "USD": "$", "GBP": "£", "EUR": "€", "CHF": "CHF ", "JPY": "¥",
}


class BigValue(Static):
    """Large ASCII art number display for portfolio total."""

    def set_value(
        self,
        value: float,
        currency: str = "USD",
        pnl_pct: float = 0.0,
        day_pct: float = 0.0,
        three_month_pct: float = 0.0,
    ) -> None:
        formatted = f"{value:,.0f}"
        lines = [""] * 5
        for ch in formatted:
            glyph = _DIGITS.get(ch, _DIGITS[" "])
            for i in range(5):
                lines[i] += glyph[i]

        symbol = _CURRENCY_SYMBOLS.get(currency, currency + " ")

        def _color(v: float) -> str:
            return "green" if v >= 0 else "red"

        stats = (
            f"  Total P&L: [{_color(pnl_pct)}]{pnl_pct:+.1f}%[/]"
            f"    Today: [{_color(day_pct)}]{day_pct:+.2f}%[/]"
            f"    3M: [{_color(three_month_pct)}]{three_month_pct:+.1f}%[/]"
        )

        ascii_block = "\n".join(lines)
        value_color = "green" if day_pct >= 0 else "#e07070"
        self.update(f"[dim]{symbol}[/]\n[bold {value_color}]{ascii_block}[/]\n{stats}")


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


def _treemap_bg(change_pct: float) -> str:
    """Map daily change % to a background color string for Rich."""
    intensity = min(abs(change_pct) / 3.0, 1.0)
    if change_pct >= 0:
        r = int(30 + (10 - 30) * intensity)
        g = int(60 + (160 - 60) * intensity)
        b = int(30 + (10 - 30) * intensity)
    else:
        r = int(60 + (180 - 60) * intensity)
        g = int(30 + (10 - 30) * intensity)
        b = int(30 + (10 - 30) * intensity)
    return f"rgb({r},{g},{b})"


class Treemap(Widget):
    """Terminal treemap — tiles sized by weight, colored by daily change."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._items: list[dict] = []

    def set_data(self, items: list[dict]) -> None:
        """Set treemap data. Each item: {label, weight, change_pct}."""
        self._items = sorted(items, key=lambda x: x["weight"], reverse=True)
        self.refresh()

    def render(self):
        w = self.size.width
        h = self.size.height
        if not self._items or w <= 0 or h <= 0:
            return Text("")

        values = [(item["weight"], i) for i, item in enumerate(self._items) if item["weight"] > 0]
        if not values:
            return Text("")

        rects = _squarify(values, 0, 0, w, h)

        # Build grid: cell -> item index
        grid = [[-1] * w for _ in range(h)]
        for rx, ry, rw, rh, idx in rects:
            x0, y0 = int(round(rx)), int(round(ry))
            x1, y1 = int(round(rx + rw)), int(round(ry + rh))
            x1 = min(x1, w)
            y1 = min(y1, h)
            for cy in range(y0, y1):
                for cx in range(x0, x1):
                    grid[cy][cx] = idx

        # Find bounding box per tile for label placement
        tile_bounds: dict[int, list[int]] = {}
        for ry in range(h):
            for rx in range(w):
                idx = grid[ry][rx]
                if idx >= 0:
                    if idx not in tile_bounds:
                        tile_bounds[idx] = [rx, ry, rx, ry]
                    else:
                        b = tile_bounds[idx]
                        if rx > b[2]:
                            b[2] = rx
                        if ry > b[3]:
                            b[3] = ry

        # Prepare label lines per tile: list of (row, start_x, text)
        tile_labels: dict[int, list[tuple[int, int, str]]] = {}
        for idx, (x0, y0, x2, y2) in tile_bounds.items():
            item = self._items[idx]
            tw = x2 - x0 + 1
            th = y2 - y0 + 1
            mid_y = (y0 + y2) // 2
            label_lines: list[tuple[int, int, str]] = []

            if tw >= 4:
                label = item["label"][: tw - 2]
                sx = x0 + (tw - len(label)) // 2
                row = mid_y if th >= 2 else y0
                label_lines.append((row, sx, label))

            if tw >= 6 and th >= 3:
                pct = f"{item.get('change_pct', 0):+.1f}%"[: tw - 2]
                sx = x0 + (tw - len(pct)) // 2
                label_lines.append((mid_y + 1, sx, pct))

            tile_labels[idx] = label_lines

        # Render each row as a Rich Text line
        lines: list[Text] = []
        for ry in range(h):
            line = Text()
            rx = 0
            while rx < w:
                idx = grid[ry][rx]
                end = rx + 1
                while end < w and grid[ry][end] == idx:
                    end += 1

                if idx >= 0:
                    bg = _treemap_bg(self._items[idx].get("change_pct", 0))
                    chars = list(" " * (end - rx))
                    for lrow, lsx, ltxt in tile_labels.get(idx, []):
                        if ry == lrow:
                            for ci, ch in enumerate(ltxt):
                                pos = lsx + ci - rx
                                if 0 <= pos < len(chars):
                                    chars[pos] = ch
                    # Border: darken the rightmost column of each tile
                    if end < w and grid[ry][end] != idx and len(chars) > 0:
                        chars[-1] = "│"
                    line.append("".join(chars), style=f"bold white on {bg}")
                else:
                    line.append(" " * (end - rx))

                rx = end
            lines.append(line)

        return Group(*lines)


def _squarify(values, x, y, w, h):
    """Squarified treemap layout. Returns list of (x, y, w, h, index)."""
    if not values:
        return []
    total = sum(v for v, _ in values)
    if total <= 0:
        return []
    rects: list[tuple] = []
    _layout_strip(values, x, y, w, h, total, rects)
    return rects


def _layout_strip(values, x, y, w, h, total, rects):
    if not values or total <= 0:
        return
    if len(values) == 1:
        rects.append((x, y, w, h, values[0][1]))
        return

    horizontal = w >= h
    best_split = 1
    best_ratio = float("inf")
    running = 0

    for i in range(len(values)):
        running += values[i][0]
        frac = running / total
        if horizontal:
            strip_w = w * frac
            if strip_w <= 0:
                continue
            worst = 0
            for j in range(i + 1):
                item_h = h * (values[j][0] / running) if running > 0 else 0
                if item_h > 0 and strip_w > 0:
                    ratio = max(strip_w / item_h, item_h / strip_w)
                    worst = max(worst, ratio)
            if worst < best_ratio:
                best_ratio = worst
                best_split = i + 1
            elif worst > best_ratio * 1.5 and i > 0:
                break
        else:
            strip_h = h * frac
            if strip_h <= 0:
                continue
            worst = 0
            for j in range(i + 1):
                item_w = w * (values[j][0] / running) if running > 0 else 0
                if item_w > 0 and strip_h > 0:
                    ratio = max(strip_h / item_w, item_w / strip_h)
                    worst = max(worst, ratio)
            if worst < best_ratio:
                best_ratio = worst
                best_split = i + 1
            elif worst > best_ratio * 1.5 and i > 0:
                break

    strip = values[:best_split]
    rest = values[best_split:]
    strip_total = sum(v for v, _ in strip)
    strip_frac = strip_total / total if total > 0 else 0

    if horizontal:
        strip_w = w * strip_frac
        cy = y
        for val, idx in strip:
            item_h = h * (val / strip_total) if strip_total > 0 else 0
            rects.append((x, cy, strip_w, item_h, idx))
            cy += item_h
        if rest:
            _layout_strip(rest, x + strip_w, y, w - strip_w, h, total - strip_total, rects)
    else:
        strip_h = h * strip_frac
        cx = x
        for val, idx in strip:
            item_w = w * (val / strip_total) if strip_total > 0 else 0
            rects.append((cx, y, item_w, strip_h, idx))
            cx += item_w
        if rest:
            _layout_strip(rest, x, y + strip_h, w, h - strip_h, total - strip_total, rects)


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


class NewsSidebar(Widget, can_focus=True):
    """Sidebar showing portfolio-aware financial news."""

    DEFAULT_CSS = """
    NewsSidebar {
        dock: right;
        width: 45;
        height: 1fr;
        background: #2a2a2a;
        border-left: solid #444;
        padding: 0 1;
        overflow-y: auto;
    }
    NewsSidebar:focus {
        border-left: solid #5b9bd5;
    }
    """

    BINDINGS = [
        Binding("up", "cursor_up", "Up", show=False),
        Binding("down", "cursor_down", "Down", show=False),
        Binding("enter", "open_article", "Open", show=False),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._items: list = []  # list of NewsItem
        self._selected = 0

    def set_items(self, items: list) -> None:
        self._items = items
        self._selected = min(self._selected, max(0, len(items) - 1))
        self.refresh()

    def render(self):
        focused = self.has_focus

        if not self._items:
            return Text("[dim]No news available. Press R to refresh.[/]")

        lines: list[Text] = []
        lines.append(Text(""))
        title_style = "bold #5b9bd5" if focused else "bold #808080"
        lines.append(Text(" NEWS FEED", style=title_style))
        lines.append(Text(" ─" * 20, style="#444"))
        lines.append(Text(""))

        for i, item in enumerate(self._items):
            is_selected = i == self._selected and focused
            prefix = "▸ " if is_selected else "  "

            # Ticker tag
            ticker_tag = Text(f"[{item.ticker}]", style="bold #5b9bd5")

            # Title (truncate to fit)
            max_title = 38
            title = item.title[:max_title]
            if len(item.title) > max_title:
                title += "…"

            if is_selected:
                title_style = "bold white"
            else:
                title_style = "#d4d4d4"

            line1 = Text(prefix)
            line1.append_text(ticker_tag)
            lines.append(line1)

            line2 = Text(f"  {title}", style=title_style)
            lines.append(line2)

            meta = f"  {item.published}"
            if item.source:
                meta += f" · {item.source[:20]}"
            lines.append(Text(meta, style="#808080"))
            lines.append(Text(""))

        hint = " ↑↓ Navigate  Enter Open  Tab Back  N Hide" if focused else " Tab to focus  N Hide"
        lines.append(Text(hint, style="dim"))
        return Group(*lines)

    def action_cursor_up(self) -> None:
        if self._items and self._selected > 0:
            self._selected -= 1
            self.refresh()

    def action_cursor_down(self) -> None:
        if self._items and self._selected < len(self._items) - 1:
            self._selected += 1
            self.refresh()

    def action_open_article(self) -> None:
        if self._items and 0 <= self._selected < len(self._items):
            from news import open_article
            open_article(self._items[self._selected].url)

    def on_focus(self) -> None:
        self.refresh()

    def on_blur(self) -> None:
        self.refresh()


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
                "  t   Transactions a  Allocation\n"
                "  o   Sort        c  Currency\n"
                "  i   Import CSV  p  New Portfolio\n"
                "  n   News feed   d  Delete portfolio\n"
                "  1-9 Switch portfolio tabs",
                classes="help-section",
            )
            yield Static(
                "[bold #5b9bd5]Drill-Down / History[/]\n"
                "  Esc  Back    ↑↓  Scroll\n"
                "  d    Delete transaction (History)",
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

    def __init__(self, txn_type: str = "buy", portfolio_name: str = ""):
        super().__init__()
        self.txn_type = txn_type
        self.portfolio_name = portfolio_name

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
            yield Label("Portfolio", classes="field-label")
            yield Input(value=self.portfolio_name, id="input-portfolio", placeholder="(leave empty for untagged)")
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

        portfolio = self.query_one("#input-portfolio", Input).value.strip()

        self.dismiss({
            "ticker": ticker,
            "type": self.txn_type,
            "shares": shares,
            "price": price,
            "date": date_str,
            "note": note,
            "portfolio": portfolio,
        })

    def action_cancel(self):
        self.dismiss(None)


class ImportModal(ModalScreen[dict | None]):
    """Modal for importing transactions from a broker CSV file."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, portfolio_name: str = ""):
        super().__init__()
        self.portfolio_name = portfolio_name

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
        result = portfolio.import_csv(path, portfolio_name=self.portfolio_name)

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


class ConfirmModal(ModalScreen[bool]):
    """Yes/No confirmation dialog."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("y", "confirm", "Yes"),
        Binding("n", "cancel", "No"),
    ]

    def __init__(self, message: str):
        super().__init__()
        self._message = message

    def compose(self) -> ComposeResult:
        with Vertical(id="modal-dialog"):
            yield Static("Confirm", id="modal-title")
            yield Static(self._message, classes="field-label")
            with Horizontal(id="modal-buttons"):
                yield Button("Yes", id="btn-confirm", variant="primary")
                yield Button("No", id="btn-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-confirm":
            self.dismiss(True)
        else:
            self.dismiss(False)

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)


class CreatePortfolioModal(ModalScreen[str | None]):
    """Modal for creating a new named portfolio."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="modal-dialog"):
            yield Static("Create Portfolio", id="modal-title")
            yield Label("Portfolio name", classes="field-label")
            yield Input(placeholder="e.g. Retirement", id="input-name")
            yield Static("", id="modal-error")
            with Horizontal(id="modal-buttons"):
                yield Button("Create", id="btn-confirm", variant="primary")
                yield Button("Cancel", id="btn-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel":
            self.dismiss(None)
        elif event.button.id == "btn-confirm":
            self._submit()

    def _submit(self):
        name = self.query_one("#input-name", Input).value.strip()
        if not name:
            self.query_one("#modal-error", Static).update("[bold]Name is required[/]")
            return
        self.dismiss(name)

    def action_cancel(self):
        self.dismiss(None)


class MoveToPortfolioModal(ModalScreen[str | None]):
    """Modal for selecting a target portfolio to move a transaction to."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, portfolios: list[str], current_portfolio: str = ""):
        super().__init__()
        self._portfolios = portfolios
        self._current = current_portfolio

    def compose(self) -> ComposeResult:
        with Vertical(id="modal-dialog"):
            yield Static("Move to Portfolio", id="modal-title")
            yield Static(
                f"Current: [bold]{self._current or '(untagged)'}[/]",
                classes="field-label",
            )
            yield DataTable(id="move-table", cursor_type="row")
            with Horizontal(id="modal-buttons"):
                yield Button("Cancel", id="btn-cancel")

    def on_mount(self) -> None:
        table = self.query_one("#move-table", DataTable)
        table.add_columns("#", "Portfolio")
        table.add_row("0", "(untagged)")
        for i, name in enumerate(self._portfolios, 1):
            label = f"{name}  ← current" if name == self._current else name
            table.add_row(str(i), label)

    def on_data_table_row_selected(self, event) -> None:
        row_idx = event.cursor_row
        if row_idx == 0:
            self.dismiss("")
        elif 1 <= row_idx <= len(self._portfolios):
            self.dismiss(self._portfolios[row_idx - 1])

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(None)

    def action_cancel(self):
        self.dismiss(None)
