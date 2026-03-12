#!/usr/bin/env python3
"""Portfolio Tracker — PySide6 desktop GUI for tracking investments."""

import sys
from datetime import datetime

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from market import clear_cache
from storage import Portfolio, Transaction
from qt_dialogs import (
    ConfirmDialog,
    CreatePortfolioDialog,
    HelpDialog,
    ImportDialog,
    MoveToPortfolioDialog,
    TransactionDialog,
)
from qt_widgets import (
    C_ACCENT,
    C_BG,
    C_NEGATIVE,
    C_POSITIVE,
    C_SELECTION,
    C_SURFACE,
    C_TEXT,
    C_TEXT_DIM,
    CURRENCIES,
    CURRENCY_SYMBOLS,
    SORT_LABELS,
    SORT_MODES,
    BigValueWidget,
    HeaderBar,
    HoldingsPanel,
    PriceChartWidget,
    StockDetailWidget,
    _left_aligned_item,
    _pnl_color,
    _right_aligned_item,
)
from qt_workers import (
    MarketWorker,
    _fetch_allocation_data,
    _fetch_drilldown_data,
    _fetch_holdings_data,
)


DARK_STYLESHEET = f"""
QMainWindow, QWidget {{
    background-color: {C_BG};
    color: {C_TEXT};
    font-family: "Helvetica Neue", sans-serif;
    font-size: 13px;
}}
QTabWidget::pane {{
    border: none;
    background: {C_BG};
}}
QTabBar::tab {{
    background: {C_SURFACE};
    color: {C_TEXT_DIM};
    padding: 8px 16px;
    margin-right: 2px;
    border: none;
    border-bottom: 2px solid transparent;
}}
QTabBar::tab:selected {{
    color: {C_ACCENT};
    font-weight: bold;
    border-bottom: 2px solid {C_ACCENT};
}}
QTabBar::tab:hover {{
    color: {C_TEXT};
}}
QTableWidget {{
    background-color: {C_BG};
    color: {C_TEXT};
    gridline-color: #333;
    border: none;
    selection-background-color: {C_SELECTION};
}}
QTableWidget::item {{
    padding: 4px 8px;
}}
QTableWidget QHeaderView::section {{
    background-color: {C_SURFACE};
    color: {C_ACCENT};
    font-weight: bold;
    border: none;
    padding: 6px 8px;
}}
QStatusBar {{
    background: #3a3220;
    color: #d7ba7d;
    font-size: 12px;
}}
#action-bar {{
    background: #3a3220;
    min-height: 32px;
    max-height: 32px;
}}
#action-bar QPushButton {{
    background: transparent;
    color: #d7ba7d;
    border: none;
    padding: 4px 10px;
    font-size: 12px;
    min-width: 0;
}}
#action-bar QPushButton:hover {{
    background: #4a4230;
    color: #f0d898;
    border-radius: 3px;
}}
#action-bar QPushButton:pressed {{
    background: #5a5240;
}}
#action-bar .action-key {{
    color: #f0d898;
    font-weight: bold;
}}
QScrollBar:vertical {{
    background: {C_BG};
    width: 10px;
}}
QScrollBar::handle:vertical {{
    background: #555;
    border-radius: 5px;
    min-height: 20px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
"""


# ── Pages ──────────────────────────────────────────────────────────────


class PortfolioPage(QWidget):
    """Main page showing portfolio tabs with holdings, big value, and chart."""

    navigate_to_drilldown = Signal(str, str)  # ticker, name
    navigate_to_history = Signal(str)  # portfolio_name
    navigate_to_allocation = Signal(str)  # portfolio_name

    def __init__(self, portfolio: Portfolio, parent=None):
        super().__init__(parent)
        self.portfolio = portfolio
        self._workers = {}   # tab_key -> MarketWorker
        self._panels = {}    # tab_key -> HoldingsPanel
        self._tab_data = {}  # tab_key -> last worker result dict

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._header = HeaderBar()
        layout.addWidget(self._header)

        self._big_value = BigValueWidget()
        self._big_value.setVisible(False)
        layout.addWidget(self._big_value)

        # Tab widget
        self._tabs = QTabWidget()
        self._tabs.currentChanged.connect(self._on_tab_changed)
        layout.addWidget(self._tabs, stretch=1)

        # Chart
        self._chart = PriceChartWidget()
        self._chart.setVisible(False)
        layout.addWidget(self._chart, stretch=1)

        self._build_tabs()

    def _build_tabs(self):
        self._tabs.clear()
        self._panels.clear()
        self._tab_data.clear()

        # "All" tab
        panel = HoldingsPanel(portfolio_name=None)
        panel.row_activated.connect(self._on_row_activated)
        self._panels[None] = panel
        self._tabs.addTab(panel, "All")

        for name in self.portfolio.portfolios:
            panel = HoldingsPanel(portfolio_name=name)
            panel.row_activated.connect(self._on_row_activated)
            self._panels[name] = panel
            self._tabs.addTab(panel, name)

    def _on_tab_changed(self, index):
        key = self._active_tab_key()
        data = self._tab_data.get(key)
        if data:
            self._update_from_data(data, key)

    def _active_tab_key(self) -> str | None:
        idx = self._tabs.currentIndex()
        if idx == 0:
            return None
        if idx > 0 and idx - 1 < len(self.portfolio.portfolios):
            return self.portfolio.portfolios[idx - 1]
        return None

    def _active_panel(self) -> HoldingsPanel | None:
        return self._panels.get(self._active_tab_key())

    def _on_row_activated(self, ticker, name):
        self.navigate_to_drilldown.emit(ticker, name)

    def refresh_all(self):
        """Refresh market data for all tabs."""
        for key, panel in self._panels.items():
            self._start_worker(key, panel)

    def _start_worker(self, tab_key, panel):
        # Don't start duplicate workers
        existing = self._workers.get(tab_key)
        if existing and existing.isRunning():
            return

        self._header.update_stats(loading=True)

        worker = MarketWorker(
            _fetch_holdings_data,
            self.portfolio,
            tab_key,
            self.portfolio.display_currency,
            self.portfolio.sort_mode,
        )
        worker.finished.connect(lambda data, k=tab_key: self._on_data_ready(k, data))
        worker.error.connect(lambda err: self._header.update_stats(loading=False))
        self._workers[tab_key] = worker
        worker.start()

    def _on_data_ready(self, tab_key, data):
        panel = self._panels.get(tab_key)
        if not panel:
            return

        self._tab_data[tab_key] = data
        panel.update_data(data)

        # Update header/big value/chart for active tab
        if tab_key == self._active_tab_key():
            self._update_from_data(data, tab_key)

    def _update_from_data(self, data, tab_key=None):
        if data.get("empty"):
            self._header.update_stats()
            self._big_value.setVisible(False)
            self._chart.setVisible(False)
            return

        rows = data["rows"]
        total_value = sum(r["value"] for r in rows)
        total_cost = sum(r["shares"] * r["avg"] for r in rows)
        total_pnl = total_value - total_cost
        total_pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0.0

        sort_label = SORT_LABELS.get(data.get("sort_mode", self.portfolio.sort_mode), "")
        self._header.update_stats(total_value, total_pnl, total_pnl_pct, sort_label)

        self._big_value.setVisible(True)
        self._big_value.set_value(
            total_value,
            currency=data.get("display_currency", "USD"),
            pnl_pct=total_pnl_pct,
            day_pct=data.get("day_pct", 0),
            three_month_pct=data.get("three_month_pct", 0),
        )

        chart_data = data.get("chart_data", {})
        if chart_data.get("dates"):
            self._chart.setVisible(True)
            label = tab_key or "Portfolio"
            self._chart.set_data(label, chart_data["dates"], chart_data["closes"])
        else:
            self._chart.setVisible(False)

    def cycle_sort(self):
        idx = SORT_MODES.index(self.portfolio.sort_mode)
        new_mode = SORT_MODES[(idx + 1) % len(SORT_MODES)]
        self.portfolio.sort_mode = new_mode
        self.portfolio.save()
        for panel in self._panels.values():
            panel.re_render(new_mode)
        sort_label = SORT_LABELS.get(new_mode, "")
        # Re-update header with new sort label
        panel = self._active_panel()
        if panel and panel._rows:
            self._update_header_from_panel(panel)

    def cycle_currency(self):
        idx = CURRENCIES.index(self.portfolio.display_currency)
        self.portfolio.display_currency = CURRENCIES[(idx + 1) % len(CURRENCIES)]
        self.portfolio.save()
        self.refresh_all()

    def switch_tab(self, index):
        if 0 <= index < self._tabs.count():
            self._tabs.setCurrentIndex(index)

    def add_portfolio_tab(self, name):
        panel = HoldingsPanel(portfolio_name=name)
        panel.row_activated.connect(self._on_row_activated)
        self._panels[name] = panel
        self._tabs.addTab(panel, name)
        self._tabs.setCurrentIndex(self._tabs.count() - 1)

    def remove_portfolio_tab(self, name):
        for i in range(1, self._tabs.count()):
            if self._tabs.tabText(i) == name:
                self._tabs.removeTab(i)
                self._panels.pop(name, None)
                break
        self._tabs.setCurrentIndex(0)

    def rebuild_tabs(self):
        """Rebuild tabs after portfolio changes."""
        self._build_tabs()
        self.refresh_all()


class DrillDownPage(QWidget):
    """Drill-down page for ETF holdings or stock detail."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._header = QLabel("")
        self._header.setFixedHeight(40)
        self._header.setStyleSheet(
            f"background: {C_SURFACE}; color: {C_TEXT}; font-size: 14px; padding: 0 12px;"
        )
        self._header.setAlignment(Qt.AlignVCenter)
        layout.addWidget(self._header)

        self._loading = QLabel("Fetching data...")
        self._loading.setAlignment(Qt.AlignCenter)
        self._loading.setStyleSheet(f"color: {C_TEXT_DIM}; font-size: 14px; padding: 40px;")
        layout.addWidget(self._loading)

        # Stock detail panel
        self._stock_detail = StockDetailWidget()
        self._stock_detail.setVisible(False)
        layout.addWidget(self._stock_detail)

        # ETF holdings table
        self._etf_table = QTableWidget()
        self._etf_table.setColumnCount(6)
        self._etf_table.setHorizontalHeaderLabels(["#", "Symbol", "Name", "Weight %", "Price", "Day %"])
        self._etf_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._etf_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._etf_table.verticalHeader().setVisible(False)
        self._etf_table.horizontalHeader().setStretchLastSection(True)
        self._etf_table.setVisible(False)
        layout.addWidget(self._etf_table, stretch=1)

        # Empty label
        self._empty = QLabel("Holdings data not available for this ticker.")
        self._empty.setAlignment(Qt.AlignCenter)
        self._empty.setStyleSheet(f"color: {C_TEXT_DIM}; padding: 40px;")
        self._empty.setVisible(False)
        layout.addWidget(self._empty)

        # Chart
        self._chart = PriceChartWidget()
        self._chart.setVisible(False)
        layout.addWidget(self._chart, stretch=1)

        self._worker = None

    def load(self, ticker, name, portfolio):
        """Load drill-down data for a ticker."""
        self._header.setText(f"{ticker} — {name}")
        self._loading.setVisible(True)
        self._stock_detail.setVisible(False)
        self._etf_table.setVisible(False)
        self._empty.setVisible(False)
        self._chart.setVisible(False)

        self._ticker = ticker

        self._worker = MarketWorker(_fetch_drilldown_data, ticker, portfolio)
        self._worker.finished.connect(self._on_data)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_data(self, data):
        self._loading.setVisible(False)
        ticker_info = data["ticker_info"]
        quote_type = data["quote_type"]

        # Chart
        history = data.get("history", {})
        if history.get("dates"):
            self._chart.setVisible(True)
            self._chart.set_data(self._ticker, history["dates"], history["closes"])

        price = ticker_info.get("price", 0)
        currency = ticker_info.get("currency", "")

        if quote_type == "ETF":
            etf_holdings = data.get("etf_holdings", [])
            if not etf_holdings:
                self._empty.setVisible(True)
                return

            total_weight = sum(h["weight"] for h in etf_holdings)
            self._header.setText(
                f"{self._ticker} — {ticker_info.get('name', self._ticker)}    "
                f"Weight coverage: {total_weight:.0f}%"
            )

            etf_prices = data.get("etf_prices", {})
            self._etf_table.setVisible(True)
            self._etf_table.setRowCount(len(etf_holdings))
            for i, h in enumerate(etf_holdings):
                symbol = h["symbol"]
                info = etf_prices.get(symbol, {})
                hp = info.get("price", 0)
                hname = info.get("name", h.get("name", symbol))
                change = info.get("change_pct", 0) or 0
                chg_col = C_POSITIVE if change >= 0 else C_NEGATIVE

                self._etf_table.setItem(i, 0, _left_aligned_item(str(i + 1)))
                self._etf_table.setItem(i, 1, _left_aligned_item(symbol))
                self._etf_table.setItem(i, 2, _left_aligned_item(hname[:30]))
                self._etf_table.setItem(i, 3, _right_aligned_item(f"{h['weight']:.1f}%"))
                self._etf_table.setItem(i, 4, _right_aligned_item(f"{hp:.2f}" if hp else "N/A"))
                self._etf_table.setItem(i, 5, _right_aligned_item(f"{change:+.2f}%", chg_col))

            header = self._etf_table.horizontalHeader()
            for col in range(5):
                header.setSectionResizeMode(col, QHeaderView.ResizeToContents)
            header.setSectionResizeMode(5, QHeaderView.Stretch)
        else:
            # Stock detail
            self._header.setText(
                f"{self._ticker} — {ticker_info.get('name', self._ticker)}    "
                f"Price: {price:.2f} {currency}"
            )
            shares = data.get("shares", 0)
            avg_cost = data.get("avg_cost", 0)
            self._stock_detail.setVisible(True)
            self._stock_detail.set_data(ticker_info, shares, avg_cost)

    def _on_error(self, err):
        self._loading.setText(f"Error: {err}")


class TransactionHistoryPage(QWidget):
    """Full-screen transaction history."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._portfolio = None
        self._portfolio_name = None
        self._transactions = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._header = QLabel("Transaction History")
        self._header.setFixedHeight(40)
        self._header.setStyleSheet(
            f"background: {C_SURFACE}; color: {C_ACCENT}; font-size: 14px; "
            f"font-weight: bold; padding: 0 12px;"
        )
        self._header.setAlignment(Qt.AlignVCenter)
        layout.addWidget(self._header)

        self._empty = QLabel("No transactions recorded.")
        self._empty.setAlignment(Qt.AlignCenter)
        self._empty.setStyleSheet(f"color: {C_TEXT_DIM}; padding: 40px;")
        self._empty.setVisible(False)
        layout.addWidget(self._empty)

        self._table = QTableWidget()
        self._table.setColumnCount(8)
        self._table.setHorizontalHeaderLabels(
            ["Date", "Type", "Ticker", "Shares", "Price", "Total", "Portfolio", "Note"]
        )
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setSelectionMode(QTableWidget.SingleSelection)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self._table, stretch=1)

    def load(self, portfolio, portfolio_name=None):
        self._portfolio = portfolio
        self._portfolio_name = portfolio_name
        self._refresh()

    def _refresh(self):
        txns = self._portfolio.get_transactions(portfolio_name=self._portfolio_name)
        self._transactions = sorted(txns, key=lambda x: x.date, reverse=True)

        if not self._transactions:
            self._empty.setVisible(True)
            self._table.setVisible(False)
            return

        self._empty.setVisible(False)
        self._table.setVisible(True)

        label = self._portfolio_name or "All"
        self._header.setText(f"Transaction History — {label}    {len(self._transactions)} total")

        self._table.setRowCount(len(self._transactions))
        for i, t in enumerate(self._transactions):
            type_col = C_POSITIVE if t.type == "buy" else C_NEGATIVE
            total = t.shares * t.price

            self._table.setItem(i, 0, _left_aligned_item(t.date))
            self._table.setItem(i, 1, _left_aligned_item(t.type.upper(), type_col))
            self._table.setItem(i, 2, _left_aligned_item(t.ticker))
            self._table.setItem(i, 3, _right_aligned_item(f"{t.shares:.2f}"))
            self._table.setItem(i, 4, _right_aligned_item(f"{t.price:.2f}"))
            self._table.setItem(i, 5, _right_aligned_item(f"{total:,.2f}"))
            self._table.setItem(i, 6, _left_aligned_item(t.portfolio or "—"))
            self._table.setItem(i, 7, _left_aligned_item(t.note or ""))

        header = self._table.horizontalHeader()
        for col in range(7):
            header.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.Stretch)

    def delete_selected(self):
        rows = self._table.selectionModel().selectedRows()
        if not rows:
            return
        row = rows[0].row()
        if row < 0 or row >= len(self._transactions):
            return
        txn = self._transactions[row]
        dlg = ConfirmDialog(
            f"Delete transaction?\n\n"
            f"  {txn.type.upper()} {txn.shares:.2f} x {txn.ticker} @ {txn.price:.2f}\n"
            f"  Date: {txn.date}",
            parent=self,
        )
        if dlg.exec() == ConfirmDialog.Accepted:
            self._portfolio.delete_transaction(txn)
            self._refresh()

    def move_selected(self):
        rows = self._table.selectionModel().selectedRows()
        if not rows:
            return
        row = rows[0].row()
        if row < 0 or row >= len(self._transactions):
            return
        txn = self._transactions[row]
        dlg = MoveToPortfolioDialog(
            self._portfolio.portfolios,
            current_portfolio=txn.portfolio,
            parent=self,
        )
        if dlg.exec() == MoveToPortfolioDialog.Accepted and dlg.selected_portfolio is not None:
            if txn.portfolio != dlg.selected_portfolio:
                self._portfolio.move_transaction(txn, dlg.selected_portfolio)
                self._refresh()


class AllocationPage(QWidget):
    """Allocation breakdown and look-through underlying holdings."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._header = QLabel("Portfolio Allocation & Top Holdings")
        self._header.setFixedHeight(40)
        self._header.setStyleSheet(
            f"background: {C_SURFACE}; color: {C_ACCENT}; font-size: 14px; "
            f"font-weight: bold; padding: 0 12px;"
        )
        self._header.setAlignment(Qt.AlignVCenter)
        layout.addWidget(self._header)

        self._loading = QLabel("Analyzing portfolio holdings...")
        self._loading.setAlignment(Qt.AlignCenter)
        self._loading.setStyleSheet(f"color: {C_TEXT_DIM}; font-size: 14px; padding: 40px;")
        layout.addWidget(self._loading)

        self._summary = QLabel("")
        self._summary.setFixedHeight(30)
        self._summary.setStyleSheet(f"color: {C_TEXT}; padding: 0 12px;")
        self._summary.setVisible(False)
        layout.addWidget(self._summary)

        # Allocation table
        self._alloc_table = QTableWidget()
        self._alloc_table.setColumnCount(6)
        self._alloc_table.setHorizontalHeaderLabels(["#", "Ticker", "Name", "Value", "Alloc %", "Type"])
        self._alloc_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._alloc_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._alloc_table.verticalHeader().setVisible(False)
        self._alloc_table.horizontalHeader().setStretchLastSection(True)
        self._alloc_table.setVisible(False)
        layout.addWidget(self._alloc_table, stretch=1)

        # Look-through title
        self._lt_title = QLabel("Top 10 Underlying Holdings (Look-Through)")
        self._lt_title.setFixedHeight(30)
        self._lt_title.setStyleSheet(
            f"color: {C_ACCENT}; font-weight: bold; padding: 0 12px;"
        )
        self._lt_title.setVisible(False)
        layout.addWidget(self._lt_title)

        # Look-through table
        self._lt_table = QTableWidget()
        self._lt_table.setColumnCount(5)
        self._lt_table.setHorizontalHeaderLabels(["#", "Stock", "Name", "Exposure %", "Via ETFs"])
        self._lt_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._lt_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._lt_table.verticalHeader().setVisible(False)
        self._lt_table.horizontalHeader().setStretchLastSection(True)
        self._lt_table.setVisible(False)
        layout.addWidget(self._lt_table, stretch=1)

        self._worker = None

    def load(self, portfolio, portfolio_name=None):
        self._loading.setVisible(True)
        self._summary.setVisible(False)
        self._alloc_table.setVisible(False)
        self._lt_title.setVisible(False)
        self._lt_table.setVisible(False)

        self._worker = MarketWorker(
            _fetch_allocation_data, portfolio, portfolio_name, portfolio.display_currency
        )
        self._worker.finished.connect(self._on_data)
        self._worker.error.connect(lambda err: self._loading.setText(f"Error: {err}"))
        self._worker.start()

    def _on_data(self, data):
        self._loading.setVisible(False)

        if data.get("empty"):
            self._summary.setText("No holdings to analyze.")
            self._summary.setVisible(True)
            return

        rows = data["rows"]
        total_value = data["total_value"]
        ticker_types = data["ticker_types"]
        top_underlying = data["top_underlying"]
        resolved_tickers = data.get("resolved_tickers", set())
        display_currency = data.get("display_currency", "USD")

        n_funds = sum(1 for t in ticker_types.values() if t != "EQUITY")
        n_resolved = len(resolved_tickers)
        n_stocks = len(ticker_types) - n_funds
        self._summary.setText(
            f"{len(rows)} holdings    "
            f"{n_funds} Funds ({n_resolved} resolved)    "
            f"{n_stocks} Stocks    "
            f"Total: {total_value:,.0f} {display_currency}"
        )
        self._summary.setVisible(True)

        # Allocation table
        self._alloc_table.setVisible(True)
        self._alloc_table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            alloc_pct = (r["value"] / total_value * 100) if total_value > 0 else 0
            qtype = ticker_types.get(r["ticker"], "EQUITY")
            resolved = r["ticker"] in resolved_tickers
            type_label = f"{qtype}" + (" *" if resolved else "")

            self._alloc_table.setItem(i, 0, _left_aligned_item(str(i + 1)))
            self._alloc_table.setItem(i, 1, _left_aligned_item(r["ticker"]))
            self._alloc_table.setItem(i, 2, _left_aligned_item(r["name"][:30]))
            self._alloc_table.setItem(i, 3, _right_aligned_item(f"{r['value']:,.0f}"))
            self._alloc_table.setItem(i, 4, _right_aligned_item(f"{alloc_pct:.1f}%"))
            self._alloc_table.setItem(i, 5, _left_aligned_item(type_label))

        header = self._alloc_table.horizontalHeader()
        for col in range(5):
            header.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.Stretch)

        # Look-through table
        self._lt_title.setVisible(True)
        self._lt_table.setVisible(True)
        self._lt_table.setRowCount(len(top_underlying))
        for i, (sym, udata) in enumerate(top_underlying):
            sources = ", ".join(dict.fromkeys(udata["sources"]))
            self._lt_table.setItem(i, 0, _left_aligned_item(str(i + 1)))
            self._lt_table.setItem(i, 1, _left_aligned_item(sym))
            self._lt_table.setItem(i, 2, _left_aligned_item(udata["name"][:30]))
            self._lt_table.setItem(i, 3, _right_aligned_item(f"{udata['exposure_pct']:.2f}%"))
            self._lt_table.setItem(i, 4, _left_aligned_item(sources[:40]))

        lt_header = self._lt_table.horizontalHeader()
        for col in range(4):
            lt_header.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        lt_header.setSectionResizeMode(4, QHeaderView.Stretch)


# ── MainWindow ─────────────────────────────────────────────────────────


class MainWindow(QMainWindow):
    """Main application window with stacked page navigation."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Portfolio Tracker")
        self.resize(1100, 750)

        self.portfolio = Portfolio()

        # Screen stack for navigation
        self._screen_stack = []

        # Stacked widget
        self._stack = QStackedWidget()
        self.setCentralWidget(self._stack)

        # Pages
        self._portfolio_page = PortfolioPage(self.portfolio)
        self._portfolio_page.navigate_to_drilldown.connect(self._push_drilldown)
        self._portfolio_page.navigate_to_history.connect(self._push_history)
        self._portfolio_page.navigate_to_allocation.connect(self._push_allocation)

        self._drilldown_page = DrillDownPage()
        self._history_page = TransactionHistoryPage()
        self._allocation_page = AllocationPage()

        self._stack.addWidget(self._portfolio_page)    # index 0
        self._stack.addWidget(self._drilldown_page)    # index 1
        self._stack.addWidget(self._history_page)      # index 2
        self._stack.addWidget(self._allocation_page)   # index 3

        self._stack.setCurrentIndex(0)
        self._screen_stack = [0]

        # Action bar (clickable buttons at the bottom)
        self._action_bar = QWidget()
        self._action_bar.setObjectName("action-bar")
        self._action_bar_layout = QHBoxLayout(self._action_bar)
        self._action_bar_layout.setContentsMargins(4, 0, 4, 0)
        self._action_bar_layout.setSpacing(2)
        self._status = self.statusBar()
        self._status.setStyleSheet("background: #3a3220; padding: 0; margin: 0;")
        self._status.addPermanentWidget(self._action_bar, 1)
        self._update_status_hints()

        # Shortcuts
        self._setup_shortcuts()

        # Auto-refresh timer (30 minutes)
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._do_refresh)
        self._refresh_timer.start(1800000)

        # Initial data load
        self._portfolio_page.refresh_all()

    def closeEvent(self, event):
        """Wait for running workers before closing."""
        self._refresh_timer.stop()
        # Collect all running workers
        workers = list(self._portfolio_page._workers.values())
        for page in (self._drilldown_page, self._allocation_page):
            if page._worker:
                workers.append(page._worker)
        # Disconnect signals and wait for each running worker
        for worker in workers:
            if worker.isRunning():
                try:
                    worker.finished.disconnect()
                    worker.error.disconnect()
                except RuntimeError:
                    pass
                worker.wait(3000)
                if worker.isRunning():
                    worker.terminate()
                    worker.wait(1000)
        super().closeEvent(event)

    def _setup_shortcuts(self):
        # Global shortcuts
        self._sc_quit = QShortcut(QKeySequence("Q"), self)
        self._sc_quit.activated.connect(self.close)

        self._sc_refresh = QShortcut(QKeySequence("R"), self)
        self._sc_refresh.activated.connect(self._do_refresh)

        self._sc_help = QShortcut(QKeySequence("?"), self)
        self._sc_help.activated.connect(self._show_help)

        self._sc_escape = QShortcut(QKeySequence("Escape"), self)
        self._sc_escape.activated.connect(self._go_back)

        # Portfolio page shortcuts
        self._sc_buy = QShortcut(QKeySequence("B"), self)
        self._sc_buy.activated.connect(self._action_buy)

        self._sc_sell = QShortcut(QKeySequence("S"), self)
        self._sc_sell.activated.connect(self._action_sell)

        self._sc_history = QShortcut(QKeySequence("T"), self)
        self._sc_history.activated.connect(self._action_history)

        self._sc_import = QShortcut(QKeySequence("I"), self)
        self._sc_import.activated.connect(self._action_import)

        self._sc_sort = QShortcut(QKeySequence("O"), self)
        self._sc_sort.activated.connect(self._action_sort)

        self._sc_currency = QShortcut(QKeySequence("C"), self)
        self._sc_currency.activated.connect(self._action_currency)

        self._sc_allocation = QShortcut(QKeySequence("A"), self)
        self._sc_allocation.activated.connect(self._action_allocation)

        self._sc_move = QShortcut(QKeySequence("M"), self)
        self._sc_move.activated.connect(self._action_move)

        self._sc_new_portfolio = QShortcut(QKeySequence("N"), self)
        self._sc_new_portfolio.activated.connect(self._action_new_portfolio)

        self._sc_delete = QShortcut(QKeySequence("D"), self)
        self._sc_delete.activated.connect(self._action_delete)

        self._sc_enter = QShortcut(QKeySequence("Return"), self)
        self._sc_enter.activated.connect(self._action_enter)

        # Tab shortcuts 1-9
        self._tab_shortcuts = []
        for i in range(1, 10):
            sc = QShortcut(QKeySequence(str(i)), self)
            sc.activated.connect(lambda idx=i-1: self._switch_tab(idx))
            self._tab_shortcuts.append(sc)

        # Group shortcuts by page context
        self._portfolio_shortcuts = [
            self._sc_buy, self._sc_sell, self._sc_history, self._sc_import,
            self._sc_sort, self._sc_currency, self._sc_allocation,
            self._sc_move, self._sc_new_portfolio, self._sc_enter,
        ] + self._tab_shortcuts

        self._history_shortcuts = []  # d and m are handled via _action_delete/_action_move

    def _current_page_index(self):
        return self._stack.currentIndex()

    def _set_shortcuts_for_page(self, page_index):
        """Enable/disable shortcuts based on current page."""
        on_portfolio = page_index == 0
        for sc in self._portfolio_shortcuts:
            sc.setEnabled(on_portfolio)
        # d/m/n are context-dependent
        self._sc_delete.setEnabled(True)  # always enabled, context-switches behavior
        self._sc_move.setEnabled(True)
        self._sc_new_portfolio.setEnabled(on_portfolio)

    def _push_page(self, index):
        self._screen_stack.append(index)
        self._stack.setCurrentIndex(index)
        self._set_shortcuts_for_page(index)
        self._update_status_hints()

    def _go_back(self):
        if len(self._screen_stack) > 1:
            self._screen_stack.pop()
            idx = self._screen_stack[-1]
            self._stack.setCurrentIndex(idx)
            self._set_shortcuts_for_page(idx)
            self._update_status_hints()
            # Refresh portfolio data when coming back
            if idx == 0:
                self._portfolio_page.refresh_all()

    def _update_status_hints(self):
        # Clear existing buttons
        while self._action_bar_layout.count():
            item = self._action_bar_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        idx = self._current_page_index()
        if idx == 0:
            buttons = [
                ("B Buy", self._action_buy),
                ("S Sell", self._action_sell),
                ("T History", self._action_history),
                ("A Alloc", self._action_allocation),
                ("O Sort", self._action_sort),
                ("C Currency", self._action_currency),
                ("I Import", self._action_import),
                ("N New", self._action_new_portfolio),
                ("D Del", self._action_delete),
                ("M Move", self._action_move),
                ("R Refresh", self._do_refresh),
                ("? Help", self._show_help),
                ("Q Quit", self.close),
            ]
        elif idx == 2:
            buttons = [
                ("D Delete", self._action_delete),
                ("M Move", self._action_move),
                ("Esc Back", self._go_back),
                ("? Help", self._show_help),
                ("Q Quit", self.close),
            ]
        else:
            buttons = [
                ("Esc Back", self._go_back),
                ("? Help", self._show_help),
                ("Q Quit", self.close),
            ]

        for label, callback in buttons:
            btn = QPushButton(label)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(callback)
            self._action_bar_layout.addWidget(btn)

        self._action_bar_layout.addStretch()

    # ── Navigation actions ──

    def _push_drilldown(self, ticker, name):
        self._drilldown_page.load(ticker, name, self.portfolio)
        self._push_page(1)

    def _push_history(self, portfolio_name=""):
        self._history_page.load(self.portfolio, portfolio_name or None)
        self._push_page(2)

    def _push_allocation(self, portfolio_name=""):
        self._allocation_page.load(self.portfolio, portfolio_name or None)
        self._push_page(3)

    # ── Shortcut actions ──

    def _do_refresh(self):
        clear_cache()
        idx = self._current_page_index()
        if idx == 0:
            self._portfolio_page.refresh_all()

    def _show_help(self):
        HelpDialog(parent=self).exec()

    def _action_buy(self):
        if self._current_page_index() != 0:
            return
        pname = self._portfolio_page._active_tab_key() or ""
        dlg = TransactionDialog("buy", portfolio_name=pname, parent=self)
        if dlg.exec() == TransactionDialog.Accepted and dlg.result_data:
            txn = Transaction(**dlg.result_data)
            self.portfolio.add_transaction(txn)
            self._portfolio_page.refresh_all()

    def _action_sell(self):
        if self._current_page_index() != 0:
            return
        pname = self._portfolio_page._active_tab_key() or ""
        dlg = TransactionDialog("sell", portfolio_name=pname, parent=self)
        if dlg.exec() == TransactionDialog.Accepted and dlg.result_data:
            txn = Transaction(**dlg.result_data)
            self.portfolio.add_transaction(txn)
            self._portfolio_page.refresh_all()

    def _action_history(self):
        if self._current_page_index() != 0:
            return
        pname = self._portfolio_page._active_tab_key() or ""
        self._push_history(pname)

    def _action_import(self):
        if self._current_page_index() != 0:
            return
        pname = self._portfolio_page._active_tab_key() or ""
        dlg = ImportDialog(portfolio_name=pname, parent=self)
        if dlg.exec() == ImportDialog.Accepted and dlg.import_result:
            if dlg.import_result.get("imported", 0) > 0:
                self._portfolio_page.refresh_all()

    def _action_sort(self):
        if self._current_page_index() != 0:
            return
        self._portfolio_page.cycle_sort()

    def _action_currency(self):
        if self._current_page_index() != 0:
            return
        self._portfolio_page.cycle_currency()

    def _action_allocation(self):
        if self._current_page_index() != 0:
            return
        pname = self._portfolio_page._active_tab_key() or ""
        self._push_allocation(pname)

    def _action_move(self):
        idx = self._current_page_index()
        if idx == 0:
            self._move_ticker()
        elif idx == 2:
            self._history_page.move_selected()

    def _action_new_portfolio(self):
        if self._current_page_index() != 0:
            return
        dlg = CreatePortfolioDialog(parent=self)
        if dlg.exec() == CreatePortfolioDialog.Accepted and dlg.portfolio_name:
            name = dlg.portfolio_name
            if not self.portfolio.add_portfolio(name):
                return  # already exists
            self._portfolio_page.add_portfolio_tab(name)
            self._portfolio_page.refresh_all()

    def _action_delete(self):
        idx = self._current_page_index()
        if idx == 0:
            self._delete_portfolio()
        elif idx == 2:
            self._history_page.delete_selected()

    def _action_enter(self):
        if self._current_page_index() != 0:
            return
        panel = self._portfolio_page._active_panel()
        if panel:
            panel.activate_selected_row()

    def _switch_tab(self, index):
        if self._current_page_index() != 0:
            return
        self._portfolio_page.switch_tab(index)

    def _move_ticker(self):
        panel = self._portfolio_page._active_panel()
        if not panel:
            return
        ticker = panel.get_selected_ticker()
        if not ticker:
            return
        from_p = self._portfolio_page._active_tab_key() or ""
        dlg = MoveToPortfolioDialog(
            self.portfolio.portfolios,
            current_portfolio=from_p,
            parent=self,
        )
        if dlg.exec() == MoveToPortfolioDialog.Accepted and dlg.selected_portfolio is not None:
            target = dlg.selected_portfolio
            if target == from_p:
                return
            moved = self.portfolio.move_ticker(ticker, None if not from_p else from_p, target)
            if moved:
                self._portfolio_page.refresh_all()

    def _delete_portfolio(self):
        pname = self._portfolio_page._active_tab_key()
        if not pname:
            return  # can't delete "All"
        dlg = ConfirmDialog(
            f"Delete portfolio '{pname}'?\n\nTransactions will become untagged.",
            parent=self,
        )
        if dlg.exec() == ConfirmDialog.Accepted:
            self.portfolio.remove_portfolio(pname)
            self._portfolio_page.remove_portfolio_tab(pname)
            self._portfolio_page.refresh_all()


# ── Entry point ────────────────────────────────────────────────────────


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(DARK_STYLESHEET)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
