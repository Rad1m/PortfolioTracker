"""Custom PySide6 widgets for Portfolio Tracker."""

from datetime import datetime

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QLinearGradient
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

# Colors matching TUI theme
C_BG = "#1e1e1e"
C_SURFACE = "#2a2a2a"
C_ACCENT = "#5b9bd5"
C_POSITIVE = "#6a9955"
C_NEGATIVE = "#d16969"
C_TEXT = "#d4d4d4"
C_TEXT_DIM = "#808080"
C_SELECTION = "#2a4a6b"

SORT_MODES = ["ticker", "value", "pnl_pct_desc", "pnl_pct_asc"]
SORT_LABELS = {
    "ticker": "Ticker A→Z",
    "value": "Value ↓",
    "pnl_pct_desc": "P&L% ↓",
    "pnl_pct_asc": "P&L% ↑",
}
CURRENCIES = ["USD", "GBP", "EUR", "CHF", "JPY"]
CURRENCY_SYMBOLS = {
    "USD": "$", "GBP": "£", "EUR": "€", "CHF": "CHF ", "JPY": "¥",
}


def _pnl_color(value: float) -> str:
    return C_POSITIVE if value >= 0 else C_NEGATIVE


def _right_aligned_item(text: str, color: str | None = None) -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
    if color:
        item.setForeground(QColor(color))
    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
    return item


def _left_aligned_item(text: str, color: str | None = None) -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    if color:
        item.setForeground(QColor(color))
    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
    return item


class HeaderBar(QFrame):
    """Top bar showing portfolio total, P&L, update time, and sort mode."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(40)
        self.setStyleSheet(f"background: {C_SURFACE}; padding: 0 12px;")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)

        self._title = QLabel("PORTFOLIO TRACKER")
        self._title.setStyleSheet(f"color: {C_ACCENT}; font-weight: bold; font-size: 14px;")
        layout.addWidget(self._title)

        self._stats = QLabel("")
        self._stats.setStyleSheet(f"color: {C_TEXT}; font-size: 13px;")
        layout.addWidget(self._stats)

        layout.addStretch()

        self._status = QLabel("Loading...")
        self._status.setStyleSheet(f"color: {C_TEXT_DIM}; font-size: 12px;")
        layout.addWidget(self._status)

    def update_stats(self, total=0.0, pnl=0.0, pnl_pct=0.0, sort_hint="", loading=False):
        if loading and total == 0:
            self._stats.setText("")
            self._status.setText("Loading...")
            return

        pnl_col = _pnl_color(pnl)
        self._stats.setText(
            f"Total: {total:,.2f}   "
            f'<span style="color:{pnl_col}">P&L: {pnl:+,.2f} ({pnl_pct:+.1f}%)</span>'
        )
        self._stats.setTextFormat(Qt.RichText)

        if loading:
            self._status.setText("Refreshing...")
        else:
            now = datetime.now().strftime("%H:%M")
            sort_part = f"  Sort: {sort_hint}" if sort_hint else ""
            self._status.setText(f"Last update: {now}{sort_part}")


class BigValueWidget(QFrame):
    """Large-font portfolio total with P&L / Today / 3M percentages."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(90)
        self.setStyleSheet(f"background: {C_BG};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 8, 20, 8)
        layout.setSpacing(4)

        self._value_label = QLabel("")
        self._value_label.setStyleSheet(f"color: {C_TEXT}; font-size: 48px; font-weight: bold;")
        self._value_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._value_label)

        self._stats_label = QLabel("")
        self._stats_label.setAlignment(Qt.AlignCenter)
        self._stats_label.setTextFormat(Qt.RichText)
        self._stats_label.setStyleSheet("font-size: 14px;")
        layout.addWidget(self._stats_label)

    def set_value(self, value, currency="USD", pnl_pct=0.0, day_pct=0.0, three_month_pct=0.0):
        symbol = CURRENCY_SYMBOLS.get(currency, currency + " ")
        color = _pnl_color(day_pct)
        self._value_label.setStyleSheet(f"color: {color}; font-size: 48px; font-weight: bold;")
        self._value_label.setText(f"{symbol}{value:,.0f}")

        def _span(label, v, fmt="+.1f"):
            col = _pnl_color(v)
            return f'{label}: <span style="color:{col}">{v:{fmt}}%</span>'

        self._stats_label.setText(
            f"{_span('Total P&L', pnl_pct)}    "
            f"{_span('Today', day_pct, '+.2f')}    "
            f"{_span('3M', three_month_pct)}"
        )


class PriceChartWidget(pg.PlotWidget):
    """Bloomberg-style interactive price chart with area fill and crosshair."""

    def __init__(self, parent=None):
        super().__init__(parent, background="#000000")
        self.setMinimumHeight(200)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Grid: subtle dashed grey lines
        self.showGrid(x=True, y=True, alpha=0.2)
        self.getPlotItem().getAxis("bottom").setGrid(100)
        self.getPlotItem().getAxis("left").setGrid(100)
        grid_pen = pg.mkPen("#444444", width=1, style=Qt.DashLine)
        for axis_name in ("bottom", "left"):
            ax = self.getAxis(axis_name)
            ax.setPen(pg.mkPen("#555555"))
            ax.setTextPen(pg.mkPen("#aaaaaa"))
            ax.setTickFont(QFont("Menlo", 9))

        # Show price axis on the right
        self.showAxis("right")
        self.getAxis("right").setPen(pg.mkPen("#555555"))
        self.getAxis("right").setTextPen(pg.mkPen("#aaaaaa"))
        self.getAxis("right").setTickFont(QFont("Menlo", 9))
        self.getAxis("right").setWidth(60)

        self._dates = []
        self._closes = []

        # Crosshair — yellow like Bloomberg
        self._vline = pg.InfiniteLine(angle=90, pen=pg.mkPen("#ffcc00", width=1, style=Qt.DashLine))
        self._hline = pg.InfiniteLine(angle=0, pen=pg.mkPen("#ffcc00", width=1, style=Qt.DashLine))
        self.addItem(self._vline, ignoreBounds=True)
        self.addItem(self._hline, ignoreBounds=True)
        self._vline.setVisible(False)
        self._hline.setVisible(False)

        # Tooltip with black background
        self._tooltip = pg.TextItem(color="#ffffff", anchor=(0, 1), fill=pg.mkBrush("#000000cc"))
        self._tooltip.setFont(QFont("Menlo", 10))
        self.addItem(self._tooltip, ignoreBounds=True)
        self._tooltip.setVisible(False)

        # Last price label on right edge
        self._price_label = pg.TextItem(color="#ffffff", anchor=(0, 0.5), fill=pg.mkBrush("#e8c96a"))
        self._price_label.setFont(QFont("Menlo", 9))
        self.addItem(self._price_label, ignoreBounds=True)
        self._price_label.setVisible(False)

        self.scene().sigMouseMoved.connect(self._on_mouse_moved)

    def set_data(self, title, dates, closes):
        self._dates = dates
        self._closes = closes
        self.clear()
        # Re-add overlay items after clear
        self.addItem(self._vline, ignoreBounds=True)
        self.addItem(self._hline, ignoreBounds=True)
        self.addItem(self._tooltip, ignoreBounds=True)
        self.addItem(self._price_label, ignoreBounds=True)

        if not closes:
            self.setTitle(f"{title} — No data", color="#888888")
            self._price_label.setVisible(False)
            return

        self.setTitle(f"{title} — 3 Month Price", color="#ffffff", size="11pt")
        x = np.arange(len(closes))
        y = np.array(closes, dtype=float)

        # Area fill under the line — subtle gradient
        fill = pg.FillBetweenItem(
            pg.PlotDataItem(x, y),
            pg.PlotDataItem(x, np.full_like(y, y.min())),
            brush=pg.mkBrush(91, 155, 213, 50),
        )
        self.addItem(fill)

        # Main price line — white
        self.plot(x, y, pen=pg.mkPen("#ffffff", width=1.5))

        # Last price label
        last_price = closes[-1]
        self._price_label.setText(f" {last_price:,.2f} ")
        self._price_label.setPos(len(closes) - 1, last_price)
        self._price_label.setVisible(True)

        # X-axis date labels
        n = len(dates)
        if n > 1:
            step = max(1, n // 6)
            ticks = [(i, dates[i][5:]) for i in range(0, n, step)]
            if ticks[-1][0] != n - 1:
                ticks.append((n - 1, dates[-1][5:]))
            self.getAxis("bottom").setTicks([ticks])

    def _on_mouse_moved(self, pos):
        if not self._closes:
            return
        vb = self.getViewBox()
        mouse_point = vb.mapSceneToView(pos)
        x = int(round(mouse_point.x()))
        if 0 <= x < len(self._closes):
            self._vline.setPos(x)
            self._hline.setPos(self._closes[x])
            self._vline.setVisible(True)
            self._hline.setVisible(True)
            self._tooltip.setText(f"  {self._dates[x]}  {self._closes[x]:,.2f}  ")
            self._tooltip.setPos(x, self._closes[x])
            self._tooltip.setVisible(True)
        else:
            self._vline.setVisible(False)
            self._hline.setVisible(False)
            self._tooltip.setVisible(False)


class HoldingsPanel(QWidget):
    """Table of holdings for one portfolio tab, with associated data worker."""

    row_activated = Signal(str, str)  # ticker, name

    COLUMNS = ["Ticker", "Name", "Shares", "Avg Cost", "Price", "Value", "P&L", "P&L %", "Alloc %"]

    def __init__(self, portfolio_name: str | None = None, parent=None):
        super().__init__(parent)
        self.portfolio_name = portfolio_name
        self._rows = []
        self._tickers = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._loading_label = QLabel("Fetching market data, please wait...")
        self._loading_label.setAlignment(Qt.AlignCenter)
        self._loading_label.setStyleSheet(f"color: {C_TEXT_DIM}; font-size: 14px; padding: 40px;")
        layout.addWidget(self._loading_label)

        self._empty_label = QLabel("No holdings yet. Press B to add your first transaction.")
        self._empty_label.setAlignment(Qt.AlignCenter)
        self._empty_label.setStyleSheet(f"color: {C_TEXT_DIM}; font-size: 14px; padding: 40px;")
        self._empty_label.setVisible(False)
        layout.addWidget(self._empty_label)

        self._table = QTableWidget()
        self._table.setColumnCount(len(self.COLUMNS))
        self._table.setHorizontalHeaderLabels(self.COLUMNS)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setSelectionMode(QTableWidget.SingleSelection)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setVisible(False)
        self._table.cellDoubleClicked.connect(self._on_row_activated)
        layout.addWidget(self._table)

    def _on_row_activated(self, row, _col):
        if 0 <= row < len(self._tickers):
            ticker = self._tickers[row]
            name = ""
            for r in self._rows:
                if r["ticker"] == ticker:
                    name = r["name"]
                    break
            self.row_activated.emit(ticker, name)

    def activate_selected_row(self):
        """Activate (drill-down) the currently selected row."""
        rows = self._table.selectionModel().selectedRows()
        if rows:
            row = rows[0].row()
            self._on_row_activated(row, 0)

    def get_selected_ticker(self) -> str | None:
        rows = self._table.selectionModel().selectedRows()
        if rows:
            row = rows[0].row()
            if 0 <= row < len(self._tickers):
                return self._tickers[row]
        return None

    def update_data(self, data: dict):
        """Update table from worker result dict."""
        if data.get("empty"):
            self._loading_label.setVisible(False)
            self._empty_label.setVisible(True)
            self._table.setVisible(False)
            return

        self._rows = data["rows"]
        self._render_table(data.get("sort_mode", "ticker"))

    def _render_table(self, sort_mode: str):
        self._loading_label.setVisible(False)
        self._empty_label.setVisible(False)
        self._table.setVisible(True)

        rows = self._sorted_rows(sort_mode)
        self._tickers = [r["ticker"] for r in rows]
        total_value = sum(r["value"] for r in rows)

        self._table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            alloc_pct = (r["value"] / total_value * 100) if total_value > 0 else 0.0
            pnl_col = _pnl_color(r["pnl"])

            self._table.setItem(i, 0, _left_aligned_item(r["ticker"]))
            self._table.setItem(i, 1, _left_aligned_item(r["name"][:25]))
            self._table.setItem(i, 2, _right_aligned_item(f"{r['shares']:.2f}"))
            self._table.setItem(i, 3, _right_aligned_item(f"{r['avg']:.2f}"))
            self._table.setItem(i, 4, _right_aligned_item(f"{r['price']:.2f}"))
            self._table.setItem(i, 5, _right_aligned_item(f"{r['value']:,.2f}"))
            self._table.setItem(i, 6, _right_aligned_item(f"{r['pnl']:+,.2f}", pnl_col))
            self._table.setItem(i, 7, _right_aligned_item(f"{r['pnl_pct']:+.1f}%", pnl_col))
            self._table.setItem(i, 8, _right_aligned_item(f"{alloc_pct:.1f}%"))

        # Auto-resize columns
        header = self._table.horizontalHeader()
        for col in range(len(self.COLUMNS) - 1):
            header.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(len(self.COLUMNS) - 1, QHeaderView.Stretch)

    def _sorted_rows(self, mode: str) -> list[dict]:
        rows = list(self._rows)
        if mode == "ticker":
            rows.sort(key=lambda r: r["ticker"])
        elif mode == "value":
            rows.sort(key=lambda r: r["value"], reverse=True)
        elif mode == "pnl_pct_desc":
            rows.sort(key=lambda r: r["pnl_pct"], reverse=True)
        elif mode == "pnl_pct_asc":
            rows.sort(key=lambda r: r["pnl_pct"])
        return rows

    def re_render(self, sort_mode: str):
        """Re-render existing data with a new sort mode."""
        if self._rows:
            self._render_table(sort_mode)


class StockDetailWidget(QFrame):
    """Panel showing stock key stats and position summary."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background: {C_SURFACE}; padding: 12px; margin: 4px;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)

        self._content = QLabel("")
        self._content.setStyleSheet(f"color: {C_TEXT}; font-size: 13px;")
        self._content.setTextFormat(Qt.RichText)
        self._content.setWordWrap(True)
        layout.addWidget(self._content)

    def set_data(self, ticker_info, shares=0, avg_cost=0):
        price = ticker_info.get("price", 0)
        currency = ticker_info.get("currency", "")
        value = shares * price
        cost = shares * avg_cost
        pnl = value - cost
        pnl_pct = (pnl / cost * 100) if cost > 0 else 0.0
        pnl_col = _pnl_color(pnl)

        lines = []
        if shares > 0:
            lines.append(f'<b style="color:{C_ACCENT}">Your Position</b>')
            lines.append(
                f"  Shares: <b>{shares:.2f}</b>    "
                f"Avg Cost: {avg_cost:.2f}    "
                f"Value: <b>{value:,.2f}</b> {currency}"
            )
            lines.append(f'  P&L: <span style="color:{pnl_col}">{pnl:+,.2f} ({pnl_pct:+.1f}%)</span>')
            lines.append("")

        lines.append(f'<b style="color:{C_ACCENT}">Key Stats</b>')

        def _fmt(val, fmt=".2f"):
            return f"{val:{fmt}}" if val is not None else "N/A"

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
            ("Div Yield", f"{ticker_info['dividend_yield']:.2%}" if ticker_info.get("dividend_yield") is not None else "N/A"),
            ("52W High", _fmt(ticker_info.get("high_52w"))),
            ("52W Low", _fmt(ticker_info.get("low_52w"))),
            ("Beta", _fmt(ticker_info.get("beta"))),
        ]

        mid = (len(stats) + 1) // 2
        for i in range(mid):
            left = stats[i]
            right = stats[i + mid] if i + mid < len(stats) else None
            line = f"  {left[0]:<14} <b>{left[1]:>10}</b>"
            if right:
                line += f"     {right[0]:<14} <b>{right[1]:>10}</b>"
            lines.append(line)

        sector = ticker_info.get("sector")
        industry = ticker_info.get("industry")
        if sector or industry:
            lines.append(
                f"  {'Sector':<14} <b>{sector or 'N/A':>10}</b>"
                f"     {'Industry':<14} <b>{(industry or 'N/A')[:20]:>10}</b>"
            )

        self._content.setText("<pre>" + "\n".join(lines) + "</pre>")


class NewsPanelWidget(QFrame):
    """Sidebar panel showing portfolio-aware financial news."""

    article_clicked = Signal(str)  # url

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background: {C_SURFACE}; border-left: 1px solid #444;")
        self.setFixedWidth(320)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(0)

        title = QLabel("NEWS FEED")
        title.setStyleSheet(f"color: {C_ACCENT}; font-weight: bold; font-size: 13px; padding-bottom: 8px;")
        layout.addWidget(title)

        from PySide6.QtWidgets import QListWidget, QListWidgetItem
        self._list = QListWidget()
        self._list.setStyleSheet(f"""
            QListWidget {{
                background: {C_SURFACE};
                border: none;
                color: {C_TEXT};
                font-size: 12px;
            }}
            QListWidget::item {{
                padding: 8px 4px;
                border-bottom: 1px solid #333;
            }}
            QListWidget::item:selected {{
                background: {C_SELECTION};
            }}
            QListWidget::item:hover {{
                background: #333;
            }}
        """)
        self._list.itemDoubleClicked.connect(self._on_item_clicked)
        layout.addWidget(self._list)

        hint = QLabel("Double-click to open in browser")
        hint.setStyleSheet(f"color: {C_TEXT_DIM}; font-size: 11px; padding-top: 4px;")
        hint.setAlignment(Qt.AlignCenter)
        layout.addWidget(hint)

        self._items = []  # list of NewsItem

    def set_items(self, items):
        from PySide6.QtWidgets import QListWidgetItem
        self._items = items
        self._list.clear()
        for item in items:
            text = f"[{item.ticker}]  {item.title}\n{item.published}"
            if item.source:
                text += f" · {item.source}"
            list_item = QListWidgetItem(text)
            list_item.setData(Qt.UserRole, item.url)
            self._list.addItem(list_item)

    def _on_item_clicked(self, item):
        url = item.data(Qt.UserRole)
        if url:
            from news import open_article
            open_article(url)


class TreemapWidget(QWidget):
    """Treemap (tiles chart) sized by weight, colored red/green by daily change."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items = []  # list of {"label": str, "weight": float, "change_pct": float}
        self.setMinimumHeight(150)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_data(self, items: list[dict]):
        """Set treemap data. Each item: {label, weight, change_pct}."""
        self._items = sorted(items, key=lambda x: x["weight"], reverse=True)
        self.update()

    @staticmethod
    def _squarify(values, x, y, w, h):
        """Squarified treemap layout. Returns list of (x, y, w, h, index)."""
        if not values:
            return []

        total = sum(v for v, _ in values)
        if total <= 0:
            return []

        rects = []
        TreemapWidget._layout_strip(values, x, y, w, h, total, rects)
        return rects

    @staticmethod
    def _layout_strip(values, x, y, w, h, total, rects):
        if not values or total <= 0:
            return

        if len(values) == 1:
            rects.append((x, y, w, h, values[0][1]))
            return

        # Decide split direction: horizontal if wider, vertical if taller
        horizontal = w >= h

        # Find best split point using squarify heuristic
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
                # Worst aspect ratio in this strip
                worst = 0
                strip_running = 0
                for j in range(i + 1):
                    strip_running += values[j][0]
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
                strip_running = 0
                for j in range(i + 1):
                    strip_running += values[j][0]
                    item_w = w * (values[j][0] / running) if running > 0 else 0
                    if item_w > 0 and strip_h > 0:
                        ratio = max(strip_h / item_w, item_w / strip_h)
                        worst = max(worst, ratio)
                if worst < best_ratio:
                    best_ratio = worst
                    best_split = i + 1
                elif worst > best_ratio * 1.5 and i > 0:
                    break

        # Layout the strip
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
                remaining_total = total - strip_total
                TreemapWidget._layout_strip(rest, x + strip_w, y, w - strip_w, h, remaining_total, rects)
        else:
            strip_h = h * strip_frac
            cx = x
            for val, idx in strip:
                item_w = w * (val / strip_total) if strip_total > 0 else 0
                rects.append((cx, y, item_w, strip_h, idx))
                cx += item_w
            if rest:
                remaining_total = total - strip_total
                TreemapWidget._layout_strip(rest, x, y + strip_h, w, h - strip_h, remaining_total, rects)

    def paintEvent(self, event):
        from PySide6.QtGui import QPainter, QPen

        if not self._items:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)

        w = self.width()
        h = self.height()

        values = [(item["weight"], i) for i, item in enumerate(self._items) if item["weight"] > 0]
        rects = self._squarify(values, 0, 0, w, h)

        for rx, ry, rw, rh, idx in rects:
            if rw < 1 or rh < 1:
                continue

            item = self._items[idx]
            change = item.get("change_pct", 0)

            # Color intensity based on magnitude of change
            intensity = min(abs(change) / 3.0, 1.0)  # cap at ±3%
            if change >= 0:
                # Green shades: dark green -> bright green
                r_c = int(30 + (10 - 30) * intensity)
                g_c = int(60 + (160 - 60) * intensity)
                b_c = int(30 + (10 - 30) * intensity)
            else:
                # Red shades: dark red -> bright red
                r_c = int(60 + (180 - 60) * intensity)
                g_c = int(30 + (10 - 30) * intensity)
                b_c = int(30 + (10 - 30) * intensity)

            bg = QColor(r_c, g_c, b_c)
            painter.fillRect(int(rx), int(ry), int(rw), int(rh), bg)

            # Border
            painter.setPen(QPen(QColor("#000000"), 1))
            painter.drawRect(int(rx), int(ry), int(rw), int(rh))

            # Text — only if tile is big enough
            painter.setPen(QColor("#ffffff"))
            label = item["label"]
            change_str = f"{change:+.2f}%"

            if rw > 50 and rh > 30:
                # Ticker name — bold, larger
                font = QFont("Helvetica Neue", max(8, min(16, int(rw / len(label)))) if label else 10)
                font.setBold(True)
                painter.setFont(font)
                painter.drawText(
                    int(rx + 4), int(ry + 4), int(rw - 8), int(rh / 2),
                    Qt.AlignLeft | Qt.AlignVCenter, label,
                )
                # Change % below
                font.setBold(False)
                font.setPointSize(max(7, font.pointSize() - 2))
                painter.setFont(font)
                painter.drawText(
                    int(rx + 4), int(ry + rh / 2), int(rw - 8), int(rh / 2 - 4),
                    Qt.AlignLeft | Qt.AlignTop, change_str,
                )
            elif rw > 30 and rh > 16:
                # Just ticker
                font = QFont("Helvetica Neue", max(7, min(11, int(rw / max(len(label), 1)))))
                font.setBold(True)
                painter.setFont(font)
                painter.drawText(
                    int(rx + 2), int(ry + 2), int(rw - 4), int(rh - 4),
                    Qt.AlignCenter, label,
                )

        painter.end()
